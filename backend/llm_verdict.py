# ============================================================
# backend/llm_verdict.py — LLM Candidate Verdict Engine
# ============================================================
# PURPOSE:
#   Uses the Anthropic Claude API to generate a professional,
#   human-readable hiring recommendation for each candidate
#   based on their layer scores and profile data.
#
# SETUP:
#   1. Get your Anthropic API key from https://console.anthropic.com
#   2. Create a .env file in the project root with:
#      ANTHROPIC_API_KEY=your-key-here
#   3. The system will automatically load it via python-dotenv
#
# FALLBACK:
#   If the API key is missing or the call fails, returns a
#   deterministic rule-based verdict instead — the app never
#   crashes due to LLM unavailability.
# ============================================================

import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Attempt to import and initialize the Anthropic client
_anthropic_client = None

try:
    import anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if api_key:
        _anthropic_client = anthropic.Anthropic(api_key=api_key)
        logger.info("LLM Verdict: Anthropic client initialized successfully. ✓")
    else:
        logger.warning(
            "LLM Verdict: ANTHROPIC_API_KEY not found in environment. "
            "Will use rule-based fallback verdicts."
        )
except ImportError:
    logger.warning("LLM Verdict: anthropic package not installed. Using fallback.")


def generate_verdict(
    candidate_name     : str,
    scores             : dict,
    jd_text            : str,
    candidate_skills   : list,
    years_of_experience: int,
) -> dict:
    """
    Generates a professional hiring verdict for a candidate.

    Args:
        candidate_name      (str):  Candidate's full name
        scores              (dict): Dict with keys l1-l5 and composite
        jd_text             (str):  Job description text
        candidate_skills    (list): Candidate's skill list
        years_of_experience (int):  Candidate's years of experience

    Returns:
        dict:
        - verdict (str): 2-3 sentence hiring recommendation
        - recommendation (str): "Strong Hire" | "Consider" | "Pass"
        - source (str): "llm" | "fallback"
    """

    # ----------------------------------------------------------
    # BUILD SCORES SUMMARY FOR PROMPT
    # ----------------------------------------------------------
    scores_summary = (
        f"Semantic Match: {scores.get('l1', 0):.1f}%, "
        f"Skill Taxonomy: {scores.get('l2', 0):.1f}%, "
        f"Experience: {scores.get('l3', 0):.1f}%, "
        f"Project Relevance: {scores.get('l4', 0):.1f}%, "
        f"GitHub Activity: {scores.get('l5', 0):.1f}%, "
        f"Composite: {scores.get('composite', 0):.1f}%"
    )

    skills_str = ", ".join(candidate_skills) if candidate_skills else "Not listed"

    # ----------------------------------------------------------
    # ATTEMPT LLM VERDICT
    # ----------------------------------------------------------
    if _anthropic_client is not None:
        try:
            prompt = f"""You are a senior technical recruiter with 15 years of experience 
at a top-tier technology company. Analyze this candidate evaluation and provide a concise verdict.

JOB DESCRIPTION:
{jd_text}

CANDIDATE: {candidate_name}
SKILLS: {skills_str}
EXPERIENCE: {years_of_experience} years
AI SCORING BREAKDOWN: {scores_summary}

Provide:
1. A 2-3 sentence professional hiring recommendation that references specific scores and skills.
2. A final recommendation label — exactly one of: "Strong Hire", "Consider", or "Pass"

Format your response as:
VERDICT: [your 2-3 sentence analysis]
RECOMMENDATION: [Strong Hire | Consider | Pass]

Be specific, professional, and constructive. Reference actual numbers from the scoring."""

            message = _anthropic_client.messages.create(
                model      = "claude-sonnet-4-6",
                max_tokens = 300,
                messages   = [{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()

            # Parse the structured response
            verdict        = ""
            recommendation = "Consider"

            for line in response_text.split("\n"):
                if line.startswith("VERDICT:"):
                    verdict = line.replace("VERDICT:", "").strip()
                elif line.startswith("RECOMMENDATION:"):
                    rec_raw        = line.replace("RECOMMENDATION:", "").strip()
                    recommendation = rec_raw if rec_raw in ["Strong Hire", "Consider", "Pass"] else "Consider"

            if not verdict:
                verdict = response_text  # Fallback: use full response as verdict

            logger.info(f"LLM Verdict: Generated for {candidate_name} → {recommendation}")

            return {
                "verdict"       : verdict,
                "recommendation": recommendation,
                "source"        : "llm",
            }

        except Exception as e:
            logger.warning(f"LLM Verdict: API call failed — {e}. Using rule-based fallback.")

    # ----------------------------------------------------------
    # RULE-BASED FALLBACK VERDICT
    # ----------------------------------------------------------
    # Deterministic verdict based on composite score thresholds.
    # Runs when API key is missing or API call fails.
    # ----------------------------------------------------------
    composite = scores.get("composite", 0)
    s1        = scores.get("l1", 0)
    s2        = scores.get("l2", 0)
    s3        = scores.get("l3", 0)

    if composite >= 75:
        recommendation = "Strong Hire"
        verdict = (
            f"{candidate_name} is a strong match for this role with a composite score "
            f"of {composite:.1f}%. Their semantic alignment ({s1:.1f}%) and skill coverage "
            f"({s2:.1f}%) indicate excellent fit. Recommend proceeding to technical interview."
        )
    elif composite >= 55:
        recommendation = "Consider"
        verdict = (
            f"{candidate_name} shows moderate alignment with a composite score of {composite:.1f}%. "
            f"Skill match of {s2:.1f}% and experience score of {s3:.1f}% suggest partial fit. "
            f"A screening call is recommended to assess gaps before a full interview."
        )
    else:
        recommendation = "Pass"
        verdict = (
            f"{candidate_name} scores {composite:.1f}% overall, below the recommended threshold "
            f"for this role. Key gaps in semantic alignment ({s1:.1f}%) and skill coverage "
            f"({s2:.1f}%) suggest this candidate is not the right fit at this time."
        )

    return {
        "verdict"       : verdict,
        "recommendation": recommendation,
        "source"        : "fallback",
    }
