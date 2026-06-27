
# ============================================================
# backend/layer_3_experience.py — Enhanced Experience Engine
# ============================================================
# SIGNAL 1 — NLP Date Extraction (60% weight):
#   Automatically parses work history dates directly from
#   resume text using regex + dateutil. No manual input needed.
#   Calculates actual total months worked across all positions.
#
# SIGNAL 2 — Seniority Classification (40% weight):
#   Reads linguistic signals in the resume to classify the
#   candidate as Junior / Mid / Senior / Staff / Executive.
#   Maps each level to a numeric score and compares against
#   the JD's expected seniority level (derived from required_years).
#
# COMPOSITE:
#   final = (date_score * 0.6) + (seniority_score * 0.4)
# ============================================================
import spacy
import re
import logging
from datetime import datetime
try:
    import dateutil.parser as dateutil_parser
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False

try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except Exception:
    nlp = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# SENIORITY LEVEL DEFINITIONS
# ============================================================
# Each level has:
# - signals: keywords that indicate this level in resume text
# - score:   numeric value (0-100) for scoring
# - min_years: typical minimum years for this level
# ============================================================

SENIORITY_LEVELS = {
    "junior": {
        "signals"  : [
            "intern", "internship", "graduate", "entry level", "entry-level",
            "junior", "associate", "trainee", "fresher", "beginner",
            "0-1 year", "1 year", "less than 2", "recently graduated",
        ],
        "score"    : 20,
        "min_years": 0,
    },
    "mid": {
        "signals"  : [
            "software engineer", "developer", "analyst", "specialist",
            "2 years", "3 years", "4 years", "mid-level", "mid level",
            "intermediate", "full stack", "full-stack",
        ],
        "score"    : 50,
        "min_years": 2,
    },
    "senior": {
        "signals"  : [
            "senior", "sr.", "lead engineer", "tech lead", "technical lead",
            "5 years", "6 years", "7 years", "8 years", "principal",
            "mentor", "mentored", "led a team", "led team",
        ],
        "score"    : 75,
        "min_years": 5,
    },
    "staff": {
        "signals"  : [
            "staff engineer", "staff developer", "distinguished",
            "fellow", "10 years", "9 years", "architect",
            "solutions architect", "system architect", "platform lead",
        ],
        "score"    : 90,
        "min_years": 9,
    },
    "executive": {
        "signals"  : [
            "vp", "vice president", "cto", "chief technology",
            "head of engineering", "director of engineering",
            "engineering manager", "15 years", "20 years",
        ],
        "score"    : 100,
        "min_years": 12,
    },
}

# Maps required_years to expected seniority level
# Used to derive what level the JD is targeting
YEARS_TO_SENIORITY = {
    (0, 1) : "junior",
    (2, 4) : "mid",
    (5, 8) : "senior",
    (9, 11): "staff",
    (12, 99): "executive",
}

# ============================================================
# REGEX PATTERNS for date range detection
# ============================================================
MONTH_NAMES = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)

DATE_PATTERNS = [
    re.compile(rf"({MONTH_NAMES}\s+\d{{4}})\s*[-–—]+\s*({MONTH_NAMES}\s+\d{{4}}|[Pp]resent|[Cc]urrent|[Nn]ow)", re.IGNORECASE),
    re.compile(r"(\b\d{4})\s*[-–—]+\s*(\d{4}|[Pp]resent|[Cc]urrent|[Nn]ow)", re.IGNORECASE),
    re.compile(r"(\b20\d{2}|19\d{2})-(\d{4}|[Pp]resent|[Cc]urrent)", re.IGNORECASE),
]


# ============================================================
# HELPER: NLP DATE EXTRACTION
# ============================================================

