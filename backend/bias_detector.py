# ============================================================
# backend/bias_detector.py — Fairness & Bias Detection Engine
# ============================================================
# PURPOSE:
#   Automatically detects patterns in scoring results that
#   might indicate unfair penalization of strong candidates.
#   This is a critical feature for responsible AI in hiring.
#
# FLAGS DETECTED:
#   1. GitHub Penalty Flag — Strong candidate dragged down by
#      missing GitHub profile (a structural bias in Layer 5)
#   2. Junior Potential Flag — High semantic + skill match but
#      low experience score (worth a human review)
#   3. Alias Penalty Flag — Low taxonomy score despite high
#      semantic score (suggests unresolved aliases)
#   4. Single Signal Dominance — One layer disproportionately
#      controls the composite score
#   5. Experience Ceiling Hit — Candidate's experience was
#      capped, potentially masking seniority advantage
# ============================================================

from typing import List, Dict


def detect_bias_flags(results: List[Dict]) -> List[Dict]:
    """
    Analyzes pipeline results and returns a list of bias flags.

    Args:
        results (list): List of candidate result dicts from main.py

    Returns:
        list: List of flag dicts, each containing:
              - candidate (str): Candidate name
              - flag_type (str): Category of bias detected
              - severity (str): "warning" | "info"
              - message (str): Human-readable explanation
              - recommendation (str): Suggested action
    """
    flags = []

    for result in results:
        name    = result["name"]
        s1      = result["score_l1"]   # Semantic
        s2      = result["score_l2"]   # Taxonomy
        s3      = result["score_l3"]   # Experience
        s4      = result["score_l4"]   # Projects
        s5      = result["score_l5"]   # GitHub
        composite = result["composite"]

        # --------------------------------------------------------
        # FLAG 1: GitHub Penalty Detection
        # --------------------------------------------------------
        # If a candidate scores well across all other layers but
        # has a low GitHub score (likely no username provided),
        # they are being unfairly penalized for a structural gap
        # in data collection — not actual lack of activity.
        # --------------------------------------------------------
        avg_non_github = (s1 + s2 + s3 + s4) / 4
        if s5 < 55 and avg_non_github > 70:
            flags.append({
                "candidate"     : name,
                "flag_type"     : "GitHub Data Gap",
                "severity"      : "warning",
                "message"       : (
                    f"{name} scores {avg_non_github:.1f}% across technical layers "
                    f"but only {s5:.1f}% on GitHub — likely due to missing or "
                    f"private GitHub profile, not actual inactivity."
                ),
                "recommendation": (
                    "Request GitHub username or accept alternative portfolio evidence "
                    "(personal website, LinkedIn, code samples)."
                ),
            })

        # --------------------------------------------------------
        # FLAG 2: High-Potential Junior
        # --------------------------------------------------------
        # Strong semantic and skill alignment but penalized solely
        # due to years-of-experience gap. Worth human review for
        # roles open to high-potential early-career candidates.
        # --------------------------------------------------------
        if s3 < 50 and s1 > 72 and s2 > 65:
            flags.append({
                "candidate"     : name,
                "flag_type"     : "High-Potential Junior",
                "severity"      : "info",
                "message"       : (
                    f"{name} shows strong semantic ({s1:.1f}%) and skill ({s2:.1f}%) "
                    f"alignment but scores {s3:.1f}% on experience — below the threshold. "
                    f"Their technical profile closely matches the role requirements."
                ),
                "recommendation": (
                    "Consider for junior variant of the role or fast-track interview "
                    "to assess practical depth beyond years on paper."
                ),
            })

        # --------------------------------------------------------
        # FLAG 3: Alias Resolution Gap
        # --------------------------------------------------------
        # High semantic score (model understands they're aligned)
        # but low taxonomy score (exact keyword match failed).
        # Suggests the taxonomy map may be missing an alias.
        # --------------------------------------------------------
        if s1 > 75 and s2 < 50:
            flags.append({
                "candidate"     : name,
                "flag_type"     : "Possible Alias Gap",
                "severity"      : "info",
                "message"       : (
                    f"{name} has high semantic alignment ({s1:.1f}%) but low "
                    f"taxonomy score ({s2:.1f}%). The candidate may be using "
                    f"skill terminology not yet in the taxonomy map."
                ),
                "recommendation": (
                    "Review candidate's raw skill list for unlisted aliases "
                    "and consider updating the TAXONOMY_MAP in layer_2_taxonomy.py."
                ),
            })

        # --------------------------------------------------------
        # FLAG 4: Project-Resume Mismatch
        # --------------------------------------------------------
        # High resume semantic score but low project relevance.
        # Candidate talks the talk but projects don't match.
        # --------------------------------------------------------
        if s1 > 72 and s4 < 45:
            flags.append({
                "candidate"     : name,
                "flag_type"     : "Project-Resume Mismatch",
                "severity"      : "warning",
                "message"       : (
                    f"{name} has strong resume alignment ({s1:.1f}%) but "
                    f"low project relevance ({s4:.1f}%). Their listed projects "
                    f"may not reflect the skills claimed in their resume."
                ),
                "recommendation": (
                    "Ask for portfolio links or code samples during screening "
                    "to verify practical application of claimed skills."
                ),
            })

        # --------------------------------------------------------
        # FLAG 5: Experience Ceiling Hit
        # --------------------------------------------------------
        # Candidate's raw experience score exceeded 100 before
        # the ceiling was applied — they are significantly over-
        # qualified. May indicate role mismatch (too senior).
        # --------------------------------------------------------
        years           = result.get("years_of_experience", 0)
        required_years  = result.get("required_years", 3)
        if required_years > 0 and years > 0:
            raw_exp_ratio = (years / required_years) * 100
            if raw_exp_ratio > 150 and composite > 75:
                flags.append({
                    "candidate"     : name,
                    "flag_type"     : "Potential Overqualification",
                    "severity"      : "info",
                    "message"       : (
                        f"{name} has {years} years of experience vs {required_years} "
                        f"required ({raw_exp_ratio:.0f}% of requirement). "
                        f"Their experience score was capped at 100% — actual seniority "
                        f"level significantly exceeds the role requirement."
                    ),
                    "recommendation": (
                        "Assess whether the role offers sufficient growth and "
                        "compensation to retain this candidate long-term."
                    ),
                })

    return flags
