from collections import defaultdict
from pathlib import Path

import pandas as pd

from ingestion import ingest_and_normalize
from rule_engine import evaluate_transactions


BASE_DIR = Path(__file__).resolve().parent.parent

GT_PATH = BASE_DIR / "data" / "external" / "external_test_ground_truth.csv"

LEDGER_PATH = (
    BASE_DIR
    / "data"
    / "external"
    / "internal_ledger_external_test_v2.csv"
)

BANK_PATH = (
    BASE_DIR
    / "data"
    / "external"
    / "bank_statement_external_test_v2.csv"
)

OUTPUT_PATH = (
    BASE_DIR
    / "data"
    / "processed"
    / "evaluation_results.csv"
)


# ============================================================
# LOAD GROUND TRUTH
# ============================================================

def load_ground_truth():
    return pd.read_csv(GT_PATH)


# ============================================================
# BUILD ACTUAL RULE-ENGINE RESULTS
# ============================================================

def build_actual_results():
    transactions = ingest_and_normalize(
        ledger_path=str(LEDGER_PATH),
        bank_path=str(BANK_PATH),
        gateway_path=None,
    )

    results = evaluate_transactions(transactions)

    print()
    print("INPUT")
    print("=" * 65)
    print(f"Normalized records : {len(transactions)}")
    print(f"Rule results       : {len(results)}")

    # Group results by economic order.
    actual_by_order = defaultdict(list)

    for transaction, result in zip(transactions, results):
        if transaction.order_id:
            actual_by_order[transaction.order_id].append(result)

    return actual_by_order


# ============================================================
# PREDICT EXCEPTION TYPE
# ============================================================

def scenario_matches(gt_row, actual_results):
    """
    Determine the predicted exception type for one GT order.

    CLEAN_MATCH and other cases without an expected exception
    are represented as blank / NONE rather than being counted
    as exception-type errors.
    """

    expected_scenario = str(
        gt_row["scenario_type"]
    ).strip()

    expected_exception = str(
        gt_row.get("expected_exception_type", "")
    ).strip()

    if expected_exception == "nan":
        expected_exception = ""

    actual_exception_types = {
        str(result.exception_type).strip()
        for result in actual_results
        if result.exception_type
    }

    actual_final_statuses = {
        str(result.final_status.value).strip()
        for result in actual_results
    }

    # --------------------------------------------------------
    # CLEAN MATCH
    # --------------------------------------------------------

    if expected_scenario == "CLEAN_MATCH":
        if "RECONCILED" in actual_final_statuses:
            return ""

        return "UNEXPECTED_EXCEPTION"

    # --------------------------------------------------------
    # Expected exception
    # --------------------------------------------------------

    if expected_exception:
        if expected_exception in actual_exception_types:
            return expected_exception

        if actual_exception_types:
            return sorted(actual_exception_types)[0]

        return "NONE"

    # --------------------------------------------------------
    # No expected exception
    # --------------------------------------------------------

    if actual_exception_types:
        return sorted(actual_exception_types)[0]

    return ""


# ============================================================
# EXPECTED RULE-ENGINE OUTCOME
# ============================================================

def expected_rule_outcome(gt_row):
    return str(
        gt_row["expected_rule_engine_outcome"]
    ).strip()


# ============================================================
# ACTUAL RULE-ENGINE OUTCOME
# ============================================================

def actual_rule_outcome(gt_row, actual_results):
    """
    Evaluate the Rule Engine outcome at economic-order level.

    CLEAN_MATCH:
        At least one RECONCILED result => MATCHED.

    All exception scenarios:
        At least one non-RECONCILED result => EXCEPTION.
    """

    expected_scenario = str(
        gt_row["scenario_type"]
    ).strip()

    # --------------------------------------------------------
    # CLEAN MATCH
    # --------------------------------------------------------

    if expected_scenario == "CLEAN_MATCH":
        if any(
            result.final_status.value == "RECONCILED"
            for result in actual_results
        ):
            return "MATCHED"

        return "EXCEPTION"

    # --------------------------------------------------------
    # Exception scenarios
    # --------------------------------------------------------

    if any(
        result.final_status.value != "RECONCILED"
        for result in actual_results
    ):
        return "EXCEPTION"

    return "MATCHED"


# ============================================================
# MAIN EVALUATION
# ============================================================