def extract_years_from_resume(resume_text: str) -> dict:
    """
    Parses work history date ranges from resume text automatically.
    Looks for patterns like:
      - "Jan 2019 - Mar 2022"
      - "2018 - Present"
      - "March 2020 – Current"
      - "2016–2019"

    Args:
        resume_text (str): Raw resume text.

    Returns:
        dict:
          - total_months (int): Total months of professional experience
          - total_years  (float): Rounded to 1 decimal place
          - positions    (int): Number of date ranges found
          - extracted    (list): Raw date strings found
    """
    if not resume_text or not resume_text.strip():
        return {"total_months": 0, "total_years": 0.0, "positions": 0, "extracted": []}

    parsed_intervals = []
    found_ranges = []
    now          = datetime.now()

    if nlp is not None:
        doc = nlp(resume_text)
        date_ents = [ent for ent in doc.ents if ent.label_ == "DATE"]
        
        i = 0
        while i < len(date_ents):
            ent_text = date_ents[i].text
            
            # Case 1: Entity itself contains a range (e.g. "Fall 2019 to Spring 2022")
            parts = re.split(r'\s*(?:to|until|-|–|—)\s*', ent_text, flags=re.IGNORECASE)
            if len(parts) == 2:
                start_str, end_str = parts[0].strip(), parts[1].strip()
                i += 1
            elif i + 1 < len(date_ents):
                # Case 2: Consecutive DATE entities separated by range markers
                start_ent = date_ents[i]
                end_ent = date_ents[i+1]
                between_text = doc.text[start_ent.end_char:end_ent.start_char].strip().lower()
                
                # Check for "Present" / "Current" which might not be tagged as DATE
                if between_text in ["-", "–", "—", "to", "until"]:
                    start_str = start_ent.text
                    end_str = end_ent.text
                    i += 2
                else:
                    # Check if the text immediately following start_ent is "- Present"
                    trailing_text = doc.text[start_ent.end_char:start_ent.end_char + 15].strip().lower()
                    if re.match(r'^(?:-|–|—|to)\s*(?:present|current|now)', trailing_text):
                        start_str = start_ent.text
                        end_str = "Present"
                        i += 1
                    else:
                        i += 1
                        continue
            else:
                # Check trailing text for "Present" on the last entity
                trailing_text = doc.text[date_ents[i].end_char:date_ents[i].end_char + 15].strip().lower()
                if re.match(r'^(?:-|–|—|to)\s*(?:present|current|now)', trailing_text):
                    start_str = date_ents[i].text
                    end_str = "Present"
                else:
                    i += 1
                    continue
                i += 1
            
            try:
                # Parse start date
                if DATEUTIL_AVAILABLE:
                    start = dateutil_parser.parse(start_str, default=datetime(now.year, 1, 1))
                else:
                    year_match = re.search(r"\d{4}", start_str)
                    if not year_match: continue
                    start = datetime(int(year_match.group()), 1, 1)

                # Parse end date
                if re.match(r"[Pp]resent|[Cc]urrent|[Nn]ow", end_str, re.IGNORECASE):
                    end = now
                else:
                    if DATEUTIL_AVAILABLE:
                        end = dateutil_parser.parse(end_str, default=datetime(now.year, 12, 1))
                    else:
                        year_match = re.search(r"\d{4}", end_str)
                        if not year_match: continue
                        end = datetime(int(year_match.group()), 12, 1)

                if start < end:
                    months = (end.year - start.year) * 12 + (end.month - start.month)
                    if 1 <= months <= 600:
                        parsed_intervals.append((start, end))
                        found_ranges.append(f"{start_str} → {end_str} ({months}mo)")
            except Exception:
                continue
    else:
        # Fallback to regex if spaCy failed to load
        for pattern in DATE_PATTERNS:
            matches = pattern.findall(resume_text)
            for start_str, end_str in matches:
                try:
                    # Parse start date
                    if DATEUTIL_AVAILABLE:
                        start = dateutil_parser.parse(start_str, default=datetime(now.year, 1, 1))
                    else:
                        year_match = re.search(r"\d{4}", start_str)
                        if not year_match: continue
                        start = datetime(int(year_match.group()), 1, 1)

                    # Parse end date
                    if re.match(r"[Pp]resent|[Cc]urrent|[Nn]ow", end_str, re.IGNORECASE):
                        end = now
                    else:
                        if DATEUTIL_AVAILABLE:
                            end = dateutil_parser.parse(end_str, default=datetime(now.year, 12, 1))
                        else:
                            year_match = re.search(r"\d{4}", end_str)
                            if not year_match: continue
                            end = datetime(int(year_match.group()), 12, 1)

                    if start < end:
                        months = (end.year - start.year) * 12 + (end.month - start.month)
                        if 1 <= months <= 600:
                            parsed_intervals.append((start, end))
                            found_ranges.append(f"{start_str} → {end_str} ({months}mo)")
                except Exception:
                    continue

    # Merge overlapping intervals to prevent double-counting
    total_months = 0
    if parsed_intervals:
        parsed_intervals.sort(key=lambda x: x[0])
        merged = [parsed_intervals[0]]
        for current in parsed_intervals[1:]:
            last = merged[-1]
            if current[0] <= last[1]:
                merged[-1] = (last[0], max(last[1], current[1]))
            else:
                merged.append(current)
        
        for start, end in merged:
            total_months += (end.year - start.year) * 12 + (end.month - start.month)

    # Deduplicate: cap at realistic maximum (40 years = 480 months)
    total_months = min(total_months, 480)

    return {
        "total_months": total_months,
        "total_years" : round(total_months / 12, 1),
        "positions"   : len(found_ranges),
        "extracted"   : found_ranges,
    }


