from model import ReconciliationResult, FinalStatus
from llm_agent import LLMExceptionAnalysis


def make_decision(
    rule_result: ReconciliationResult,
    llm_analysis: LLMExceptionAnalysis,
) -> FinalStatus:

    if (
        llm_analysis.confidence_score >= 0.80
        and not llm_analysis.requires_human_review
        and llm_analysis.resolution
    ):
        return FinalStatus.RESOLVED

    if llm_analysis.requires_human_review:
        return FinalStatus.NEEDS_REVIEW

    return FinalStatus.UNRESOLVED