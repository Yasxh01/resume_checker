# ============================================================
# backend/layer_5_behavioral.py — Enhanced Behavioral Engine v2
# ============================================================
# All-Signal GitHub Intelligence
#
# SIGNAL 1 — Repository & Follower Score (30% weight):
#   Original V1 scoring — public repos and followers.
#   Still valuable as a baseline activity indicator.
#
# SIGNAL 2 — Contribution Pattern Analysis (40% weight):
#   Fetches live public events from GitHub API to measure:
#   - Total commits in last 30 days
#   - Number of unique active coding days
#   - Consistency score (active days / 30)
#   - Average commits per push (measures commit discipline)
#   This is the strongest behavioral signal — it shows
#   CURRENT, SUSTAINED coding activity, not just a resume claim.
#
# SIGNAL 3 — Code Quality Signals (30% weight):
#   Aggregates stars, forks, documentation rate, and recent
#   activity across all repos to measure peer validation and
#   professional coding discipline.
#
# COMPOSITE:
#   final = (repo_follower × 0.30) + (contribution × 0.40) + (quality × 0.30)
#
# FALLBACK:
#   Returns 50.0 (neutral) for any signal that fails.
#   An empty username returns 50.0 overall — never penalises.
# ============================================================

import os
import math
import logging
import asyncio
import httpx
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
NEUTRAL_SCORE    = 50.0
RECENT_CUTOFF = datetime.now(timezone.utc) - timedelta(days=365)

# Signal weights (must sum to 1.0)
WEIGHT_REPO_FOLLOWER  = 0.30
WEIGHT_CONTRIBUTION   = 0.40
WEIGHT_CODE_QUALITY   = 0.30

POINTS_PER_REPO       = 2
MAX_REPO_SCORE        = 50
POINTS_PER_FOLLOWER   = 5
MAX_FOLLOWER_SCORE    = 50


