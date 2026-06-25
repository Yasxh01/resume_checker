# ============================================================
# backend/layer_3_experience.py — Experience Ratio Engine
# ============================================================

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def calculate_experience_score(candidate_years: int, required_years: int) -> float:
    """
    Calculates experience score with hard ceiling at 100.0.
    Formula: min((candidate_years / required_years) * 100, 100.0)
    """
    if required_years == 0:
        return 100.0
    if candidate_years == 0:
        return 0.0
    if candidate_years < 0 or required_years < 0:
        return 0.0

    raw_score   = (candidate_years / required_years) * 100
    final_score = min(raw_score, 100.0)

    logger.info(
        f"Layer 3: ({candidate_years}/{required_years}) * 100 = "
        f"{round(raw_score, 2)}% → capped at {round(final_score, 2)}%"
    )

    return round(final_score, 2)
