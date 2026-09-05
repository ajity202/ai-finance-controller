"""
Deterministic Reconciliation Rule Engine

Pipeline:

    UnifiedTransaction
            |
            v
      Rule Engine
       /       \
   MATCHED    EXCEPTION
      |           |
 RECONCILED    LLM Agent

The rule engine performs deterministic checks only.
AI/LLM analysis happens later for exceptions.
"""

import os
from decimal import Decimal
from typing import List, Optional, Set

from model import (
    UnifiedTransaction,
    ReconciliationResult,
    ExceptionType,
    FinalStatus,
)


# ============================================================
# CONFIGURATION
# ============================================================

TOLERANCE = Decimal("0.01")

# Standard gateway fee used when Gateway data is unavailable.
STANDARD_FEE_RATE = Decimal("0.02")

# Settlement delays greater than this are exceptions.
MAX_SETTLEMENT_DELAY_DAYS = 3


# ============================================================
# RESULT HELPERS
# ============================================================

def _create_match(
    transaction: UnifiedTransaction,
) -> ReconciliationResult:
    """Create a successful deterministic reconciliation result."""

    return ReconciliationResult(
        unified_transaction_id=transaction.unified_transaction_id,
        final_status=FinalStatus.RECONCILED,
        exception_type=None,
        difference=Decimal("0.00"),
        resolution=(
            "Transaction successfully reconciled "
            "using deterministic rules."
        ),
        confidence_score=1.0,
        ai_explanation=None,
        recommended_action="No action required.",
        requires_human_review=False,
    )


def _create_exception(
    transaction: UnifiedTransaction,
    exception_type: ExceptionType,
    resolution: str,
    difference: Decimal = Decimal("0.00"),
) -> ReconciliationResult:
    """
    Create an exception result.

    Exceptions remain UNRESOLVED until the LLM/Decision
    Engine analyzes them.
    """

    return ReconciliationResult(
        unified_transaction_id=transaction.unified_transaction_id,
        final_status=FinalStatus.UNRESOLVED,
        exception_type=exception_type,
        difference=abs(difference),
        resolution=resolution,
        confidence_score=None,
        ai_explanation=None,
        recommended_action=(
            "Send exception to LLM Agent for analysis."
        ),
        requires_human_review=True,
    )


# ============================================================
# RULE 1 — MISSING RECORDS
# ============================================================

def _check_missing_records(
    transaction: UnifiedTransaction,
) -> Optional[ReconciliationResult]:
    """
    Check mandatory source records.

    Internal Ledger and Bank Settlement are mandatory.
    Payment Gateway is optional.
    """

    if transaction.internal_ledger is None:
        return _create_exception(
            transaction,
            ExceptionType.MISSING_RECORD,
            "Internal ledger record is missing.",
        )

    if transaction.bank is None:
        return _create_exception(
            transaction,
            ExceptionType.MISSING_RECORD,
            "Bank settlement record is missing.",
        )

    return None


# ============================================================
# RULE 2 — DUPLICATE
# ============================================================

def _check_duplicate(
    transaction: UnifiedTransaction,
    seen_orders: Set[str],
) -> Optional[ReconciliationResult]:
    """
    Detect duplicate Order IDs within the batch.

    The first occurrence is treated as the original.
    Subsequent occurrences are treated as duplicates.
    """

    order_id = transaction.order_id

    if not order_id:
        return None

    if order_id in seen_orders:
        return _create_exception(
            transaction,
            ExceptionType.DUPLICATE,
            (
                f"Duplicate transaction detected for "
                f"Order ID: {order_id}."
            ),
        )

    seen_orders.add(order_id)

    return None


# ============================================================
# RULE 3 — CHARGEBACK
# ============================================================

def _check_chargeback(
    transaction: UnifiedTransaction,
) -> Optional[ReconciliationResult]:
    """Detect chargeback transactions."""

    # Check Bank Settlement first
    if transaction.bank is not None:
        if transaction.bank.transaction_type == "CHARGEBACK":
            return _create_exception(
                transaction,
                ExceptionType.CHARGEBACK,
                "Chargeback transaction detected in bank settlement data.",
                abs(transaction.bank.settlement_amount),
            )

    # Check Payment Gateway
    if transaction.gateway is not None:
        if transaction.gateway.chargeback_amount > Decimal("0.00"):
            return _create_exception(
                transaction,
                ExceptionType.CHARGEBACK,
                "Chargeback amount detected in payment gateway data.",
                transaction.gateway.chargeback_amount,
            )

    return None


