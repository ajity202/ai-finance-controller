import pandas as pd

from ingestion import ingest_and_normalize
from pipeline import run_reconciliation_pipeline


LEDGER = "data/external/internal_ledger_external_test_v2.csv"
BANK = "data/external/bank_statement_external_test_v2.csv"
GT = "data/external/external_test_ground_truth.csv"


def main():

    print("\n" + "=" * 60)
    print("AI PIPELINE EVALUATION - EXTERNAL V2")
    print("=" * 60)

    # ---------------------------------------------------------
    # Load Ground Truth
    # ---------------------------------------------------------

    gt = pd.read_csv(GT)

    # ---------------------------------------------------------
    # Normalize external dataset
    # ---------------------------------------------------------

    transactions = ingest_and_normalize(
        ledger_path=LEDGER,
        bank_path=BANK,
        gateway_path=None,
    )

    print(f"Normalized transactions : {len(transactions)}")
    print(f"Ground truth orders     : {len(gt)}")

    # ---------------------------------------------------------
    # Run complete AI pipeline
    # ---------------------------------------------------------

    results = run_reconciliation_pipeline(
        ledger_path=LEDGER,
        bank_path=BANK,
        gateway_path=None,
    )

    print(f"Pipeline results        : {len(results)}")

    # ---------------------------------------------------------
    # Attach order_id to results
    # ---------------------------------------------------------

    rows = []

    for transaction, result in zip(transactions, results):

        rows.append({
            "order_id": transaction.order_id,
            "unified_transaction_id":
                result.unified_transaction_id,
            "final_status":
                result.final_status.value,
            "exception_type":
                result.exception_type,
            "confidence_score":
                result.confidence_score,
        })

    actual = pd.DataFrame(rows)

    # Remove records that cannot be linked to an economic order
    actual = actual[
        actual["order_id"].notna()
    ].copy()

    # ---------------------------------------------------------
    # Aggregate multiple records belonging to same order
    # ---------------------------------------------------------

    status_priority = {
        "NEEDS_REVIEW": 4,
        "UNRESOLVED": 3,
        "RESOLVED": 2,
        "RECONCILED": 1,
    }

    exception_priority = {
        "CHARGEBACK": 7,
        "REFUND": 6,
        "AMOUNT_MISMATCH": 5,
        "FEE_DIFFERENCE": 4,
        "TIMING_DIFFERENCE": 3,
        "DUPLICATE": 2,
        "MISSING_RECORD": 1,
    }

    def aggregate_order(group):

        statuses = group["final_status"].tolist()

        final_status = max(
            statuses,
            key=lambda x: status_priority.get(x, 0),
        )

        exceptions = [
            x for x in group["exception_type"].tolist()
            if pd.notna(x) and str(x).strip()
        ]

        exception_type = (
            max(
                exceptions,
                key=lambda x:
                    exception_priority.get(x, 0),
            )
            if exceptions
            else None
        )

        return pd.Series({
            "predicted_final_status": final_status,
            "predicted_exception_type": exception_type,
        })

    actual_orders = (
        actual
        .groupby("order_id")
        .apply(
            aggregate_order,
            include_groups=False,
        )
        .reset_index()
    )

    # ---------------------------------------------------------
    # Merge with Ground Truth
    # ---------------------------------------------------------

    merged = gt.merge(
        actual_orders,
        on="order_id",
        how="left",
    )

    print(f"Matched GT orders      : "
          f"{merged['predicted_final_status'].notna().sum()}")

    # ---------------------------------------------------------
    # FINAL STATUS ACCURACY
    # ---------------------------------------------------------

    merged["status_correct"] = (
        merged["expected_final_status"]
        == merged["predicted_final_status"]
    )

    status_accuracy = (
        merged["status_correct"].mean() * 100
    )

    # ---------------------------------------------------------
    # EXCEPTION TYPE ACCURACY
    # ---------------------------------------------------------

    exception_rows = merged[
        merged["expected_exception_type"].notna()
        & (
            merged["expected_exception_type"]
            .astype(str)
            .str.strip()
            != ""
        )
        & merged["predicted_exception_type"].notna()
    ]

    exception_accuracy = (
        (
            exception_rows["expected_exception_type"]
            == exception_rows["predicted_exception_type"]
        ).mean() * 100
        if len(exception_rows)
        else 0
    )

    # ---------------------------------------------------------
    # RULE OUTCOME ACCURACY
    # ---------------------------------------------------------

    merged["predicted_rule_outcome"] = (
        merged["predicted_final_status"]
        .apply(
            lambda x:
                "MATCHED"
                if x == "RECONCILED"
                else "EXCEPTION"
        )
    )

    merged["rule_correct"] = (
        merged["expected_rule_engine_outcome"]
        == merged["predicted_rule_outcome"]
    )

    rule_accuracy = (
        merged["rule_correct"].mean() * 100
    )

    # ---------------------------------------------------------
    # RESULTS
    # ---------------------------------------------------------

    print("\n" + "-" * 60)

    print(
        f"Final Status Accuracy   : "
        f"{status_accuracy:.2f}%"
    )

    print(
        f"Exception Type Accuracy : "
        f"{exception_accuracy:.2f}%"
    )

    print(
        f"Rule Outcome Accuracy   : "
        f"{rule_accuracy:.2f}%"
    )

    print()

    print(
        "Correct Final Statuses  :",
        merged["status_correct"].sum(),
        "/",
        len(merged),
    )

    print(
        "Correct Exception Types :",
        (
            exception_rows[
                "expected_exception_type"
            ]
            == exception_rows[
                "predicted_exception_type"
            ]
        ).sum(),
        "/",
        len(exception_rows),
    )

    print(
        "Correct Rule Outcomes   :",
        merged["rule_correct"].sum(),
        "/",
        len(merged),
    )

    # ---------------------------------------------------------
    # STATUS BREAKDOWN
    # ---------------------------------------------------------

    print("\nFINAL STATUS BREAKDOWN")
    print("-" * 60)

    for status in [
        "RECONCILED",
        "RESOLVED",
        "NEEDS_REVIEW",
        "UNRESOLVED",
    ]:

        expected = (
            merged["expected_final_status"]
            == status
        ).sum()

        predicted = (
            merged["predicted_final_status"]
            == status
        ).sum()

        print(
            f"{status:<15}"
            f"GT: {expected:<4}"
            f"Predicted: {predicted:<4}"
        )

    # ---------------------------------------------------------
    # SAVE
    # ---------------------------------------------------------

    output = "data/processed/ai_pipeline_evaluation.csv"

    merged.to_csv(
        output,
        index=False,
    )

    print("\nSaved:", output)


if __name__ == "__main__":
    main()