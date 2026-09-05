import csv
import os
import random
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP


# ============================================================
# HELPERS
# ============================================================

def quantize_amount(value: Decimal) -> Decimal:
    """Format a Decimal strictly to 2 decimal places."""
    return value.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def make_unified_id(
    transaction_id: str,
    gateway_reference: str = None,
    bank_reference: str = None,
) -> str:
    """
    Generate the same UnifiedTransaction ID format used
    by ingestion.py.
    """

    if bank_reference:
        return f"UNI_{transaction_id}_{bank_reference}"

    if gateway_reference:
        return f"UNI_{transaction_id}_{gateway_reference}"

    return f"UNI_{transaction_id}"


def make_bank_only_id(bank_reference: str) -> str:
    """Generate the same ID used by ingestion.py for unmatched bank records."""
    return f"UNI_BANK_{bank_reference}"


# ============================================================
# DATASET GENERATOR
# ============================================================

def generate_synthetic_reconciliation_data(
    raw_dir: str = "data/raw",
    processed_dir: str = "data/processed",
    seed: int = 42,
) -> None:

    random.seed(seed)

    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    base_date = datetime(2026, 8, 1, 9, 0, 0)
    currency = "INR"

    internal_ledger = []
    payment_gateway = []
    bank_settlement = []
    ground_truth = []

    # ============================================================
    # BUSINESS SCENARIOS
    # ============================================================
    #
    # 001 - 050 : CLEAN_MATCH
    # 051 - 060 : FEE_DIFFERENCE
    # 061 - 068 : TIMING_DIFFERENCE
    # 069 - 076 : AMOUNT_MISMATCH
    # 077 - 086 : MISSING_RECORD
    # 087 - 092 : DUPLICATE
    # 093 - 100 : REFUND
    # 101 - 105 : CHARGEBACK
    # 106 - 110 : UNRESOLVED
    #
    # Business scenarios = 110
    #
    # Normalized transactions = 121 because:
    #   - 6 duplicate scenarios create 12 normalized records
    #   - 5 unresolved scenarios create 10 normalized records
    # ============================================================

    for i in range(1, 111):

        transaction_id = f"TXN_{1000 + i}"
        order_id = f"ORD_{1000 + i}"
        invoice_id = f"INV_{1000 + i}"
        customer_id = f"CUST_{random.randint(100, 999)}"

        gateway_ref = f"pay_G{1000 + i}"
        bank_ref = f"BNK_UTR_{5000 + i}"

        transaction_time = (
            base_date
            + timedelta(
                hours=i * 2,
                minutes=random.randint(5, 55),
            )
        )

        transaction_date = transaction_time.strftime(
            "%Y-%m-%d"
        )

        base_amount = quantize_amount(
            Decimal(random.randint(500, 15000))
        )

        standard_gateway_fee = quantize_amount(
            base_amount * Decimal("0.02")
        )

        expected_settlement = quantize_amount(
            base_amount - standard_gateway_fee
        )

        settlement_date = (
            transaction_time + timedelta(days=1)
        ).strftime("%Y-%m-%d")

        # ========================================================
        # 1. CLEAN MATCH — 1 to 50
        # ========================================================

        if i <= 50:

            internal_ledger.append({
                "transaction_id": transaction_id,
                "order_id": order_id,
                "invoice_id": invoice_id,
                "transaction_date": transaction_date,
                "amount": str(base_amount),
                "currency": currency,
                "customer_id": customer_id,
                "reference_id": gateway_ref,
            })

            payment_gateway.append({
                "gateway_reference": gateway_ref,
                "order_id": order_id,
                "transaction_date": transaction_date,
                "gross_amount": str(base_amount),
                "fee": str(standard_gateway_fee),
                "net_amount": str(expected_settlement),
                "currency": currency,
                "refund_amount": "0.00",
                "chargeback_amount": "0.00",
            })

            bank_settlement.append({
                "bank_reference": bank_ref,
                "gateway_reference": gateway_ref,
                "settlement_date": settlement_date,
                "settlement_amount": str(expected_settlement),
                "bank_fee": "0.00",
                "currency": currency,
            })

            ground_truth.append({
                "unified_transaction_id": make_unified_id(
                    transaction_id,
                    gateway_ref,
                    bank_ref,
                ),
                "order_id": order_id,
                "scenario_type": "CLEAN_MATCH",
                "expected_rule_engine_outcome": "MATCHED",
                "expected_exception_type": "",
                "expected_final_status": "RECONCILED",
                "notes": (
                    "Ledger, gateway and bank amounts reconcile exactly."
                ),
            })

        # ========================================================
        # 2. FEE DIFFERENCE — 51 to 60
        # ========================================================

        elif i <= 60:

            custom_fee_rate = (
                Decimal("0.035")
                if i % 2 == 0
                else Decimal("0.015")
            )

            actual_fee = quantize_amount(
                base_amount * custom_fee_rate
            )

            actual_settlement = quantize_amount(
                base_amount - actual_fee
            )

            internal_ledger.append({
                "transaction_id": transaction_id,
                "order_id": order_id,
                "invoice_id": invoice_id,
                "transaction_date": transaction_date,
                "amount": str(base_amount),
                "currency": currency,
                "customer_id": customer_id,
                "reference_id": gateway_ref,
            })

            payment_gateway.append({
                "gateway_reference": gateway_ref,
                "order_id": order_id,
                "transaction_date": transaction_date,
                "gross_amount": str(base_amount),
                "fee": str(actual_fee),
                "net_amount": str(actual_settlement),
                "currency": currency,
                "refund_amount": "0.00",
                "chargeback_amount": "0.00",
            })

            bank_settlement.append({
                "bank_reference": bank_ref,
                "gateway_reference": gateway_ref,
                "settlement_date": settlement_date,
                "settlement_amount": str(actual_settlement),
                "bank_fee": "0.00",
                "currency": currency,
            })

            ground_truth.append({
                "unified_transaction_id": make_unified_id(
                    transaction_id,
                    gateway_ref,
                    bank_ref,
                ),
                "order_id": order_id,
                "scenario_type": "FEE_DIFFERENCE",
                "expected_rule_engine_outcome": "EXCEPTION",
                "expected_exception_type": "FEE_DIFFERENCE",
                "expected_final_status": "UNRESOLVED",
                "notes": (
                    f"Gateway fee differs from the configured "
                    f"standard 2% fee. Actual fee rate: "
                    f"{custom_fee_rate * 100}%."
                ),
            })

        # ========================================================
        # 3. TIMING DIFFERENCE — 61 to 68
        # ========================================================

        elif i <= 68:

            delayed_settlement_date = (
                transaction_time + timedelta(days=9)
            ).strftime("%Y-%m-%d")

            internal_ledger.append({
                "transaction_id": transaction_id,
                "order_id": order_id,
                "invoice_id": invoice_id,
                "transaction_date": transaction_date,
                "amount": str(base_amount),
                "currency": currency,
                "customer_id": customer_id,
                "reference_id": gateway_ref,
            })

            payment_gateway.append({
                "gateway_reference": gateway_ref,
                "order_id": order_id,
                "transaction_date": transaction_date,
                "gross_amount": str(base_amount),
                "fee": str(standard_gateway_fee),
                "net_amount": str(expected_settlement),
                "currency": currency,
                "refund_amount": "0.00",
                "chargeback_amount": "0.00",
            })

            bank_settlement.append({
                "bank_reference": bank_ref,
                "gateway_reference": gateway_ref,
                "settlement_date": delayed_settlement_date,
                "settlement_amount": str(expected_settlement),
                "bank_fee": "0.00",
                "currency": currency,
            })

            ground_truth.append({
                "unified_transaction_id": make_unified_id(
                    transaction_id,
                    gateway_ref,
                    bank_ref,
                ),
                "order_id": order_id,
                "scenario_type": "TIMING_DIFFERENCE",
                "expected_rule_engine_outcome": "EXCEPTION",
                "expected_exception_type": "TIMING_DIFFERENCE",
                "expected_final_status": "UNRESOLVED",
                "notes": (
                    "Settlement delayed beyond the configured "
                    "3-day settlement window."
                ),
            })

        # ========================================================
        # 4. AMOUNT MISMATCH — 69 to 76
        # ========================================================

        elif i <= 76:

            mismatched_amount = quantize_amount(
                expected_settlement - Decimal("150.00")
            )

            internal_ledger.append({
                "transaction_id": transaction_id,
                "order_id": order_id,
                "invoice_id": invoice_id,
                "transaction_date": transaction_date,
                "amount": str(base_amount),
                "currency": currency,
                "customer_id": customer_id,
                "reference_id": gateway_ref,
            })

            payment_gateway.append({
                "gateway_reference": gateway_ref,
                "order_id": order_id,
                "transaction_date": transaction_date,
                "gross_amount": str(base_amount),
                "fee": str(standard_gateway_fee),
                "net_amount": str(expected_settlement),
                "currency": currency,
                "refund_amount": "0.00",
                "chargeback_amount": "0.00",
            })

            bank_settlement.append({
                "bank_reference": bank_ref,
                "gateway_reference": gateway_ref,
                "settlement_date": settlement_date,
                "settlement_amount": str(mismatched_amount),
                "bank_fee": "0.00",
                "currency": currency,
            })

            ground_truth.append({
                "unified_transaction_id": make_unified_id(
                    transaction_id,
                    gateway_ref,
                    bank_ref,
                ),
                "order_id": order_id,
                "scenario_type": "AMOUNT_MISMATCH",
                "expected_rule_engine_outcome": "EXCEPTION",
                "expected_exception_type": "AMOUNT_MISMATCH",
                "expected_final_status": "UNRESOLVED",
                "notes": (
                    "Unexplained INR 150 deduction from the "
                    "expected bank settlement."
                ),
            })

        # ========================================================
        # 5. MISSING RECORD — 77 to 86
        # ========================================================

        elif i <= 86:

            if i <= 82:

                # --------------------------------------------
                # Ledger + Gateway exist.
                # Bank is missing.
                # --------------------------------------------

                internal_ledger.append({
                    "transaction_id": transaction_id,
                    "order_id": order_id,
                    "invoice_id": invoice_id,
                    "transaction_date": transaction_date,
                    "amount": str(base_amount),
                    "currency": currency,
                    "customer_id": customer_id,
                    "reference_id": gateway_ref,
                })

                payment_gateway.append({
                    "gateway_reference": gateway_ref,
                    "order_id": order_id,
                    "transaction_date": transaction_date,
                    "gross_amount": str(base_amount),
                    "fee": str(standard_gateway_fee),
                    "net_amount": str(expected_settlement),
                    "currency": currency,
                    "refund_amount": "0.00",
                    "chargeback_amount": "0.00",
                })

                ground_truth.append({
                    "unified_transaction_id": make_unified_id(
                        transaction_id,
                        gateway_ref,
                    ),
                    "order_id": order_id,
                    "scenario_type": "MISSING_RECORD",
                    "expected_rule_engine_outcome": "EXCEPTION",
                    "expected_exception_type": "MISSING_RECORD",
                    "expected_final_status": "UNRESOLVED",
                    "notes": (
                        "Ledger and gateway records exist, "
                        "but bank settlement is missing."
                    ),
                })

            else:

                # --------------------------------------------
                # Bank exists without Ledger/Gateway.
                # --------------------------------------------

                bank_settlement.append({
                    "bank_reference": bank_ref,
                    "gateway_reference": "",
                    "settlement_date": settlement_date,
                    "settlement_amount": str(expected_settlement),
                    "bank_fee": "0.00",
                    "currency": currency,
                })

                ground_truth.append({
                    "unified_transaction_id": make_bank_only_id(
                        bank_ref
                    ),
                    "order_id": "",
                    "scenario_type": "MISSING_RECORD",
                    "expected_rule_engine_outcome": "EXCEPTION",
                    "expected_exception_type": "MISSING_RECORD",
                    "expected_final_status": "UNRESOLVED",
                    "notes": (
                        "Bank settlement exists without a "
                        "corresponding ledger transaction."
                    ),
                })

        # ========================================================
        # 6. DUPLICATE — 87 to 92
        # ========================================================

        elif i <= 92:

            if i <= 89:

                # --------------------------------------------
                # Duplicate INTERNAL LEDGER records.
                #
                # Ingestion creates:
                #   UNI_TXN_1087_D0_BNK_UTR_5087
                #   UNI_TXN_1087_D1_BNK_UTR_5087
                #
                # The first is the original.
                # The second is the duplicate.
                # --------------------------------------------

                for duplicate_index in range(2):

                    duplicate_transaction_id = (
                        f"{transaction_id}_D{duplicate_index}"
                    )

                    internal_ledger.append({
                        "transaction_id": duplicate_transaction_id,
                        "order_id": order_id,
                        "invoice_id": invoice_id,
                        "transaction_date": transaction_date,
                        "amount": str(base_amount),
                        "currency": currency,
                        "customer_id": customer_id,
                        "reference_id": gateway_ref,
                    })

                payment_gateway.append({
                    "gateway_reference": gateway_ref,
                    "order_id": order_id,
                    "transaction_date": transaction_date,
                    "gross_amount": str(base_amount),
                    "fee": str(standard_gateway_fee),
                    "net_amount": str(expected_settlement),
                    "currency": currency,
                    "refund_amount": "0.00",
                    "chargeback_amount": "0.00",
                })

                bank_settlement.append({
                    "bank_reference": bank_ref,
                    "gateway_reference": gateway_ref,
                    "settlement_date": settlement_date,
                    "settlement_amount": str(expected_settlement),
                    "bank_fee": "0.00",
                    "currency": currency,
                })

                for duplicate_index in range(2):

                    duplicate_transaction_id = (
                        f"{transaction_id}_D{duplicate_index}"
                    )

                    is_duplicate = duplicate_index == 1

                    ground_truth.append({
                        "unified_transaction_id": make_unified_id(
                            duplicate_transaction_id,
                            gateway_ref,
                            bank_ref,
                        ),
                        "order_id": order_id,
                        "scenario_type": "DUPLICATE",
                        "expected_rule_engine_outcome": (
                            "EXCEPTION"
                            if is_duplicate
                            else "MATCHED"
                        ),
                        "expected_exception_type": (
                            "DUPLICATE"
                            if is_duplicate
                            else ""
                        ),
                        "expected_final_status": (
                            "UNRESOLVED"
                            if is_duplicate
                            else "RECONCILED"
                        ),
                        "notes": (
                            "Duplicate ledger pair. First record is "
                            "the original; second record is the "
                            "duplicate detected by the batch rule."
                            if is_duplicate
                            else
                            "Original ledger record in a duplicate pair."
                        ),
                    })

            else:

                # --------------------------------------------
                # Duplicate BANK settlement records.
                #
                # Ingestion creates:
                #   UNI_TXN_1090_BNK_UTR_5090_0
                #   UNI_TXN_1090_BNK_UTR_5090_1
                #
                # The first is the original.
                # The second is the duplicate.
                # --------------------------------------------

                internal_ledger.append({
                    "transaction_id": transaction_id,
                    "order_id": order_id,
                    "invoice_id": invoice_id,
                    "transaction_date": transaction_date,
                    "amount": str(base_amount),
                    "currency": currency,
                    "customer_id": customer_id,
                    "reference_id": gateway_ref,
                })

                payment_gateway.append({
                    "gateway_reference": gateway_ref,
                    "order_id": order_id,
                    "transaction_date": transaction_date,
                    "gross_amount": str(base_amount),
                    "fee": str(standard_gateway_fee),
                    "net_amount": str(expected_settlement),
                    "currency": currency,
                    "refund_amount": "0.00",
                    "chargeback_amount": "0.00",
                })

                for duplicate_index in range(2):

                    duplicate_bank_ref = (
                        f"{bank_ref}_{duplicate_index}"
                    )

                    bank_settlement.append({
                        "bank_reference": duplicate_bank_ref,
                        "gateway_reference": gateway_ref,
                        "settlement_date": settlement_date,
                        "settlement_amount": str(
                            expected_settlement
                        ),
                        "bank_fee": "0.00",
                        "currency": currency,
                    })

                    is_duplicate = duplicate_index == 1

                    ground_truth.append({
                        "unified_transaction_id": make_unified_id(
                            transaction_id,
                            gateway_ref,
                            duplicate_bank_ref,
                        ),
                        "order_id": order_id,
                        "scenario_type": "DUPLICATE",
                        "expected_rule_engine_outcome": (
                            "EXCEPTION"
                            if is_duplicate
                            else "MATCHED"
                        ),
                        "expected_exception_type": (
                            "DUPLICATE"
                            if is_duplicate
                            else ""
                        ),
                        "expected_final_status": (
                            "UNRESOLVED"
                            if is_duplicate
                            else "RECONCILED"
                        ),
                        "notes": (
                            "Duplicate bank settlement pair. First "
                            "record is the original; second is the "
                            "duplicate."
                            if is_duplicate
                            else
                            "Original bank settlement in a duplicate pair."
                        ),
                    })

        # ========================================================
        # 7. REFUND — 93 to 100
        # ========================================================

        elif i <= 100:

            refund_amount = quantize_amount(
                base_amount * Decimal("0.50")
            )

            net_after_refund = quantize_amount(
                expected_settlement - refund_amount
            )

            internal_ledger.append({
                "transaction_id": transaction_id,
                "order_id": order_id,
                "invoice_id": invoice_id,
                "transaction_date": transaction_date,
                "amount": str(base_amount),
                "currency": currency,
                "customer_id": customer_id,
                "reference_id": gateway_ref,
            })

            payment_gateway.append({
                "gateway_reference": gateway_ref,
                "order_id": order_id,
                "transaction_date": transaction_date,
                "gross_amount": str(base_amount),
                "fee": str(standard_gateway_fee),
                "net_amount": str(net_after_refund),
                "currency": currency,
                "refund_amount": str(refund_amount),
                "chargeback_amount": "0.00",
            })

            bank_settlement.append({
                "bank_reference": bank_ref,
                "gateway_reference": gateway_ref,
                "settlement_date": settlement_date,
                "settlement_amount": str(net_after_refund),
                "bank_fee": "0.00",
                "currency": currency,
            })

            ground_truth.append({
                "unified_transaction_id": make_unified_id(
                    transaction_id,
                    gateway_ref,
                    bank_ref,
                ),
                "order_id": order_id,
                "scenario_type": "REFUND",
                "expected_rule_engine_outcome": "EXCEPTION",
                "expected_exception_type": "REFUND",
                "expected_final_status": "UNRESOLVED",
                "notes": (
                    "Partial refund detected in gateway data."
                ),
            })

        # ========================================================
        # 8. CHARGEBACK — 101 to 105
        # ========================================================

        elif i <= 105:

            chargeback_amount = base_amount

            internal_ledger.append({
                "transaction_id": transaction_id,
                "order_id": order_id,
                "invoice_id": invoice_id,
                "transaction_date": transaction_date,
                "amount": str(base_amount),
                "currency": currency,
                "customer_id": customer_id,
                "reference_id": gateway_ref,
            })

            payment_gateway.append({
                "gateway_reference": gateway_ref,
                "order_id": order_id,
                "transaction_date": transaction_date,
                "gross_amount": str(base_amount),
                "fee": str(standard_gateway_fee),
                "net_amount": "0.00",
                "currency": currency,
                "refund_amount": "0.00",
                "chargeback_amount": str(chargeback_amount),
            })

            bank_settlement.append({
                "bank_reference": bank_ref,
                "gateway_reference": gateway_ref,
                "settlement_date": settlement_date,
                "settlement_amount": "0.00",
                "bank_fee": "25.00",
                "currency": currency,
            })

            ground_truth.append({
                "unified_transaction_id": make_unified_id(
                    transaction_id,
                    gateway_ref,
                    bank_ref,
                ),
                "order_id": order_id,
                "scenario_type": "CHARGEBACK",
                "expected_rule_engine_outcome": "EXCEPTION",
                "expected_exception_type": "CHARGEBACK",
                "expected_final_status": "UNRESOLVED",
                "notes": (
                    "Full chargeback detected with bank dispute fee."
                ),
            })

        # ========================================================
        # 9. UNRESOLVED — 106 to 110
        # ========================================================

        else:

            corrupted_bank_amount = quantize_amount(
                Decimal(random.randint(10, 400))
                + Decimal("0.37")
            )

            corrupted_reference = (
                f"corrupt_{random.randint(100, 999)}"
            )

            # --------------------------------------------
            # Ledger side exists.
            # Gateway deliberately omitted.
            # --------------------------------------------

            internal_ledger.append({
                "transaction_id": transaction_id,
                "order_id": order_id,
                "invoice_id": invoice_id,
                "transaction_date": transaction_date,
                "amount": str(base_amount),
                "currency": currency,
                "customer_id": customer_id,
                "reference_id": gateway_ref,
            })

            # --------------------------------------------
            # Bank side exists but has a corrupted reference.
            # --------------------------------------------

            bank_settlement.append({
                "bank_reference": bank_ref,
                "gateway_reference": corrupted_reference,
                "settlement_date": settlement_date,
                "settlement_amount": str(corrupted_bank_amount),
                "bank_fee": "0.00",
                "currency": currency,
            })

            # Ingestion creates TWO normalized transactions:
            #
            # Ledger side:
            #   UNI_TXN_1106
            #
            # Bank side:
            #   UNI_BANK_BNK_UTR_5106
            #
            # Current deterministic engine sees both as
            # missing-record situations.

            ground_truth.append({
                "unified_transaction_id": make_unified_id(
                    transaction_id
                ),
                "order_id": order_id,
                "scenario_type": "UNRESOLVED",
                "expected_rule_engine_outcome": "EXCEPTION",
                "expected_exception_type": "MISSING_RECORD",
                "expected_final_status": "UNRESOLVED",
                "notes": (
                    "Ledger transaction has no matching gateway "
                    "or bank settlement."
                ),
            })

            ground_truth.append({
                "unified_transaction_id": make_bank_only_id(
                    bank_ref
                ),
                "order_id": "",
                "scenario_type": "UNRESOLVED",
                "expected_rule_engine_outcome": "EXCEPTION",
                "expected_exception_type": "MISSING_RECORD",
                "expected_final_status": "UNRESOLVED",
                "notes": (
                    "Bank settlement has a corrupted gateway "
                    "reference and no matching ledger record."
                ),
            })

    # ============================================================
    # CSV WRITER
    # ============================================================

    def write_csv(
        filepath: str,
        data: list[dict],
        fieldnames: list[str],
    ) -> None:

        with open(
            filepath,
            mode="w",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
            )

            writer.writeheader()
            writer.writerows(data)

    # ============================================================
    # WRITE RAW SOURCE FILES
    # ============================================================

    write_csv(
        os.path.join(
            raw_dir,
            "internal_ledger.csv",
        ),
        internal_ledger,
        [
            "transaction_id",
            "order_id",
            "invoice_id",
            "transaction_date",
            "amount",
            "currency",
            "customer_id",
            "reference_id",
        ],
    )

    write_csv(
        os.path.join(
            raw_dir,
            "payment_gateway.csv",
        ),
        payment_gateway,
        [
            "gateway_reference",
            "order_id",
            "transaction_date",
            "gross_amount",
            "fee",
            "net_amount",
            "currency",
            "refund_amount",
            "chargeback_amount",
        ],
    )

    write_csv(
        os.path.join(
            raw_dir,
            "bank_settlement.csv",
        ),
        bank_settlement,
        [
            "bank_reference",
            "gateway_reference",
            "settlement_date",
            "settlement_amount",
            "bank_fee",
            "currency",
        ],
    )

    # ============================================================
    # WRITE GROUND TRUTH
    # ============================================================

    write_csv(
        os.path.join(
            processed_dir,
            "ground_truth.csv",
        ),
        ground_truth,
        [
            "unified_transaction_id",
            "order_id",
            "scenario_type",
            "expected_rule_engine_outcome",
            "expected_exception_type",
            "expected_final_status",
            "notes",
        ],
    )

    # ============================================================
    # VALIDATION
    # ============================================================

    print("\nSynthetic reconciliation dataset generated successfully.")
    print("-" * 50)
    print(f"Business scenarios      : 110")
    print(f"Ground truth records    : {len(ground_truth)}")
    print(f"Ledger records          : {len(internal_ledger)}")
    print(f"Gateway records         : {len(payment_gateway)}")
    print(f"Bank records            : {len(bank_settlement)}")
    print("-" * 50)

    if len(ground_truth) == 121:
        print("Ground truth validation : PASS")
    else:
        print(
            f"Ground truth validation : WARNING "
            f"(expected 121, got {len(ground_truth)})"
        )


if __name__ == "__main__":
    generate_synthetic_reconciliation_data()