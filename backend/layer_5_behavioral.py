# ============================================================
# backend/layer_5_behavioral.py — GitHub Behavioral Engine
# ============================================================

import logging
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POINTS_PER_REPO     = 2
MAX_REPO_SCORE      = 50
POINTS_PER_FOLLOWER = 5
MAX_FOLLOWER_SCORE  = 50
NEUTRAL_SCORE       = 50.0
GITHUB_API_URL      = "https://api.github.com/users/{username}"
REQUEST_TIMEOUT     = 10


def calculate_github_score(github_username: str) -> dict:
    """
    Fetches live GitHub data and returns behavioral score + metadata.

    Returns dict:
    - score (float): 0.0 to 100.0
    - public_repos (int)
    - followers (int)
    - repo_score (float)
    - follower_score (float)
    - status (str): "success", "not_found", "rate_limited", "no_username", "error"
    """
    default_response = {
        "score"        : NEUTRAL_SCORE,
        "public_repos" : 0,
        "followers"    : 0,
        "repo_score"   : 0,
        "follower_score": 0,
        "status"       : "no_username",
    }

    if not github_username or not github_username.strip():
        return default_response

    username = github_username.strip()
    api_url  = GITHUB_API_URL.format(username=username)

    try:
        response = requests.get(
            api_url,
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": "CandidateRankingPlatform/1.0",
                "Accept"    : "application/vnd.github.v3+json",
            }
        )

        if response.status_code == 404:
            default_response["status"] = "not_found"
            return default_response

        if response.status_code == 403:
            default_response["status"] = "rate_limited"
            return default_response

        if response.status_code != 200:
            default_response["status"] = "error"
            return default_response

        data         = response.json()
        public_repos = data.get("public_repos", 0)
        followers    = data.get("followers",    0)

        repo_score     = min(public_repos * POINTS_PER_REPO,     MAX_REPO_SCORE)
        follower_score = min(followers    * POINTS_PER_FOLLOWER,  MAX_FOLLOWER_SCORE)
        total_score    = repo_score + follower_score

        return {
            "score"         : round(float(total_score), 2),
            "public_repos"  : public_repos,
            "followers"     : followers,
            "repo_score"    : repo_score,
            "follower_score": follower_score,
            "status"        : "success",
        }

    except requests.exceptions.ConnectionError:
        default_response["status"] = "connection_error"
        return default_response
    except requests.exceptions.Timeout:
        default_response["status"] = "timeout"
        return default_response
    except Exception as e:
        logger.error(f"Layer 5: Unexpected error — {e}")
        default_response["status"] = "error"
        return default_response