# ============================================================
# HELPER: SENIORITY CLASSIFICATION
# ============================================================

def classify_seniority(resume_text: str) -> dict:
    """
    Classifies candidate seniority level from resume language.

    Scans for weighted keyword signals across all seniority
    levels. The level with the most signal hits wins.

    Args:
        resume_text (str): Raw resume text.

    Returns:
        dict:
          - level     (str):   "junior" | "mid" | "senior" | "staff" | "executive"
          - score     (int):   Numeric score for this level (0-100)
          - confidence(float): Signal hit rate (0.0 - 1.0)
          - hits      (dict):  Signal counts per level
    """
    text   = resume_text.lower()
    hits   = {level: 0 for level in SENIORITY_LEVELS}
    detail = {level: [] for level in SENIORITY_LEVELS}

    for level, config in SENIORITY_LEVELS.items():
        for signal in config["signals"]:
            if signal.lower() in text:
                hits[level]   += 1
                detail[level].append(signal)

    # Find winning level
    best_level = max(hits, key=hits.get)
    best_hits  = hits[best_level]
    total_signals = sum(len(c["signals"]) for c in SENIORITY_LEVELS.values())

    # If no signals found, default to "mid"
    if best_hits == 0:
        best_level = "mid"
        confidence = 0.0
    else:
        confidence = round(best_hits / len(SENIORITY_LEVELS[best_level]["signals"]), 3)

    return {
        "level"     : best_level,
        "score"     : SENIORITY_LEVELS[best_level]["score"],
        "confidence": confidence,
        "hits"      : hits,
        "signals"   : detail[best_level],
    }


# ============================================================
# HELPER: DATE-BASED EXPERIENCE SCORE
# ============================================================

def _score_from_dates(extracted_years: float, required_years: int) -> float:
    """
    Converts extracted years into a 0-100 score with hard ceiling.
    Identical ceiling logic to V1 for consistency.
    """
    if required_years == 0:
        return 100.0
    if extracted_years <= 0:
        return 0.0
    raw   = (extracted_years / required_years) * 100
    return round(min(raw, 100.0), 2)


# ============================================================
# HELPER: SENIORITY-BASED SCORE
# ============================================================

def _score_from_seniority(candidate_level: str, required_years: int) -> float:
    """
    Maps candidate seniority level against JD's expected level.

    Derives expected seniority from required_years, then
    scores how well the candidate's level aligns.

    Scoring matrix:
    - Exact match or above → 100.0
    - One level below      → 65.0
    - Two levels below     → 35.0
    - Three+ below         → 10.0
    """
    # Derive expected level from required years
    expected_level = "mid"  # default
    for (min_y, max_y), level in YEARS_TO_SENIORITY.items():
        if min_y <= required_years <= max_y:
            expected_level = level
            break

    # Build ordered list for comparison
    level_order = ["junior", "mid", "senior", "staff", "executive"]

    try:
        candidate_idx = level_order.index(candidate_level)
        expected_idx  = level_order.index(expected_level)
    except ValueError:
        return 50.0  # Unknown level → neutral

    diff = candidate_idx - expected_idx

    # Scoring by gap
    if diff >= 0:
        return 100.0   # Meets or exceeds expected level
    elif diff == -1:
        return 65.0    # One level below
    elif diff == -2:
        return 35.0    # Two levels below
    else:
        return 10.0    # Far below expected level


