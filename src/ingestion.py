"""
Data ingestion and normalization layer.

Responsibilities:
1. Load raw CSV files.
2. Validate records using Pydantic models.
3. Preserve missing/duplicate source records.
4. Normalize source records into UnifiedTransaction objects.

Mandatory sources:
- Internal Ledger
- Bank Settlement

Optional source:
- Payment Gateway
"""

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional

import pandas as pd

from model import (
    BankSettlementRecord,
    InternalLedgerRecord,
    PaymentGatewayRecord,
    UnifiedTransaction,
)


# ============================================================
# HELPERS
# ============================================================


def parse_decimal(value: str, field_name: str) -> Decimal:
    """Safely convert a CSV value into Decimal."""

    if value is None or not value.strip():
        return Decimal("0.00")

    try:
        return Decimal(value.strip())
    except InvalidOperation as exc:
        raise ValueError(
            f"Invalid decimal value '{value}' "
            f"for field '{field_name}'."
        ) from exc


def normalize_optional(value: Optional[str]) -> Optional[str]:
    """Convert empty CSV strings into None."""

    if value is None:
        return None

    value = value.strip()

    return value if value else None


def parse_date(value: str):
    """
    Parse dates from different source-system formats.

    Supported formats:
    - YYYY-MM-DD
    - DD-MM-YYYY
    - DD/MM/YYYY
    - YYYY/MM/DD
    """

    if value is None or not str(value).strip():
        raise ValueError("Date value cannot be empty.")

    value = str(value).strip()

    supported_formats = (
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    )

    for date_format in supported_formats:
        try:
            return pd.to_datetime(
                value,
                format=date_format,
            ).date()
        except ValueError:
            continue

    raise ValueError(
        f"Unsupported date format: '{value}'. "
        f"Supported formats: YYYY-MM-DD, DD-MM-YYYY, "
        f"DD/MM/YYYY, YYYY/MM/DD."
    )