# ============================================================
# RULE 4 — REFUND
# ============================================================

def _check_refund(
    transaction: UnifiedTransaction,
) -> Optional[ReconciliationResult]:
    """Detect refund transactions."""

    # Check Bank Settlement first
    if transaction.bank is not None:
        if transaction.bank.transaction_type == "REFUND":
            return _create_exception(
                transaction,
                ExceptionType.REFUND,
                "Refund transaction detected in bank settlement data.",
                abs(transaction.bank.settlement_amount),
            )

    # Check Payment Gateway
    if transaction.gateway is not None:
        if transaction.gateway.refund_amount > Decimal("0.00"):
            return _create_exception(
                transaction,
                ExceptionType.REFUND,
                "Refund amount detected in payment gateway data.",
                transaction.gateway.refund_amount,
            )

    # Check Internal Ledger for negative amount
    if transaction.internal_ledger is not None:
        if transaction.internal_ledger.amount < Decimal("0.00"):
            return _create_exception(
                transaction,
                ExceptionType.REFUND,
                "Negative ledger amount indicates a refund.",
                abs(transaction.internal_ledger.amount),
            )

    return None

# ============================================================
# RULE 5 — TIMING DIFFERENCE
# ============================================================

def _check_timing_difference(
    transaction: UnifiedTransaction,
) -> Optional[ReconciliationResult]:
    """
    Detect unusually delayed settlements.

    Date fields are already Pydantic date objects.
    """

    if (
        transaction.internal_ledger is None
        or transaction.bank is None
    ):
        return None

    ledger_date = (
        transaction.internal_ledger.transaction_date
    )

    settlement_date = (
        transaction.bank.settlement_date
    )

    delay_days = (
        settlement_date - ledger_date
    ).days

    # Settlement before transaction date.
    if delay_days < 0:
        return _create_exception(
            transaction,
            ExceptionType.TIMING_DIFFERENCE,
            (
                "Bank settlement date occurs before "
                "the ledger transaction date."
            ),
        )

    # Settlement delayed beyond normal window.
    if delay_days > MAX_SETTLEMENT_DELAY_DAYS:
        return _create_exception(
            transaction,
            ExceptionType.TIMING_DIFFERENCE,
            (
                f"Bank settlement occurred {delay_days} "
                f"days after the ledger transaction."
            ),
        )

    return None


# ============================================================
# RULE 6 — AMOUNT AND FEE RECONCILIATION
# ============================================================

