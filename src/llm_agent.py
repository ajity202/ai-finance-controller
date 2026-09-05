"""
LLM Exception Resolution Agent

The LLM receives only reconciliation exceptions and
analyzes the available financial evidence.

The LLM does NOT perform blind reconciliation.
It must rely only on supplied evidence.
"""

import os
import time
from typing import Optional

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

from model import (
    UnifiedTransaction,
    ExceptionType,
)


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        ".env",
    )
)

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not configured in .env"
    )

client = genai.Client(api_key=API_KEY)

MODEL_NAME = "gemini-3.1-flash-lite"


# ============================================================
# STRUCTURED LLM RESPONSE
# ============================================================

class LLMExceptionAnalysis(BaseModel):
    exception_type: ExceptionType = Field(
        description="Most likely exception type based only on evidence."
    )

    explanation: str = Field(
        description="Clear explanation of why the exception occurred."
    )

    evidence: list[str] = Field(
        description="Specific facts from the supplied transaction evidence."
    )

    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence from 0 to 1."
    )

    recommended_action: str = Field(
        description="Recommended next action for finance operations."
    )

    resolution: Optional[str] = Field(
        default=None,
        description="Proposed resolution if sufficient evidence exists."
    )

    requires_human_review: bool = Field(
        description="Whether a human should review the exception."
    )


# ============================================================
# EVIDENCE BUILDER
# ============================================================

def build_transaction_evidence(
    transaction: UnifiedTransaction,
) -> str:
    """
    Convert normalized transaction data into explicit evidence.

    Only facts available in the source records are included.
    """

    evidence = {
        "unified_transaction_id":
            transaction.unified_transaction_id,

        "order_id":
            transaction.order_id,

        "currency":
            transaction.currency.value,

        "ledger": None,
        "gateway": None,
        "bank": None,
    }

    # --------------------------------------------------------
    # Ledger
    # --------------------------------------------------------

    if transaction.internal_ledger:

        ledger = transaction.internal_ledger

        evidence["ledger"] = {
            "transaction_id":
                ledger.transaction_id,

            "order_id":
                ledger.order_id,

            "transaction_date":
                str(ledger.transaction_date),

            "amount":
                str(ledger.amount),

            "currency":
                ledger.currency.value,

            "reference_id":
                ledger.reference_id,
        }

    # --------------------------------------------------------
    # Gateway
    # --------------------------------------------------------

    if transaction.gateway:

        gateway = transaction.gateway

        evidence["gateway"] = {
            "gateway_reference":
                gateway.gateway_reference,

            "order_id":
                gateway.order_id,

            "transaction_date":
                str(gateway.transaction_date),

            "gross_amount":
                str(gateway.gross_amount),

            "fee":
                str(gateway.fee),

            "net_amount":
                str(gateway.net_amount),

            "refund_amount":
                str(gateway.refund_amount),

            "chargeback_amount":
                str(gateway.chargeback_amount),

            "currency":
                gateway.currency.value,
        }

    # --------------------------------------------------------
    # Bank
    # --------------------------------------------------------

    if transaction.bank:

        bank = transaction.bank

        evidence["bank"] = {
            "bank_reference":
                bank.bank_reference,

            "gateway_reference":
                bank.gateway_reference,

            "settlement_date":
                str(bank.settlement_date),

            "settlement_amount":
                str(bank.settlement_amount),

            "bank_fee":
                str(bank.bank_fee),

            "transaction_type":
                bank.transaction_type.value,

            "currency":
                bank.currency.value,
        }

    return str(evidence)


# ============================================================
# LLM ANALYSIS
# ============================================================
REQUEST_DELAY_SECONDS = 8
MAX_RETRIES = 1


def call_gemini_with_retry(prompt: str):
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(REQUEST_DELAY_SECONDS)

            return client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": LLMExceptionAnalysis,
                },
            )

        except Exception as error:
            error_text = str(error)

            if "429" not in error_text and "503" not in error_text:
                raise

            if attempt == MAX_RETRIES - 1:
                raise

            wait_time = 5
            print(
                f"Gemini rate/quota limit reached. "
                f"Retrying in {wait_time}s..."
            )
            time.sleep(wait_time)

def analyze_exception(
    transaction: UnifiedTransaction,
    exception_type: ExceptionType,
) -> LLMExceptionAnalysis:
    """
    Analyze a single reconciliation exception.
    """

    evidence = build_transaction_evidence(
        transaction
    )

    prompt = f"""
You are an AI Finance Controller exception-resolution agent.

Your job is to ANALYZE the exception, not invent or modify financial records.

STRICT RULES:
- Use ONLY the evidence provided below.
- Never invent, assume, or infer an exact amount, date, fee, reference,
  transaction, refund, chargeback, or business policy.
- Never propose a corrected value unless that exact value is explicitly
  supported by the evidence.
- If the correct value cannot be determined, state:
  "The available evidence is insufficient to determine the correct value."
- Distinguish clearly between FACTS and POSSIBLE EXPLANATIONS.
- The deterministic rule engine classification is a starting point;
  you may confirm or challenge it based on the evidence.
- If evidence is contradictory or insufficient, set
  requires_human_review=true.
- A high confidence score is allowed ONLY when the evidence strongly
  supports the conclusion.

DETERMINISTIC CLASSIFICATION:
{exception_type}

TASK:
1. Validate or challenge the exception classification.
2. Explain the discrepancy using factual evidence.
3. List the strongest evidence.
4. Identify the likely cause ONLY if supported by evidence.
5. Recommend an operational next step.
6. Provide a resolution ONLY when the evidence supports a specific resolution.
7. Otherwise set resolution=null and recommend human review.

IMPORTANT:
Do not correct dates, amounts, fees, or records yourself.
The AI recommends actions; it does not alter financial records.

TRANSACTION EVIDENCE:
{evidence}
"""

    response = call_gemini_with_retry(prompt)

    return LLMExceptionAnalysis.model_validate_json(
        response.text
    )


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("LLM EXCEPTION AGENT")
    print("=" * 60)

    print(
        "\nLLM agent configured successfully."
    )

    print(
        f"Model: {MODEL_NAME}"
    )