def read_csv(filepath: str) -> List[dict]:
    """Read a CSV file and return rows as dictionaries."""

    path = Path(filepath)

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {filepath}"
        )

    with path.open(
        mode="r",
        newline="",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError(
                f"CSV file has no header: {filepath}"
            )

        return list(reader)


# ============================================================
# SOURCE LOADERS
# ============================================================


def load_internal_ledger(
    filepath: str,
) -> List[InternalLedgerRecord]:
    """Load and validate Internal Ledger records."""

    rows = read_csv(filepath)
    records = []

    for row in rows:

        records.append(
            InternalLedgerRecord(
                transaction_id=row["transaction_id"],
                order_id=row["order_id"],
                invoice_id=normalize_optional(
                    row.get("invoice_id")
                ),
                transaction_date=row["transaction_date"],
                amount=parse_decimal(
                    row["amount"],
                    "amount",
                ),
                currency=row["currency"],
                customer_id=normalize_optional(
                    row.get("customer_id")
                ),
                reference_id=normalize_optional(
                    row.get("reference_id")
                ),
            )
        )

    return records


def load_payment_gateway(
    filepath: Optional[str],
) -> List[PaymentGatewayRecord]:
    """
    Load and validate Payment Gateway records.

    Payment Gateway is optional.
    """

    if not filepath:
        return []

    path = Path(filepath)

    if not path.exists():
        return []

    rows = read_csv(filepath)
    records = []

    for row in rows:

        records.append(
            PaymentGatewayRecord(
                gateway_reference=row["gateway_reference"],
                order_id=row["order_id"],
                transaction_date=row["transaction_date"],
                gross_amount=parse_decimal(
                    row["gross_amount"],
                    "gross_amount",
                ),
                fee=parse_decimal(
                    row["fee"],
                    "fee",
                ),
                net_amount=parse_decimal(
                    row["net_amount"],
                    "net_amount",
                ),
                currency=row["currency"],
                refund_amount=parse_decimal(
                    row["refund_amount"],
                    "refund_amount",
                ),
                chargeback_amount=parse_decimal(
                    row["chargeback_amount"],
                    "chargeback_amount",
                ),
            )
        )

    return records


def load_bank_settlement(
    filepath: str,
) -> List[BankSettlementRecord]:
    """Load and validate Bank Settlement records."""

    rows = read_csv(filepath)
    records = []

    for row in rows:

        records.append(
            BankSettlementRecord(
                bank_reference=row["bank_reference"],

                gateway_reference=normalize_optional(
                    row.get("gateway_reference")
                ),

                settlement_date=parse_date(
                    row["settlement_date"]
                ),

                settlement_amount=parse_decimal(
                    row["settlement_amount"],
                    "settlement_amount",
                ),

                bank_fee=parse_decimal(
                    row["bank_fee"],
                    "bank_fee",
                ),

                currency=row["currency"],

                transaction_type=(
                    row.get(
                        "transaction_type",
                        "SETTLEMENT",
                    )
                    .strip()
                    .upper()
                ),
            )
        )

    return records


# ============================================================
# NORMALIZATION
# ============================================================


def ingest_and_normalize(
    ledger_path: str,
    bank_path: str,
    gateway_path: Optional[str] = None,
) -> List[UnifiedTransaction]:
    """
    Normalize Ledger, Bank and optional Gateway data.

    Matching priority:

    WITH GATEWAY:
        Ledger.order_id
            -> Gateway.order_id

        Gateway.gateway_reference
            -> Bank.gateway_reference

    WITHOUT GATEWAY:
        Ledger.reference_id
            -> Bank.gateway_reference

    Each bank source record is consumed at most once.

    Unmatched records are preserved.
    """

    ledgers = load_internal_ledger(ledger_path)
    banks = load_bank_settlement(bank_path)
    gateways = load_payment_gateway(gateway_path)

    unified_transactions = []

    # --------------------------------------------------------
    # Gateway indexes
    # --------------------------------------------------------

    gateway_by_order = {}

    for gateway in gateways:
        gateway_by_order.setdefault(
            gateway.order_id,
            [],
        ).append(gateway)

    gateway_by_reference = {
        gateway.gateway_reference: gateway
        for gateway in gateways
    }

    # --------------------------------------------------------
    # Bank indexes
    # --------------------------------------------------------

    bank_by_reference = {}

    for bank in banks:

        if bank.gateway_reference:

            bank_by_reference.setdefault(
                bank.gateway_reference,
                [],
            ).append(bank)

    processed_bank_refs = set()

    # ========================================================
    # PROCESS LEDGER RECORDS
    # ========================================================

    for ledger in ledgers:

        # ----------------------------------------------------
        # CASE 1 — Gateway available
        # ----------------------------------------------------

        matching_gateways = gateway_by_order.get(
            ledger.order_id,
            [],
        )

        if matching_gateways:

            for gateway in matching_gateways:

                # IMPORTANT:
                # Gateway -> Bank matching uses
                # gateway.gateway_reference
                matching_banks = bank_by_reference.get(
                    gateway.gateway_reference,
                    [],
                )

                bank = next(
                    (
                        b
                        for b in matching_banks
                        if b.bank_reference
                        not in processed_bank_refs
                    ),
                    None,
                )

                if bank:

                    processed_bank_refs.add(
                        bank.bank_reference
                    )

                unified_transactions.append(
                    UnifiedTransaction(
                        unified_transaction_id=(
                            f"UT-{ledger.order_id}-"
                            f"{ledger.transaction_id}"
                        ),
                        order_id=ledger.order_id,
                        customer_id=ledger.customer_id,
                        currency=ledger.currency,
                        internal_ledger=ledger,
                        gateway=gateway,
                        bank=bank,
                    )
                )

            continue

        # ----------------------------------------------------
        # CASE 2 — No Gateway
        #
        # Direct Ledger -> Bank matching
        # Ledger.reference_id -> Bank.gateway_reference
        # ----------------------------------------------------

        matching_banks = (
            bank_by_reference.get(
                ledger.reference_id,
                [],
            )
            if ledger.reference_id
            else []
        )

        bank = next(
            (
                b
                for b in matching_banks
                if b.bank_reference
                not in processed_bank_refs
            ),
            None,
        )

        if bank:

            processed_bank_refs.add(
                bank.bank_reference
            )

        unified_transactions.append(
            UnifiedTransaction(
                unified_transaction_id=(
                    f"UT-{ledger.order_id}-"
                    f"{ledger.transaction_id}"
                ),
                order_id=ledger.order_id,
                customer_id=ledger.customer_id,
                currency=ledger.currency,
                internal_ledger=ledger,
                gateway=None,
                bank=bank,
            )
        )

    # ========================================================
    # UNMATCHED BANK RECORDS
    # ========================================================

    for bank in banks:

        if bank.bank_reference in processed_bank_refs:
            continue

        gateway = (
            gateway_by_reference.get(
                bank.gateway_reference
            )
            if bank.gateway_reference
            else None
        )

        unified_transactions.append(
            UnifiedTransaction(
                unified_transaction_id=(
                    f"UT-BANK-{bank.bank_reference}"
                ),
                order_id=(
                    bank.gateway_reference
                    if bank.gateway_reference
                    else None
                ),
                customer_id=None,
                currency=bank.currency,
                internal_ledger=None,
                gateway=gateway,
                bank=bank,
            )
        )

    return unified_transactions


# ============================================================
# LOCAL TEST
# ============================================================


if __name__ == "__main__":

    try:

        transactions = ingest_and_normalize(
            ledger_path="data/raw/internal_ledger.csv",
            bank_path="data/raw/bank_settlement.csv",
            gateway_path="data/raw/payment_gateway.csv",
        )

        print(
            f"Successfully normalized "
            f"{len(transactions)} transactions."
        )

        for transaction in transactions[:5]:

            print(
                transaction.unified_transaction_id,
                "|",
                transaction.source_summary(),
            )

    except Exception as error:

        print(
            f"Ingestion failed: {error}"
        )