def _check_amounts(
    transaction: UnifiedTransaction,
) -> Optional[ReconciliationResult]:
    """
    Reconcile monetary values across available sources.

    When Gateway exists:

        Ledger Gross
             |
             v
        Gateway Gross
             |
          - Gateway Fee
             |
             v
        Gateway Net
             |
          - Bank Fee
             |
             v
        Bank Settlement

    When Gateway is unavailable:

        Ledger Amount
             |
        Standard 2% fee
             |
             v
        Expected Settlement
             |
             v
        Bank Settlement
    """

    ledger_amount = transaction.ledger_amount
    bank_amount = transaction.bank_settlement_amount

    if ledger_amount is None or bank_amount is None:
        return _create_exception(
            transaction,
            ExceptionType.UNKNOWN,
            "Required monetary values are unavailable.",
        )

    # ========================================================
    # PAYMENT GATEWAY AVAILABLE
    # ========================================================

    if transaction.gateway is not None:

        gateway_gross = (
            transaction.gateway_gross_amount
        )

        gateway_net = (
            transaction.gateway_net_amount
        )

        gateway_fee = (
            transaction.gateway_fee
            or Decimal("0.00")
        )

        bank_fee = (
            transaction.bank_fee
            or Decimal("0.00")
        )

        if gateway_gross is None or gateway_net is None:
            return _create_exception(
                transaction,
                ExceptionType.UNKNOWN,
                "Payment Gateway record is incomplete.",
            )

        # ----------------------------------------------------
        # A. Ledger Gross ↔ Gateway Gross
        # ----------------------------------------------------

        gross_difference = abs(
            ledger_amount - gateway_gross
        )

        if gross_difference > TOLERANCE:
            return _create_exception(
                transaction,
                ExceptionType.AMOUNT_MISMATCH,
                (
                    "Ledger amount does not match "
                    "Gateway gross amount."
                ),
                gross_difference,
            )

        # ----------------------------------------------------
        # B. CHECK STANDARD GATEWAY FEE
        # ----------------------------------------------------
        #
        # This is important for detecting the synthetic
        # FEE_DIFFERENCE scenarios.
        #
        # Example:
        #   Expected 2% fee = ₹200
        #   Actual fee      = ₹350
        #
        # → FEE_DIFFERENCE
        # ----------------------------------------------------

        expected_gateway_fee = (
            gateway_gross * STANDARD_FEE_RATE
        )

        fee_difference = abs(
            gateway_fee - expected_gateway_fee
        )

        if fee_difference > TOLERANCE:

            return _create_exception(
                transaction,
                ExceptionType.FEE_DIFFERENCE,
                (
                    f"Gateway fee differs from the "
                    f"standard {STANDARD_FEE_RATE * 100}% "
                    f"fee. Expected: "
                    f"{expected_gateway_fee}, "
                    f"Actual: {gateway_fee}."
                ),
                fee_difference,
            )

        # ----------------------------------------------------
        # C. Verify Gateway Net
        # ----------------------------------------------------

        calculated_gateway_net = (
            gateway_gross - gateway_fee
        )

        gateway_net_difference = abs(
            calculated_gateway_net - gateway_net
        )

        if gateway_net_difference > TOLERANCE:
            return _create_exception(
                transaction,
                ExceptionType.FEE_DIFFERENCE,
                (
                    "Gateway net amount does not equal "
                    "gross amount minus gateway fee."
                ),
                gateway_net_difference,
            )

        # ----------------------------------------------------
        # D. Gateway Net ↔ Bank Settlement
        # ----------------------------------------------------

        expected_bank_amount = (
            gateway_net - bank_fee
        )

        bank_difference = abs(
            expected_bank_amount - bank_amount
        )

        if bank_difference <= TOLERANCE:
            return _create_match(transaction)

        # ----------------------------------------------------
        # E. Direct Gateway Net ↔ Bank Check
        # ----------------------------------------------------

        gateway_bank_difference = abs(
            gateway_net - bank_amount
        )

        if (
            bank_fee > Decimal("0.00")
            and abs(
                gateway_bank_difference - bank_fee
            ) <= TOLERANCE
        ):
            return _create_match(transaction)

        # ----------------------------------------------------
        # F. Genuine Amount Mismatch
        # ----------------------------------------------------

        return _create_exception(
            transaction,
            ExceptionType.AMOUNT_MISMATCH,
            (
                "Bank settlement does not match the "
                "expected Gateway net amount."
            ),
            bank_difference,
        )

    # ========================================================
    # PAYMENT GATEWAY NOT AVAILABLE
    # ========================================================

    # Gateway is optional.
    # Reconcile Ledger directly against Bank.

    direct_difference = abs(
        ledger_amount - bank_amount
    )

    # Exact Ledger ↔ Bank match.
    if direct_difference <= TOLERANCE:
        return _create_match(transaction)

    # --------------------------------------------------------
    # Check expected standard 2% fee
    # --------------------------------------------------------

    expected_net = (
        ledger_amount
        * (Decimal("1") - STANDARD_FEE_RATE)
    )

    fee_adjusted_difference = abs(
        expected_net - bank_amount
    )

    if fee_adjusted_difference <= TOLERANCE:
        return _create_match(transaction)

    # --------------------------------------------------------
    # No deterministic explanation
    # --------------------------------------------------------

    return _create_exception(
        transaction,
        ExceptionType.AMOUNT_MISMATCH,
        (
            "Bank settlement does not match the ledger "
            "amount or expected amount after the standard fee."
        ),
        direct_difference,
    )


# ============================================================
# MAIN TRANSACTION EVALUATOR
# ============================================================