def main():

    gt = load_ground_truth()
    actual_by_order = build_actual_results()

    evaluation_rows = []

    exception_correct = 0
    exception_evaluated = 0

    outcome_correct = 0

    missing_orders = []

    # ========================================================
    # EVALUATE EACH GT ORDER
    # ========================================================

    for _, gt_row in gt.iterrows():

        order_id = str(
            gt_row["order_id"]
        ).strip()

        actual_results = actual_by_order.get(
            order_id,
            []
        )

        if not actual_results:
            missing_orders.append(order_id)

        # ----------------------------------------------------
        # Expected exception
        # ----------------------------------------------------

        expected_exception = str(
            gt_row.get("expected_exception_type", "")
        ).strip()

        if expected_exception == "nan":
            expected_exception = ""

        # ----------------------------------------------------
        # Predicted exception
        # ----------------------------------------------------

        predicted_exception = scenario_matches(
            gt_row,
            actual_results,
        )

        # ----------------------------------------------------
        # Exception-type accuracy
        #
        # ONLY evaluate rows where GT actually expects
        # an exception type.
        # ----------------------------------------------------

        has_expected_exception = bool(
            expected_exception
        )

        if has_expected_exception:

            exception_evaluated += 1

            exception_is_correct = (
                predicted_exception
                == expected_exception
            )

            if exception_is_correct:
                exception_correct += 1

        else:
            exception_is_correct = None

        # ----------------------------------------------------
        # Rule outcome
        # ----------------------------------------------------

        expected_outcome = expected_rule_outcome(
            gt_row
        )

        predicted_outcome = actual_rule_outcome(
            gt_row,
            actual_results,
        )

        outcome_is_correct = (
            predicted_outcome
            == expected_outcome
        )

        if outcome_is_correct:
            outcome_correct += 1

        # ----------------------------------------------------
        # Store detailed result
        # ----------------------------------------------------

        evaluation_rows.append(
            {
                "order_id": order_id,

                "scenario_type": gt_row[
                    "scenario_type"
                ],

                "expected_exception_type":
                    expected_exception,

                "predicted_exception_type":
                    predicted_exception,

                "exception_evaluated":
                    has_expected_exception,

                "exception_correct":
                    exception_is_correct,

                "expected_rule_engine_outcome":
                    expected_outcome,

                "predicted_rule_engine_outcome":
                    predicted_outcome,

                "outcome_correct":
                    outcome_is_correct,

                "actual_record_count":
                    len(actual_results),

                "actual_exception_types":
                    ", ".join(
                        sorted(
                            {
                                str(
                                    r.exception_type
                                )
                                for r in actual_results
                                if r.exception_type
                            }
                        )
                    ),
            }
        )

    # ========================================================
    # SAVE RESULTS
    # ========================================================

    evaluation_df = pd.DataFrame(
        evaluation_rows
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    evaluation_df.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    # ========================================================
    # OVERALL METRICS
    # ========================================================

    total = len(gt)

    exception_accuracy = (
        exception_correct
        / exception_evaluated
        * 100
        if exception_evaluated
        else 0
    )

    outcome_accuracy = (
        outcome_correct
        / total
        * 100
        if total
        else 0
    )

    # ========================================================
    # PRINT RESULTS
    # ========================================================

    print()
    print("=" * 65)
    print("RESULTS")
    print("=" * 65)

    print(
        f"GT orders evaluated     : {total}"
    )

    print(
        f"Exception cases evaluated: "
        f"{exception_evaluated}"
    )

    print(
        f"Exception type accuracy : "
        f"{exception_accuracy:.2f}%"
    )

    print(
        f"Rule outcome accuracy   : "
        f"{outcome_accuracy:.2f}%"
    )

    # ========================================================
    # SCENARIO ACCURACY
    # ========================================================

    print()
    print("SCENARIO ACCURACY")
    print("-" * 65)

    for scenario in gt[
        "scenario_type"
    ].unique():

        subset = evaluation_df[
            evaluation_df[
                "scenario_type"
            ]
            == scenario
        ]

        # Exception accuracy only where an exception
        # is actually expected.

        exception_subset = subset[
            subset[
                "exception_evaluated"
            ] == True
        ]

        if exception_subset.empty:

            exception_text = "N/A"

        else:

            scenario_exception_accuracy = (
                exception_subset[
                    "exception_correct"
                ]
                .mean()
                * 100
            )

            exception_text = (
                f"{scenario_exception_accuracy:6.2f}%"
            )

        scenario_outcome_accuracy = (
            subset[
                "outcome_correct"
            ]
            .mean()
            * 100
        )

        print(
            f"{scenario:<20} "
            f"{len(subset):>3} | "
            f"Exception: {exception_text} | "
            f"Outcome: "
            f"{scenario_outcome_accuracy:6.2f}%"
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("-" * 65)

    incorrect_exceptions = (
        exception_evaluated
        - exception_correct
    )

    print(
        f"INCORRECT EXCEPTION "
        f"CLASSIFICATIONS: "
        f"{incorrect_exceptions}"
    )

    if missing_orders:

        print()

        print(
            "Orders with no normalized records: "
            f"{len(missing_orders)}"
        )

    # ========================================================
    # OUTPUT
    # ========================================================

    print()

    print(
        "Detailed evaluation saved to:"
    )

    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()