# ============================================================
# SHARED REQUEST HELPER
# ============================================================
async def _github_get(client: httpx.AsyncClient, url: str, params: dict = None) -> dict | list | None:
    """
    Makes an async GET request to the GitHub API with standard headers.
    Returns parsed JSON or None on any failure.
    """
    cache_key = f"{url}?{params}"
    if cache_key in _github_cache:
        return _github_cache[cache_key]

    headers = {
        "User-Agent": "CandidateRankingPlatform/2.0",
        "Accept"    : "application/vnd.github.v3+json",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    try:
        response = await client.get(url, params=params or {}, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            _github_cache[cache_key] = data
            return data
        logger.warning(f"Layer 5: GitHub GET {url} → {response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"Layer 5: GitHub GET failed — {e}")
        return None


# ============================================================
# SIGNAL 1: Repository & Follower Score 
# ============================================================
def _score_repo_followers(profile: dict) -> dict:
    """
    Original V1 scoring using public_repos and followers count.

    Scoring:
      repo_score     = min(public_repos × 2, 50)
      follower_score = min(followers    × 5, 50)
      total          = repo_score + follower_score  (max 100)

    Args:
        profile (dict): GitHub user profile JSON

    Returns:
        dict: score, public_repos, followers, repo_pts, follower_pts
    """
    public_repos   = profile.get("public_repos", 0)
    followers      = profile.get("followers",    0)

    repo_pts       = min(public_repos * POINTS_PER_REPO,     MAX_REPO_SCORE)
    follower_pts   = min(followers    * POINTS_PER_FOLLOWER,  MAX_FOLLOWER_SCORE)
    total          = round(float(repo_pts + follower_pts), 2)

    logger.info(
        f"Layer 5 (Repo/Follower): repos={public_repos}→{repo_pts}pts, "
        f"followers={followers}→{follower_pts}pts = {total}/100"
    )

    return {
        "score"      : total,
        "public_repos": public_repos,
        "followers"  : followers,
        "repo_pts"   : repo_pts,
        "follower_pts": follower_pts,
    }


# ============================================================
# SIGNAL 2: Contribution Pattern Analysis
# ============================================================
async def _score_contribution_patterns(client: httpx.AsyncClient, username: str) -> dict:
    """
    Analyses commit frequency and consistency from public events.

    GitHub's Events API returns up to 90 days of public activity.
    We look at PushEvents (code commits) to measure:

    Metrics:
    - total_commits:     Raw commit count in window
    - active_days:       Unique calendar days with commits
    - consistency_score: active_days / 30 × 100 (normalized to 30 days)
    - avg_commits_push:  Commit discipline indicator

    Scoring breakdown (max 100):
    - Consistency (active days): 50 pts max  ← most important
    - Commit volume:             30 pts max
    - Discipline (commits/push): 20 pts max
    """
    events_url = f"{GITHUB_API_BASE}/users/{username}/events/public"
    events     = await _github_get(client, events_url, params={"per_page": 100})

    if not events or not isinstance(events, list):
        logger.warning(f"Layer 5: No events found for '{username}'. Returning neutral.")
        return {
            "score"             : NEUTRAL_SCORE,
            "total_commits"     : 0,
            "active_days"       : 0,
            "consistency_score" : 0.0,
            "avg_commits_push"  : 0.0,
            "push_events"       : 0,
            "persona"           : "Unknown",
            "status"            : "no_events",
        }

    # Filter to only push events (actual code commits)
    push_events = [e for e in events if e.get("type") == "PushEvent"]

    if not push_events:
        return {
            "score"             : NEUTRAL_SCORE,
            "total_commits"     : 0,
            "active_days"       : 0,
            "consistency_score" : 0.0,
            "avg_commits_push"  : 0.0,
            "push_events"       : 0,
            "persona"           : "Unknown",
            "status"            : "no_push_events",
        }

    # Count commits per push event
    commit_counts = [
        len(e.get("payload", {}).get("commits", []))
        for e in push_events
    ]
    total_commits = sum(commit_counts)

    # Count unique active days and time of day
    active_day_set = set()
    night_commits = 0
    day_commits = 0

    for e in push_events:
        created_at = e.get("created_at")
        if created_at:
            active_day_set.add(created_at[:10])
            try:
                hour = int(created_at[11:13])
                if hour >= 22 or hour <= 4:
                    night_commits += 1
                else:
                    day_commits += 1
            except Exception:
                pass

    active_days = len(active_day_set)
    
    if night_commits > day_commits and night_commits > 0:
        persona = "Midnight Hacker 🦉"
    elif day_commits > 0:
        persona = "9-to-5 Corporate ☕"
    else:
        persona = "Unknown"

    # Consistency: normalize over 30 days (cap at 30 to handle high-activity devs)
    consistency_score = min(active_days / 30, 1.0) * 100

    # Average commits per push (discipline indicator)
    # Clean coders make focused commits (5-10 per push is healthy)
    avg_commits = total_commits / max(len(push_events), 1)

    # ----------------------------------------------------------
    # SCORING
    # ----------------------------------------------------------

    # Consistency score (50 pts): most important signal
    # 10+ active days = near max
    consistency_pts = min(active_days / 10, 1.0) * 50

    # Volume score (30 pts): log-scale to not over-reward bursty coders
    # 50+ commits → 30 pts, 10 commits → ~21 pts
    volume_pts = min((math.log1p(total_commits) / math.log1p(50)) * 30, 30)

    # Discipline score (20 pts): avg 3-15 commits per push = disciplined
    if 3 <= avg_commits <= 15:
        discipline_pts = 20.0
    elif avg_commits < 3:
        discipline_pts = (avg_commits / 3) * 20
    else:
        # Very large pushes suggest bulk uploads, less discipline
        discipline_pts = max(0, 20 - (avg_commits - 15) * 0.5)

    discipline_pts = min(discipline_pts, 20.0)

    total_score = round(
        min(consistency_pts + volume_pts + discipline_pts, 100.0), 2
    )

    logger.info(
        f"Layer 5 (Contribution): commits={total_commits}, "
        f"active_days={active_days}, avg_per_push={round(avg_commits,1)} → "
        f"consistency={round(consistency_pts,1)} + "
        f"volume={round(volume_pts,1)} + "
        f"discipline={round(discipline_pts,1)} = {total_score}/100"
    )

    return {
        "score"             : total_score,
        "total_commits"     : total_commits,
        "active_days"       : active_days,
        "consistency_score" : round(consistency_score, 1),
        "avg_commits_push"  : round(avg_commits, 1),
        "push_events"       : len(push_events),
        "persona"           : persona,
        "consistency_pts"   : round(consistency_pts, 1),
        "volume_pts"        : round(volume_pts, 1),
        "discipline_pts"    : round(discipline_pts, 1),
        "status"            : "success",
    }


# ============================================================
# SIGNAL 3: Code Quality Analysis
# ============================================================
async def _score_code_quality(client: httpx.AsyncClient, username: str) -> dict:
    """
    Evaluates peer-validated code quality from repository metadata.

    Signals:
    - Stars (max 30):          Community recognition (log scale)
    - Forks (max 25):          Others built on their work (linear scale)
    - Documentation (max 20):  % of repos with descriptions
    - Activity (max 25):       % of original repos updated recently

    Args:
        username (str): GitHub username

    Returns:
        dict: score, total_stars, total_forks, etc.
    """
    repos_url = f"{GITHUB_API_BASE}/users/{username}/repos"
    repos     = await _github_get(client, repos_url, params={"per_page": 30, "sort": "updated", "type": "owner"})

    if not repos or not isinstance(repos, list):
        return {
            "score"            : NEUTRAL_SCORE,
            "total_stars"      : 0,
            "total_forks"      : 0,
            "documented_repos" : 0,
            "recently_active"  : 0,
            "documentation_pct": 0.0,
            "activity_pct"     : 0.0,
            "status"           : "no_repos",
        }

    total_repos = len(repos)

    # Aggregate metrics
    total_stars      = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks      = sum(r.get("forks_count", 0) for r in repos)
    documented       = sum(
        1 for r in repos
        if r.get("description") and len(r["description"].strip()) > 5
    )
    recently_active  = sum(
        1 for r in repos
        if (
            r.get("updated_at", "")
             and datetime.fromisoformat(
                 r["updated_at"].replace("Z","+00:00")
             ) >= RECENT_CUTOFF
               and not r.get("fork", False)
        )
    )

    # Stars: log-scale (100 stars = max 30 pts)
    star_score   = min((math.log1p(total_stars) / math.log1p(100)) * 30, 30.0)

    # Forks: linear (10 forks = max 25 pts)
    fork_score   = min((total_forks / 10) * 25, 25.0)

    # Documentation: % of repos with descriptions
    doc_pct      = documented / total_repos
    doc_score    = doc_pct * 20

    # Activity: % of original repos updated recently
    active_pct   = recently_active / total_repos
    active_score = active_pct * 25

    total_score = round(
        min(star_score + fork_score + doc_score + active_score, 100.0), 2
    )

    logger.info(
        f"Layer 5 (Code Quality): stars={total_stars}→{round(star_score,1)}, "
        f"forks={total_forks}→{round(fork_score,1)}, "
        f"docs={round(doc_pct*100)}%→{round(doc_score,1)}, "
        f"active={round(active_pct*100)}%→{round(active_score,1)} = {total_score}/100"
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
        "repos_total"      : total_repos,
        "status"           : "success",
    }


# ============================================================
# PUBLIC API
# ============================================================
async def calculate_github_score(github_username: str) -> dict:
    """
    All-signal GitHub behavioral intelligence engine.

    Combines three independent signals:
    - Signal 1: Repo count + follower count  (30%)
    - Signal 2: Contribution pattern analysis (40%)
    - Signal 3: Code quality signals          (30%)

    Args:
        github_username (str): GitHub username. Empty = neutral score.

    Returns:
        dict:
          - score               (float): Final composite 0.0–100.0
          - repo_follower_score (float): Signal 1 score
          - contribution_score  (float): Signal 2 score
          - quality_score       (float): Signal 3 score
          - public_repos        (int)
          - followers           (int)
          - total_commits       (int):   Recent commit count
          - active_days         (int):   Unique days with commits
          - consistency_score   (float): % of days active (0-100)
          - total_stars         (int)
          - total_forks         (int)
          - status              (str)
    """
    # ----------------------------------------------------------
    # EDGE CASE: No username
    # ----------------------------------------------------------
    if not github_username or not github_username.strip():
        logger.info(f"Layer 5: No username — returning neutral {NEUTRAL_SCORE}.")
        return {
            "score"               : NEUTRAL_SCORE,
            "repo_follower_score" : NEUTRAL_SCORE,
            "contribution_score"  : NEUTRAL_SCORE,
            "quality_score"       : NEUTRAL_SCORE,
            "public_repos"        : 0,
            "followers"           : 0,
            "total_commits"       : 0,
            "active_days"         : 0,
            "consistency_score"   : 0.0,
            "avg_commits_push"    : 0.0,
            "total_stars"         : 0,
            "total_forks"         : 0,
            "documented_repos"    : 0,
            "recently_active"     : 0,
            "repos_total"         : 0,
            "status"              : "no_username",
        }

    username = github_username.strip()

    # ----------------------------------------------------------
    # FETCH ALL DATA CONCURRENTLY
    # ----------------------------------------------------------
    logger.info(f"Layer 5: Running all 3 signals concurrently for '{username}'...")
    
    async with httpx.AsyncClient() as client:
        profile_url = f"{GITHUB_API_BASE}/users/{username}"
        
        # Launch tasks concurrently
        profile_task = _github_get(client, profile_url)
        contrib_task = _score_contribution_patterns(client, username)
        quality_task = _score_code_quality(client, username)
        
        profile, s2, s3 = await asyncio.gather(profile_task, contrib_task, quality_task)

    if not profile:
        logger.warning(f"Layer 5: Profile not found for '{username}'. Returning neutral.")
        return {
            "score"               : NEUTRAL_SCORE,
            "repo_follower_score" : NEUTRAL_SCORE,
            "contribution_score"  : NEUTRAL_SCORE,
            "quality_score"       : NEUTRAL_SCORE,
            "public_repos"        : 0,
            "followers"           : 0,
            "total_commits"       : 0,
            "active_days"         : 0,
            "consistency_score"   : 0.0,
            "avg_commits_push"    : 0.0,
            "total_stars"         : 0,
            "total_forks"         : 0,
            "documented_repos"    : 0,
            "recently_active"     : 0,
            "repos_total"         : 0,
            "persona"             : "Unknown",
            "status"              : "not_found",
        }

    s1 = _score_repo_followers(profile)

    # ----------------------------------------------------------
    # COMPOSITE SCORE
    # ----------------------------------------------------------
    composite = (
        s1["score"] * WEIGHT_REPO_FOLLOWER +
        s2["score"] * WEIGHT_CONTRIBUTION  +
        s3["score"] * WEIGHT_CODE_QUALITY
    )
    composite = round(min(composite, 100.0), 2)

    logger.info(
        f"Layer 5: Final composite = "
        f"repo_follower({s1['score']}) × {WEIGHT_REPO_FOLLOWER} + "
        f"contribution({s2['score']}) × {WEIGHT_CONTRIBUTION} + "
        f"quality({s3['score']}) × {WEIGHT_CODE_QUALITY} "
        f"= {composite}"
    )

    return {
        "score"               : composite,
        "repo_follower_score" : s1["score"],
        "contribution_score"  : s2["score"],
        "quality_score"       : s3["score"],
        "public_repos"        : s1["public_repos"],
        "followers"           : s1["followers"],
        "repo_pts"            : s1["repo_pts"],
        "follower_pts"        : s1["follower_pts"],
        "total_commits"       : s2["total_commits"],
        "active_days"         : s2.get("active_days", 0),
        "consistency_score"   : s2.get("consistency_score", 0.0),
        "avg_commits_push"    : s2.get("avg_commits_push", 0.0),
        "persona"             : s2.get("persona", "Unknown"),
        "push_events"         : s2["push_events"],
        "consistency_pts"     : s2.get("consistency_pts", 0),
        "volume_pts"          : s2.get("volume_pts", 0),
        "discipline_pts"      : s2.get("discipline_pts", 0),
        "total_stars"         : s3["total_stars"],
        "total_forks"         : s3["total_forks"],
        "documented_repos"    : s3["documented_repos"],
        "recently_active"     : s3["recently_active"],
        "documentation_pct"   : s3["documentation_pct"],
        "activity_pct"        : s3["activity_pct"],
        "repos_total"         : s3.get("repos_total", 0),
        "star_score"          : s3.get("star_score", 0),
        "fork_score"          : s3.get("fork_score", 0),
        "doc_score"           : s3.get("doc_score", 0),
        "active_score"        : s3.get("active_score", 0),
        "status"              : "success",
    }
