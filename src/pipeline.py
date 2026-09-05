from ingestion import ingest_and_normalize
from rule_engine import evaluate_transactions
from llm_agent import analyze_exception
from decision_engine import make_decision
from model import (
    ReconciliationResult,
    FinalStatus,
    ExceptionType,
)


def run_reconciliation_pipeline(
    ledger_path="data/raw/internal_ledger.csv",
    bank_path="data/raw/bank_settlement.csv",
    gateway_path="data/raw/payment_gateway.csv",
):

    # 1. Ingestion + normalization
    transactions = ingest_and_normalize(
        ledger_path,
        bank_path,
        gateway_path,
    )

    # 2. Deterministic rule engine
    rule_results = evaluate_transactions(transactions)

    final_results = []
    llm_calls = 0

    # 3. LLM + Decision Engine
    for transaction, rule_result in zip(
        transactions,
        rule_results,
    ):

        # Clean transaction
        if rule_result.final_status == FinalStatus.RECONCILED:
            final_results.append(rule_result)
            continue

        try:
            exception_type = ExceptionType(
                rule_result.exception_type
            )

            llm_analysis = analyze_exception(
                transaction,
                exception_type,
            )

            llm_calls += 1

            final_status = make_decision(
                rule_result,
                llm_analysis,
            )

            final_results.append(
                ReconciliationResult(
                    unified_transaction_id=(
                        rule_result.unified_transaction_id
                    ),
                    final_status=final_status,
                    exception_type=(
                        llm_analysis.exception_type.value
                    ),
                    difference=rule_result.difference,
                    resolution=llm_analysis.resolution,
                    confidence_score=(
                        llm_analysis.confidence_score
                    ),
                    ai_explanation=llm_analysis.explanation,
                    recommended_action=(
                        llm_analysis.recommended_action
                    ),
                    requires_human_review=(
                        llm_analysis.requires_human_review
                    ),
                )
            )

        except Exception as error:

            # Gemini unavailable/quota exhausted:
            # preserve the transaction and rule result.
            final_results.append(
                rule_result.model_copy(
                    update={
                        "final_status": FinalStatus.UNRESOLVED,
                        "requires_human_review": True,
                        "ai_explanation": (
                            "AI analysis unavailable. "
                            "Manual review required."
                        ),
                        "recommended_action": (
                            "Review the reconciliation exception manually."
                        ),
                    }
                )
            )

            print(
                f"LLM unavailable for "
                f"{rule_result.unified_transaction_id}: {error}"
            )

    print(f"Transactions processed: {len(transactions)}")
    print(f"LLM calls completed: {llm_calls}")

    return final_results


if __name__ == "__main__":

    results = run_reconciliation_pipeline()

    print("=" * 60)
    print("AI FINANCE CONTROLLER PIPELINE")
    print("=" * 60)

    print(f"Results: {len(results)}")

    print("\nFIRST 10 RESULTS")
    print("-" * 60)

    for result in results[:10]:
        print(
            result.unified_transaction_id,
            "→",
            result.final_status.value,
        )