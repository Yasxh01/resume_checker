# ============================================================
# backend/layer_2_taxonomy.py — Skill Taxonomy Engine
# ============================================================
import logging
import difflib
from functools import lru_cache

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
    "ec2"                   : "aws",
    "s3"                    : "aws",
    "lambda"                : "aws",
    "cloudformation"        : "aws",
    "cloud functions"       : "gcp",
    "compute engine"        : "gcp",
    "bigquery"              : "gcp",
    "azure functions"       : "azure",

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
    "mysql server": "mysql",
    "mariadb": "mysql",
    "redis cache": "redis",
    "dynamodb": "dynamodb",
    "firebase firestore": "firestore",
    "firestore": "firestore",

    # Frontend
    "reactjs"               : "react",
    "react.js"              : "react",
    "react js"              : "react",
    "vuejs"                 : "vue",
    "vue.js"                : "vue",
    "nextjs"                : "nextjs",
    "next.js"               : "nextjs",
    "angularjs"             : "angular",
    "react native": "reactnative",
    "react-native": "reactnative",
    "html5": "html",
    "css3": "css",
    "tailwind css": "tailwind",
    "tailwindcss": "tailwind",
    "bootstrap 5": "bootstrap",
    "angular.js" : "angular",

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
    "fastapi": "fastapi",
    "rest api": "rest",
    "restful api": "rest",
    "restful services": "rest",
    "spring boot": "springboot",
    "spring mvc": "spring",
    ".net": "dotnet",
    "asp.net": "dotnet",
    "asp.net core": "dotnet",

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
    "c sharp": "csharp",
    "c#": "csharp",
    "cpp": "cpp",
    "java 8": "java",
    "java 11": "java",
    "java 17": "java",
    "typescript": "typescript",

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
    "github actions": "github-actions",
    "github workflow": "github-actions",
    "docker compose": "docker",
    "kubernetes cluster": "kubernetes",
    "helm": "helm",
    "ansible": "ansible",
    "terraform clud": "terraform",

    # ML/Data
    "scikit learn"          : "scikitlearn",
    "sklearn"               : "scikitlearn",
    "scikit-learn"          : "scikitlearn",
    "tf"                    : "tensorflow",
    "torch"                 : "pytorch",
    "numpy": "numpy",
    "np": "numpy",
    "pandas": "pandas",
    "pd": "pandas",
    "opencv": "opencv",
    "huggingface": "huggingface",
    "hugging face": "huggingface",
    "langchain": "langchain",
    "llm": "llm",
    "genai": "generative ai",
    "generative ai": "generative ai",
    "bert": "transformers",
    "transformers": "transformers",

    # Version Control
    "github"                : "git",
    "gitlab"                : "git",
    "bitbucket"             : "git",
    "version control"       : "git",
    "git hub": "git",
    "gitlab ci": "git",
}

@lru_cache(maxsize=512)
def _normalize_skill(skill: str) -> str:
    """Normalize a skill string to its canonical form."""
    if not skill:
        return ""
    cleaned = skill.lower().strip()
    return TAXONOMY_MAP.get(cleaned, cleaned)

def _fuzzy_match(skill: str, candidate_skills: set, cutoff: float = 0.90) -> bool:
    """
    Returns True if a close skill match exists.
    Used only when exact matching fails.
    """
    return bool(
        difflib.get_close_matches(
            skill,
            candidate_skills,
            n=1,
            cutoff=cutoff,
        )
    )

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
    
    if not jd_skills:
        return {
            "score": 100.0,
            "matched": [],
            "missing": [],
            "normalized_jd": [],
            "normalized_candidate": [],
        }

    if not candidate_skills:
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
    for skill in list(missing_set):

        if _fuzzy_match(skill, normalized_candidate_set):
            matched_set.add(skill)
            missing_set.remove(skill)


    # Calculate score
    score = (len(matched_set) / len(normalized_jd_set)) * 100

    logger.info(
    "Layer 2: %d/%d skills matched (%.2f%%)",
    len(matched_set),
    len(normalized_jd_set),
    score,
    )

    return {
        "score"               : round(score, 2),
        "matched"             : sorted(list(matched_set)),
        "missing"             : sorted(list(missing_set)),
        "normalized_jd"       : sorted(list(normalized_jd_set)),
        "normalized_candidate": sorted(list(normalized_candidate_set)),
    }