def evaluate_transaction(
    transaction: UnifiedTransaction,
    seen_orders: Optional[Set[str]] = None,
) -> ReconciliationResult:
    """
    Evaluate one normalized transaction.

    Rule priority:
        1. Chargeback
        2. Refund
        3. Duplicate
        4. Missing Record
        5. Timing Difference
        6. Amount / Fee
        7. Unknown
    """

    if seen_orders is None:
        seen_orders = set()

    # --------------------------------------------------------
    # 1. Chargeback
    # --------------------------------------------------------

    result = _check_chargeback(transaction)

    if result is not None:
        return result

    # --------------------------------------------------------
    # 2. Refund
    # --------------------------------------------------------

    result = _check_refund(transaction)

    if result is not None:
        return result

    # --------------------------------------------------------
    # 3. Duplicate
    # --------------------------------------------------------

    result = _check_duplicate(
        transaction,
        seen_orders,
    )

    if result is not None:
        return result

    # --------------------------------------------------------
    # 4. Missing records
    # --------------------------------------------------------

    result = _check_missing_records(transaction)

    if result is not None:
        return result

    # --------------------------------------------------------
    # 5. Timing Difference
    # --------------------------------------------------------

    result = _check_timing_difference(transaction)

    if result is not None:
        return result

    # --------------------------------------------------------
    # 6. Amount / Fee
    # --------------------------------------------------------

    result = _check_amounts(transaction)

    if result is not None:
        return result

    # --------------------------------------------------------
    # 7. Fallback
    # --------------------------------------------------------

    return _create_exception(
        transaction,
        ExceptionType.UNKNOWN,
        "Transaction could not be classified by deterministic rules.",
    )
# ============================================================
# BATCH EVALUATION
# ============================================================

def evaluate_transactions(
    transactions: List[UnifiedTransaction],
) -> List[ReconciliationResult]:
    """
    Evaluate the complete normalized transaction batch.
    """

    results = []

    seen_orders: Set[str] = set()

    for transaction in transactions:

        result = evaluate_transaction(
            transaction,
            seen_orders,
        )

        results.append(result)

    return results

# ============================================================
# BACKWARD-COMPATIBLE BATCH ALIAS
# ============================================================

def reconcile_batch(
    transactions: List[UnifiedTransaction],
) -> List[ReconciliationResult]:
    """
    Alias for batch reconciliation.

    Keeps compatibility with external testing scripts
    without changing the rule engine logic.
    """
    return evaluate_transactions(transactions)


# ============================================================
# LOCAL INTEGRATION TEST
# ============================================================

if __name__ == "__main__":

    try:
        from ingestion import ingest_and_normalize

    except ImportError:
        print("ERROR: Could not import ingestion.py.")
        raise SystemExit(1)

    # --------------------------------------------------------
    # Project paths
    # --------------------------------------------------------

    base_dir = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
        )
    )

    ledger_path = os.path.join(
        base_dir,
        "data",
        "raw",
        "internal_ledger.csv",
    )

    bank_path = os.path.join(
        base_dir,
        "data",
        "raw",
        "bank_settlement.csv",
    )

    gateway_path = os.path.join(
        base_dir,
        "data",
        "raw",
        "payment_gateway.csv",
    )

    # --------------------------------------------------------
    # Execute pipeline
    # --------------------------------------------------------

    try:

        print("=" * 60)
        print("AI FINANCE CONTROLLER")
        print("DETERMINISTIC RULE ENGINE")
        print("=" * 60)

        print("\nLoading source data...")

        transactions = ingest_and_normalize(
            ledger_path=ledger_path,
            bank_path=bank_path,
            gateway_path=gateway_path,
        )

        print(
            f"Normalized Transactions : {len(transactions)}"
        )

        print("\nRunning deterministic reconciliation...")

        results = evaluate_transactions(
            transactions
        )

        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------

        reconciled_count = sum(
            1
            for result in results
            if result.final_status
            == FinalStatus.RECONCILED
        )

        exception_count = (
            len(results) - reconciled_count
        )

        print("\n" + "=" * 60)
        print("RULE ENGINE SUMMARY")
        print("=" * 60)

        print(
            f"Total Transactions       : {len(results)}"
        )

        print(
            f"Auto-Reconciled          : {reconciled_count}"
        )

        print(
            f"Exceptions               : {exception_count}"
        )

        print("=" * 60)

        # ----------------------------------------------------
        # Exception breakdown
        # ----------------------------------------------------

        exception_tallies = {}

        for result in results:

            if result.exception_type is not None:

                exception_name = str(
                    result.exception_type
                )

                exception_tallies[exception_name] = (
                    exception_tallies.get(
                        exception_name,
                        0,
                    )
                    + 1
                )

        print("\nException Breakdown:")

        if not exception_tallies:

            print("  No exceptions detected.")

        else:

            for exception_name, count in sorted(
                exception_tallies.items()
            ):

                print(
                    f"  {exception_name:<20} : {count}"
                )

        print(
            "\nRule engine execution completed."
        )

    except Exception as error:

        print(
            f"\nRule engine execution failed: {error}"
        )

        raise