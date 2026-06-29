# ==========================================================
# backend/layer_4_projects.py — Enhanced Project Engine
# ==========================================================
#
# SIGNAL 1 — GitHub Repository Deep Analysis (50% weight):
#   Fetches actual repo languages and topics via GitHub API.
#   Matches them against JD required skills for hard evidence
#   of what the candidate has actually BUILT, not just claimed.
#
# SIGNAL 2 — Code Quality Signals (50% weight):
#   Evaluates stars, forks, documentation discipline, and
#   recent activity — peer-validated quality indicators.
#
# FALLBACK — Semantic Text Similarity:
#   If no GitHub username is provided, falls back to the
#   original semantic cosine similarity of project text vs JD.
#   This ensures the layer always produces a score.
# ============================================================

import os
import logging
import asyncio
import httpx

from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from datetime import datetime, timedelta, timezone


GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
_github_cache = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================
GITHUB_API_BASE  = "https://api.github.com"
REQUEST_TIMEOUT  = 10
MAX_REPOS        = 30    # Max repos to fetch per user
RECENT_CUTOFF = datetime.now(timezone.utc) - timedelta(days=365)


WEIGHT_SKILL_MATCH  = 0.50   # GitHub language/topic vs JD skills
WEIGHT_CODE_QUALITY = 0.50   # Stars, forks, docs, activity


# ============================================================
# HELPER: Shared model accessor (avoids Windows spawn issues)
# ============================================================
def _get_model():
    try:
        import layer_1_semantic
        return layer_1_semantic._embedding_model
    except Exception:
        return None