# ============================================================
# PUBLIC API
# ============================================================

def calculate_experience_score(
    candidate_years: int,
    required_years : int,
    resume_text    : str = "",
) -> dict:
    """
    Dual-signal experience scoring engine.

    Combines:
    - NLP date extraction from resume text  (60% weight)
    - Seniority level classification        (40% weight)

    Falls back to manual candidate_years if NLP extraction
    finds no dates in the resume text.

    Args:
        candidate_years (int): Manually entered years (fallback).
        required_years  (int): JD minimum years requirement.
        resume_text     (str): Full resume text for NLP extraction.

    Returns:
        dict:
          - score              (float): Final composite 0.0-100.0
          - date_score         (float): Score from NLP date extraction
          - seniority_score    (float): Score from level classification
          - extracted_years    (float): Years parsed from resume text
          - seniority_level    (str):   Detected seniority level
          - seniority_confidence(float): Confidence of classification
          - extraction_method  (str):   "nlp" | "manual" | "combined"
          - positions_found    (int):   Number of date ranges extracted
          - date_ranges        (list):  Raw extracted date strings
    """
    # ----------------------------------------------------------
    # EDGE CASES
    # ----------------------------------------------------------
    if required_years == 0:
        return {
            "score"               : 100.0,
            "date_score"          : 100.0,
            "seniority_score"     : 100.0,
            "extracted_years"     : float(candidate_years),
            "seniority_level"     : "unknown",
            "seniority_confidence": 0.0,
            "extraction_method"   : "no_requirement",
            "positions_found"     : 0,
            "date_ranges"         : [],
        }

    # ----------------------------------------------------------
    # SIGNAL 1: NLP DATE EXTRACTION
    # ----------------------------------------------------------
    extraction  = extract_years_from_resume(resume_text)
    nlp_years   = extraction["total_years"]
    positions   = extraction["positions"]
    date_ranges = extraction["extracted"]

    # Decide source: use NLP if it found dates, else fall back to manual
    if nlp_years > 0:
        effective_years    = nlp_years
        extraction_method  = "nlp"
        logger.info(
            f"Layer 3: NLP extracted {nlp_years} years "
            f"from {positions} positions: {date_ranges}"
        )
    else:
        effective_years   = float(candidate_years)
        extraction_method = "manual"
        logger.info(
            f"Layer 3: No dates found in resume text. "
            f"Using manual input: {candidate_years} years."
        )

    date_score = _score_from_dates(effective_years, required_years)

    # ----------------------------------------------------------
    # SIGNAL 2: SENIORITY CLASSIFICATION
    # ----------------------------------------------------------
    seniority       = classify_seniority(resume_text)
    seniority_score = _score_from_seniority(seniority["level"], required_years)

    logger.info(
        f"Layer 3: Seniority detected = '{seniority['level']}' "
        f"(confidence: {seniority['confidence']}) → score: {seniority_score}"
    )

    # ----------------------------------------------------------
    # COMPOSITE SCORE
    # ----------------------------------------------------------
    # Weight: 60% date extraction, 40% seniority classification
    # Rationale: objective dates are more reliable than
    # linguistic signals which can vary by writing style.
    composite = (date_score * 0.60) + (seniority_score * 0.40)
    composite = round(min(composite, 100.0), 2)

    if nlp_years > 0:
        extraction_method = "combined"

    logger.info(
        f"Layer 3: date_score={date_score} × 0.6 + "
        f"seniority_score={seniority_score} × 0.4 = {composite}"
    )

    return {
        "score"               : composite,
        "date_score"          : date_score,
        "seniority_score"     : seniority_score,
        "extracted_years"     : effective_years,
        "seniority_level"     : seniority["level"],
        "seniority_confidence": seniority["confidence"],
        "extraction_method"   : extraction_method,
        "positions_found"     : positions,
        "date_ranges"         : date_ranges,
    }
