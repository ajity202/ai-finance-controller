"""
Source schemas: one Pydantic model per raw data source.

IMPORTANT: these models intentionally do NOT contain a `status` field.
Status is a system-generated result that only exists after reconciliation
(see UnifiedTransaction / FinalStatus). A source record is just a fact
as reported by that system.
"""

from datetime import date
from decimal import Decimal
from typing import Optional
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, computed_field

class Currency(str, Enum):
    INR = "INR"
    USD = "USD"

class BankTransactionType(str, Enum):
    SETTLEMENT = "SETTLEMENT"
    REFUND = "REFUND"
    CHARGEBACK = "CHARGEBACK"



class InternalLedgerRecord(BaseModel):
    """A single row from the company's internal ledger/accounting system."""

    model_config = ConfigDict(frozen=True)

    transaction_id: str
    order_id: str
    invoice_id: Optional[str] = None
    transaction_date: date
    amount: Decimal = Field(..., description="Amount recorded internally, as booked.")
    currency: Currency = Currency.INR
    customer_id: Optional[str] = None
    reference_id: Optional[str] = Field(
        default=None,
        description="Free-text reference the ledger stores back to the gateway, if any.",
    )


class PaymentGatewayRecord(BaseModel):
    """A single transaction record from the payment gateway (e.g. Razorpay)."""

    model_config = ConfigDict(frozen=True)

    gateway_reference: str
    order_id: str
    transaction_date: date
    gross_amount: Decimal = Field(..., description="Amount charged to the customer.")
    fee: Decimal = Field(default=Decimal("0"), description="Gateway processing fee.")
    net_amount: Decimal = Field(
        ..., description="gross_amount - fee (+/- refunds/chargebacks), as reported by gateway."
    )
    currency: Currency = Currency.INR
    refund_amount: Decimal = Field(default=Decimal("0"))
    chargeback_amount: Decimal = Field(default=Decimal("0"))


class BankSettlementRecord(BaseModel):
    """A single settlement line from the bank statement."""

    model_config = ConfigDict(frozen=True)

    bank_reference: str
    gateway_reference: Optional[str] = None
    settlement_date: date
    settlement_amount: Decimal = Field(
        ..., description="Amount actually credited by the bank."
    )
    bank_fee: Decimal = Field(default=Decimal("0"))
    currency: Currency = Currency.INR
    transaction_type: BankTransactionType = BankTransactionType.SETTLEMENT

"""
UnifiedTransaction: the canonical, normalized representation of one
economic transaction after ingestion + normalization, before any
reconciliation decision has been made.

Join strategy (see docs/reconciliation-flow.md):
    Internal Ledger  --(order_id)-->  Payment Gateway  --(gateway_reference)-->  Bank Settlement

A transaction may legitimately be missing one or two sources (e.g. the
bank hasn't settled yet, or the gateway record can't be found) — those
are exactly the cases the Rule Engine needs to detect, so all three
source blocks are Optional here.

This model intentionally carries NO status/outcome field. Status is
produced downstream by the Rule Engine / LLM Agent / Decision Engine.
"""