# ============================================================
# HELPER: Fetch GitHub Repositories
# ============================================================
def _get_github_headers() -> dict:
    headers = {
        "User-Agent": "CandidateRankingPlatform/2.0",
        "Accept"    : "application/vnd.github.v3+json",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


async def _fetch_repos(client: httpx.AsyncClient, username: str) -> list:
    """
    Fetches public repositories for a GitHub user.

    Returns:
        list: List of repo dicts from GitHub API, or empty list on failure.
    """
    cache_key = f"repos_{username}"

    # Cache hit
    if cache_key in _github_cache:
        return _github_cache[cache_key]

    try:
        url = f"{GITHUB_API_BASE}/users/{username}/repos"
        params = {
            "per_page": MAX_REPOS,
            "sort": "updated",
            "type": "owner"
        }

        response = await client.get(
            url,
            params=params,
            headers=_get_github_headers(),
            timeout=REQUEST_TIMEOUT
        )

        # Success
        if response.status_code == 200:
            data = response.json()
            _github_cache[cache_key] = data
            return data

        # GitHub rate limit
        if response.status_code == 403:
            remaining = response.headers.get("X-RateLimit-Remaining")

            if remaining == "0":
                logger.warning(
                    "Layer 4: GitHub API rate limit reached. Falling back to semantic scoring."
                )
            else:
                logger.warning(
                    "Layer 4: GitHub returned HTTP 403."
                )

            return []

        # User not found
        if response.status_code == 404:
            logger.warning(
                f"Layer 4: GitHub user '{username}' not found."
            )
            return []

        # Other errors
        logger.warning(
            f"Layer 4: GitHub returned HTTP {response.status_code}"
        )
        return []

    except httpx.TimeoutException:
        logger.warning("Layer 4: GitHub request timed out.")
        return []

    except Exception as e:
        logger.warning(f"Layer 4: GitHub fetch failed - {e}")
        return []

# ============================================================
# HELPER: Fetch Repo Languages
# ============================================================
async def _fetch_repo_languages(client: httpx.AsyncClient, languages_url: str) -> dict:
    """
    Fetches language breakdown for a single repository.

    Returns:
        dict: {language_name: bytes_of_code} or empty dict.
    """
    if languages_url in _github_cache:
        return _github_cache[languages_url]

    try:
        response = await client.get(languages_url, headers=_get_github_headers(), timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            _github_cache[languages_url] = data
            return data
        return {}
    except Exception:
        return {}


# ============================================================
# SIGNAL 1: GitHub Skill Match Score
# ============================================================
async def _calculate_skill_match_score(client: httpx.AsyncClient, repos: list, jd_skills: list) -> dict:
    """
    Matches actual GitHub repo languages and topics against JD skills.

    Process:
    1. Aggregate all languages across repos (weighted by bytes of code)
    2. Collect all repo topics (manually set tags like "django", "aws")
    3. Normalize everything to lowercase
    4. Compute intersection with normalized JD skills
    5. Score = (matched_skills / total_jd_skills) * 100

    Args:
        repos     (list): GitHub repos from API
        jd_skills (list): Required skills from job description

    Returns:
        dict: score, matched_skills, all_languages, all_topics
    """
    if not repos or not jd_skills:
        return {"score": 0.0, "matched_skills": [], "all_languages": {}, "all_topics": []}

    # Aggregate languages across all repos concurrently
    all_languages = {}
    lang_urls = [repo.get("languages_url") for repo in repos if repo.get("languages_url")]
    
    tasks = [_fetch_repo_languages(client, url) for url in lang_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for langs in results:
        if isinstance(langs, dict):
            for lang, bytes_count in langs.items():
                key = lang.lower()
                all_languages[key] = all_languages.get(key, 0) + bytes_count
        elif isinstance(langs, Exception):
            logger.warning(f"Layer 4: Failed to fetch language data - {langs}")

    # Collect all topics across repos
    all_topics = []
    for repo in repos:
        topics = repo.get("topics", [])
        all_topics.extend([t.lower().replace("-", " ") for t in topics])

    # Build candidate's technical fingerprint
    candidate_tech = set(all_languages.keys()) | set(all_topics)

    # Normalize JD skills for comparison
    # Apply basic alias resolution inline
    QUICK_ALIASES = {
        "javascript": ["js", "es6", "ecmascript", "vanilla js"],
        "typescript": ["ts"],
        "python"    : ["py", "python3"],
        "postgresql": ["postgres", "pg"],
        "mongodb"   : ["mongo"],
        "kubernetes": ["k8s"],
        "aws"       : ["amazon web services"],
    }

    normalized_jd = set()
    for skill in jd_skills:
        s = skill.lower().strip()
        normalized_jd.add(s)
        # Add reverse aliases: if JD has "aws", also check for "amazon-web-services"
        for canonical, aliases in QUICK_ALIASES.items():
            if s == canonical:
                normalized_jd.update(aliases)
            elif s in aliases:
                normalized_jd.add(canonical)

    # Compute intersection
    matched = normalized_jd & candidate_tech

    # Score
    score = (len(matched) / max(len(set(s.lower() for s in jd_skills)), 1)) * 100
    score = round(min(score, 100.0), 2)

    logger.info(
        f"Layer 4 (Skill Match): {len(matched)}/{len(jd_skills)} skills matched "
        f"in GitHub repos = {score}%"
    )

    return {
        "score"          : score,
        "matched_skills" : sorted(list(matched)),
        "all_languages"  : dict(sorted(all_languages.items(), key=lambda x: x[1], reverse=True)[:10]),
        "all_topics"     : list(set(all_topics))[:15],
    }


# ============================================================
# SIGNAL 2: Code Quality Score
# ============================================================
def _calculate_code_quality_score(repos: list) -> dict:
    """
    Evaluates code quality signals across all repositories.

    Signals:
    - Stars:           Community recognition (max 30 pts)
    - Forks:           Others built on their work (max 25 pts)
    - Documentation:   Repos with descriptions (max 20 pts)
    - Recent Activity: Repos updated recently (max 25 pts)

    Args:
        repos (list): GitHub repos from API

    Returns:
        dict: score, total_stars, total_forks, documented, recent_active
    """
    if not repos:
        return {
            "score": 0.0, "total_stars": 0, "total_forks": 0,
            "documented_repos": 0, "recently_active": 0,
            "documentation_pct": 0.0, "activity_pct": 0.0,
        }

    total_repos    = len(repos)
    total_stars    = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks    = sum(r.get("forks_count",       0) for r in repos)
    documented     = sum(1 for r in repos if r.get("description") and len(r["description"]) > 5)
    recently_active = sum(
        1 for r in repos
        if (
            r.get("updated_at", "")
             and datetime.fromisoformat(
                 r["updated_at"].replace("Z","+00:00")
             ) >= RECENT_CUTOFF
               and not r.get("fork", False)
        )
    )

    # ----------------------------------------------------------
    # SCORING BREAKDOWN
    # ----------------------------------------------------------

    # Stars score: logarithmic scale to prevent 1 viral repo dominating
    # 0 stars=0, 10 stars≈20pts, 50 stars≈27pts, 100 stars=30pts
    import math
    star_score  = min(30.0, (math.log1p(total_stars) / math.log1p(100)) * 30)

    # Forks score: linear, capped at 25 pts (10 forks = 25 pts)
    fork_score  = min(25.0, (total_forks / max(1, 10)) * 25)

    # Documentation score: % of repos with descriptions × 20 pts
    doc_pct     = documented / total_repos
    doc_score   = doc_pct * 20

    # Activity score: % of repos active recently × 25 pts
    active_pct  = recently_active / total_repos
    active_score = active_pct * 25

    total_score = star_score + fork_score + doc_score + active_score
    total_score = round(min(total_score, 100.0), 2)

    logger.info(
        f"Layer 4 (Code Quality): stars={total_stars}→{round(star_score,1)}pts, "
        f"forks={total_forks}→{round(fork_score,1)}pts, "
        f"docs={round(doc_pct*100)}%→{round(doc_score,1)}pts, "
        f"active={round(active_pct*100)}%→{round(active_score,1)}pts "
        f"= {total_score}/100"
    )

    return {
        "score"            : total_score,
        "total_stars"      : total_stars,
        "total_forks"      : total_forks,
        "documented_repos" : documented,
        "recently_active"  : recently_active,
        "documentation_pct": round(doc_pct * 100, 1),
        "activity_pct"     : round(active_pct * 100, 1),
        "star_score"       : round(star_score,   1),
        "fork_score"       : round(fork_score,   1),
        "doc_score"        : round(doc_score,    1),
        "active_score"     : round(active_score, 1),
    }


# ============================================================
# FALLBACK: Semantic Text Similarity
# ============================================================
def _semantic_fallback(jd_text: str, projects_text: str) -> float:
    """
    Original V1 scoring — used when no GitHub username is provided.
    Computes cosine similarity between JD and project description text.
    """
    if not projects_text or not projects_text.strip():
        return 0.0
    if not jd_text or not jd_text.strip():
        return 0.0

    model = _get_model()

    if model is not None:
        try:
            jd_emb  = model.encode(jd_text,       convert_to_numpy=True)
            pr_emb  = model.encode(projects_text, convert_to_numpy=True)
            sim     = cosine_similarity(jd_emb.reshape(1, -1), pr_emb.reshape(1, -1))
            return round(float(sim[0][0]) * 100, 2)
        except Exception as e:
            logger.warning(f"Layer 4: Neural fallback failed — {e}. Using TF-IDF.")

    try:
        vectorizer   = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform([jd_text, projects_text])
        sim          = cosine_similarity(tfidf_matrix[0], tfidf_matrix[1])
        return round(float(sim[0][0]) * 100, 2)
    except Exception as e:
        logger.error(f"Layer 4: TF-IDF fallback failed — {e}.")
        return 0.0


# ============================================================
# PUBLIC API
# ============================================================
async def calculate_project_relevance(
    jd_text       : str,
    projects_text : str,
    jd_skills     : list = None,
    github_username: str = "",
) -> dict:
    """
    Dual-signal project portfolio relevance engine.

    If github_username is provided:
      → Fetches live repo data from GitHub API
      → Score = (skill_match × 0.5) + (code_quality × 0.5)

    If no github_username:
      → Falls back to semantic text similarity (V1 method)

    Args:
        jd_text         (str):  Full job description text.
        projects_text   (str):  Candidate's project descriptions.
        jd_skills       (list): Required skills for repo matching.
        github_username (str):  GitHub username for live API scoring.

    Returns:
        dict:
          - score             (float): Final 0.0–100.0
          - method            (str):   "github_api" | "semantic_fallback"
          - skill_match_score (float): GitHub language/topic match score
          - quality_score     (float): Code quality signals score
          - matched_skills    (list):  Skills found in actual repos
          - top_languages     (list):  Top programming languages used
          - total_stars       (int):   Total stars across all repos
          - total_forks       (int):   Total forks across all repos
          - repos_analysed    (int):   Number of repos fetched
    """
    jd_skills = jd_skills or []

    # ----------------------------------------------------------
    # PATH A: GitHub API Deep Analysis
    # ----------------------------------------------------------
    if github_username and github_username.strip():
        username = github_username.strip()
        logger.info(f"Layer 4: Fetching GitHub repos for '{username}'...")

        async with httpx.AsyncClient() as client:
            repos = await _fetch_repos(client, username)
            if repos:
                skill_result = await _calculate_skill_match_score(client, repos, jd_skills)

        if repos:
            quality_result = _calculate_code_quality_score(repos)

            # Composite
            composite = (
                skill_result["score"]   * WEIGHT_SKILL_MATCH +
                quality_result["score"] * WEIGHT_CODE_QUALITY
            )
            composite = round(min(composite, 100.0), 2)

            logger.info(
                f"Layer 4: GitHub composite = "
                f"skill({skill_result['score']}) × {WEIGHT_SKILL_MATCH} + "
                f"quality({quality_result['score']}) × {WEIGHT_CODE_QUALITY} "
                f"= {composite}"
            )

            return {
                "score"             : composite,
                "method"            : "github_api",
                "skill_match_score" : skill_result["score"],
                "quality_score"     : quality_result["score"],
                "matched_skills"    : skill_result["matched_skills"],
                "top_languages"     : list(skill_result["all_languages"].keys())[:5],
                "all_topics"        : skill_result["all_topics"],
                "total_stars"       : quality_result["total_stars"],
                "total_forks"       : quality_result["total_forks"],
                "documented_repos"  : quality_result["documented_repos"],
                "recently_active"   : quality_result["recently_active"],
                "repos_analysed"    : len(repos),
                "star_score"        : quality_result["star_score"],
                "fork_score"        : quality_result["fork_score"],
                "doc_score"         : quality_result["doc_score"],
                "active_score"      : quality_result["active_score"],
            }
        else:
            logger.warning(f"Layer 4: No repos found for '{username}'. Using semantic fallback.")

    # ----------------------------------------------------------
    # PATH B: Semantic Text Fallback
    # ----------------------------------------------------------
    logger.info("Layer 4: No GitHub username — using semantic text similarity.")
    semantic_score = _semantic_fallback(jd_text, projects_text)

    return {
        "score"             : semantic_score,
        "method"            : "semantic_fallback",
        "skill_match_score" : 0.0,
        "quality_score"     : 0.0,
        "matched_skills"    : [],
        "top_languages"     : [],
        "all_topics"        : [],
        "total_stars"       : 0,
        "total_forks"       : 0,
        "documented_repos"  : 0,
        "recently_active"   : 0,
        "repos_analysed"    : 0,
        "star_score"        : 0.0,
        "fork_score"        : 0.0,
        "doc_score"         : 0.0,
        "active_score"      : 0.0,
    }
