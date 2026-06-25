# ============================================================
# backend/layer_2_taxonomy.py — Skill Taxonomy Engine
# ============================================================
# UPDATED: Now returns matched AND missing skills for the
# Score Explanation Panel in the frontend.
# ============================================================

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# TAXONOMY MAP — Alias Resolution Dictionary
# ============================================================
TAXONOMY_MAP = {
    # Cloud
    "amazon web services"   : "aws",
    "amazon-web-services"   : "aws",
    "aws cloud"             : "aws",
    "google cloud"          : "gcp",
    "google cloud platform" : "gcp",
    "microsoft azure"       : "azure",
    "azure cloud"           : "azure",

    # Databases
    "postgres"              : "postgresql",
    "postgres sql"          : "postgresql",
    "pg"                    : "postgresql",
    "mongo"                 : "mongodb",
    "mongo db"              : "mongodb",
    "ms sql"                : "mssql",
    "sql server"            : "mssql",
    "microsoft sql server"  : "mssql",
    "elastic"               : "elasticsearch",
    "es"                    : "elasticsearch",

    # Frontend
    "reactjs"               : "react",
    "react.js"              : "react",
    "react js"              : "react",
    "vuejs"                 : "vue",
    "vue.js"                : "vue",
    "nextjs"                : "nextjs",
    "next.js"               : "nextjs",
    "angularjs"             : "angular",
    "angular.js"            : "angular",

    # Backend
    "django rest framework" : "django",
    "drf"                   : "django",
    "django rest"           : "django",
    "flask api"             : "flask",
    "flask-restful"         : "flask",
    "express"               : "expressjs",
    "express.js"            : "expressjs",
    "fast api"              : "fastapi",
    "spring boot"           : "spring",
    "spring framework"      : "spring",
    "node"                  : "nodejs",
    "node.js"               : "nodejs",

    # Languages
    "py"                    : "python",
    "python3"               : "python",
    "python 3"              : "python",
    "ts"                    : "typescript",
    "type script"           : "typescript",
    "js"                    : "javascript",
    "es6"                   : "javascript",
    "vanilla js"            : "javascript",
    "ecmascript"            : "javascript",
    "c++"                   : "cpp",
    "cplusplus"             : "cpp",
    "golang"                : "go",
    "go lang"               : "go",

    # DevOps
    "docker container"      : "docker",
    "containerization"      : "docker",
    "k8s"                   : "kubernetes",
    "kube"                  : "kubernetes",
    "ci/cd"                 : "cicd",
    "ci cd"                 : "cicd",
    "continuous integration": "cicd",
    "continuous deployment" : "cicd",
    "github actions"        : "cicd",
    "jenkins"               : "cicd",
    "infra as code"         : "terraform",
    "iac"                   : "terraform",

    # ML/Data
    "scikit learn"          : "scikitlearn",
    "sklearn"               : "scikitlearn",
    "scikit-learn"          : "scikitlearn",
    "tf"                    : "tensorflow",
    "torch"                 : "pytorch",

    # Version Control
    "github"                : "git",
    "gitlab"                : "git",
    "bitbucket"             : "git",
    "version control"       : "git",
}


def _normalize_skill(skill: str) -> str:
    """Normalize a skill string to its canonical form."""
    cleaned = skill.lower().strip()
    return TAXONOMY_MAP.get(cleaned, cleaned)


def calculate_taxonomy_score(jd_skills: list, candidate_skills: list) -> dict:
    """
    Calculates taxonomy score with full explanation.

    Returns a dict containing:
    - score (float): 0.0 to 100.0
    - matched (list): Skills the candidate has that match JD
    - missing (list): Required skills the candidate lacks
    - normalized_jd (list): JD skills after normalization
    - normalized_candidate (list): Candidate skills after normalization
    """
    # Zero-division safety
    if not jd_skills or len(jd_skills) == 0:
        return {
            "score": 100.0,
            "matched": [],
            "missing": [],
            "normalized_jd": [],
            "normalized_candidate": [],
        }

    if not candidate_skills or len(candidate_skills) == 0:
        normalized_jd = [_normalize_skill(s) for s in jd_skills]
        return {
            "score": 0.0,
            "matched": [],
            "missing": normalized_jd,
            "normalized_jd": normalized_jd,
            "normalized_candidate": [],
        }

    # Normalize both skill lists
    normalized_jd_set        = set(_normalize_skill(s) for s in jd_skills)
    normalized_candidate_set = set(_normalize_skill(s) for s in candidate_skills)

    # Compute intersection and difference
    matched_set = normalized_jd_set & normalized_candidate_set
    missing_set = normalized_jd_set - normalized_candidate_set

    # Calculate score
    score = (len(matched_set) / len(normalized_jd_set)) * 100

    logger.info(
        f"Layer 2: {len(matched_set)}/{len(normalized_jd_set)} skills matched = {round(score, 2)}%"
    )

    return {
        "score"               : round(score, 2),
        "matched"             : sorted(list(matched_set)),
        "missing"             : sorted(list(missing_set)),
        "normalized_jd"       : sorted(list(normalized_jd_set)),
        "normalized_candidate": sorted(list(normalized_candidate_set)),
    }