class UnifiedTransaction(BaseModel):
    model_config = ConfigDict(frozen=False)

    # --- Identity -----------------------------------------------------
    unified_transaction_id: str = Field(
        ..., description="Stable synthetic key generated during normalization (see ingestion)."
    )
    order_id: Optional[str]= Field(
        default=None,
        description="Common order identifier when available.",
    )

    customer_id: Optional[str] = None
    currency: Currency = Currency.INR

    # --- Raw source records (nullable: a source may be missing) -------
    internal_ledger: Optional[InternalLedgerRecord] = None
    gateway: Optional[PaymentGatewayRecord] = None
    bank: Optional[BankSettlementRecord] = None

    # --- Convenience accessors -----------------------------------------
    # These are thin computed views over the nested source records so the
    # Rule Engine and LLM prompt builder don't need to null-check nested
    # objects everywhere. They are derived, not authoritative.

    @computed_field  # type: ignore[misc]
    @property
    def has_ledger_record(self) -> bool:
        return self.internal_ledger is not None

    @computed_field  # type: ignore[misc]
    @property
    def has_gateway_record(self) -> bool:
        return self.gateway is not None

    @computed_field  # type: ignore[misc]
    @property
    def has_bank_record(self) -> bool:
        return self.bank is not None

    @computed_field  # type: ignore[misc]
    @property
    def ledger_amount(self) -> Optional[Decimal]:
        return self.internal_ledger.amount if self.internal_ledger else None

    @computed_field  # type: ignore[misc]
    @property
    def ledger_transaction_date(self) -> Optional[date]:
        return self.internal_ledger.transaction_date if self.internal_ledger else None

    @computed_field  # type: ignore[misc]
    @property
    def gateway_reference(self) -> Optional[str]:
        return self.gateway.gateway_reference if self.gateway else None

    @computed_field  # type: ignore[misc]
    @property
    def gateway_gross_amount(self) -> Optional[Decimal]:
        return self.gateway.gross_amount if self.gateway else None

    @computed_field  # type: ignore[misc]
    @property
    def gateway_fee(self) -> Optional[Decimal]:
        return self.gateway.fee if self.gateway else None

    @computed_field  # type: ignore[misc]
    @property
    def gateway_net_amount(self) -> Optional[Decimal]:
        return self.gateway.net_amount if self.gateway else None

    @computed_field  # type: ignore[misc]
    @property
    def gateway_refund_amount(self) -> Optional[Decimal]:
        return self.gateway.refund_amount if self.gateway else None

    @computed_field  # type: ignore[misc]
    @property
    def gateway_chargeback_amount(self) -> Optional[Decimal]:
        return self.gateway.chargeback_amount if self.gateway else None

    @computed_field  # type: ignore[misc]
    @property
    def gateway_transaction_date(self) -> Optional[date]:
        return self.gateway.transaction_date if self.gateway else None

    @computed_field  # type: ignore[misc]
    @property
    def bank_reference(self) -> Optional[str]:
        return self.bank.bank_reference if self.bank else None

    @computed_field  # type: ignore[misc]
    @property
    def bank_settlement_amount(self) -> Optional[Decimal]:
        return self.bank.settlement_amount if self.bank else None

    @computed_field  # type: ignore[misc]
    @property
    def bank_fee(self) -> Optional[Decimal]:
        return self.bank.bank_fee if self.bank else None

    @computed_field  # type: ignore[misc]
    @property
    def bank_settlement_date(self) -> Optional[date]:
        return self.bank.settlement_date if self.bank else None

    def source_summary(self) -> str:
        """Short human-readable summary, useful for logs and LLM prompts."""
        parts = []
        parts.append("ledger" if self.has_ledger_record else "NO-ledger")
        parts.append("gateway" if self.has_gateway_record else "NO-gateway")
        parts.append("bank" if self.has_bank_record else "NO-bank")
        return "+".join(parts)


class FinalStatus(str, Enum):
    RECONCILED = "RECONCILED"
    RESOLVED = "RESOLVED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    UNRESOLVED = "UNRESOLVED"


class ReconciliationResult(BaseModel):
    """
    Final result produced by the reconciliation pipeline.
    """

    model_config = ConfigDict(frozen=False)

    unified_transaction_id: str
    final_status: FinalStatus

    exception_type: Optional[str] = None
    difference: Optional[Decimal] = None
    resolution: Optional[str] = None

    confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    ai_explanation: Optional[str] = None
    recommended_action: Optional[str] = None
    requires_human_review: bool = False

# ============================================================
# GROUND TRUTH / EVALUATION MODELS
# ============================================================


class ScenarioType(str, Enum):
    """Synthetic reconciliation scenario used to test the system."""

    CLEAN_MATCH = "CLEAN_MATCH"
    FEE_DIFFERENCE = "FEE_DIFFERENCE"
    TIMING_DIFFERENCE = "TIMING_DIFFERENCE"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    MISSING_RECORD = "MISSING_RECORD"
    DUPLICATE = "DUPLICATE"
    REFUND = "REFUND"
    CHARGEBACK = "CHARGEBACK"
    UNRESOLVED = "UNRESOLVED"


class RuleEngineOutcome(str, Enum):
    """Expected classification produced by the deterministic Rule Engine."""

    MATCHED = "MATCHED"
    EXCEPTION = "EXCEPTION"


class ExceptionType(str, Enum):
    """Types of reconciliation exceptions."""

    FEE_DIFFERENCE = "FEE_DIFFERENCE"
    TIMING_DIFFERENCE = "TIMING_DIFFERENCE"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    MISSING_RECORD = "MISSING_RECORD"
    DUPLICATE = "DUPLICATE"
    REFUND = "REFUND"
    CHARGEBACK = "CHARGEBACK"
    UNKNOWN = "UNKNOWN"


class GroundTruthRecord(BaseModel):
    """
    Ground-truth record for evaluating the reconciliation system.

    Ground truth represents the known correct outcome of a synthetic
    transaction. It is NOT generated by the Rule Engine or LLM.

    IMPORTANT:
    NEEDS_REVIEW is intentionally NOT used as a ground-truth label.
    It is a confidence/decision state produced by the system.
    """

    model_config = ConfigDict(frozen=True)

    unified_transaction_id: str

    order_id: str

    scenario_type: ScenarioType

    expected_rule_engine_outcome: RuleEngineOutcome

    expected_exception_type: Optional[ExceptionType] = None

    expected_final_status: FinalStatus

    notes: str = ""