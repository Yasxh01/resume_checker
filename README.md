# 🎯 RecruitIQ — AI-Powered Candidate Ranking Platform

> A production-grade, multi-layer hybrid scoring pipeline that ranks candidates by **meaning**, not keywords — combining neural semantic embeddings, skill taxonomy resolution, NLP-based experience extraction, live GitHub analysis, and Gemini LLM verdicts into a single transparent composite score.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Why RecruitIQ](#why-recruitiq)
- [Architecture](#architecture)
- [The 5-Layer Pipeline](#the-5-layer-pipeline)
- [Features](#features)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Setup & Installation](#setup--installation)
- [Configuration (.env)](#configuration-env)
- [Running the Application](#running-the-application)
- [API Reference](#api-reference)
- [Scoring Formula](#scoring-formula)
- [Bias Detection Engine](#bias-detection-engine)
- [Resume Parser](#resume-parser)
- [LLM Integration](#llm-integration)
- [Frontend Pages](#frontend-pages)
- [Mock Data & JD Templates](#mock-data--jd-templates)
- [Performance Optimisations](#performance-optimisations)

---

## Overview

RecruitIQ is a full-stack AI candidate ranking platform built with **FastAPI** on the backend and **Vanilla HTML/CSS/JavaScript** on the frontend. It evaluates every resume through five independent scoring layers — semantic meaning, skill taxonomy, professional timeline, portfolio quality, and live GitHub behavioral signals — then combines them into a single explainable composite score.

The system accepts a Job Description and a list of candidates (manual entry or PDF upload), runs all evaluations **concurrently** using `asyncio.gather`, sorts the results, flags potential hiring biases, and optionally generates **Gemini 2.5 Flash** LLM verdicts and personalised interview questions.

---

## Why RecruitIQ

Traditional ATS systems fail in predictable ways:

| Problem | How RecruitIQ Solves It |
|---|---|
| "AWS" vs "Amazon Web Services" treated as different skills | 140+ alias taxonomy map + `difflib` fuzzy matching resolves both to the same canonical skill |
| Years of experience is self-reported and easy to fake | spaCy NER extracts actual date ranges from resume text and computes real months worked |
| Keyword-matching penalises unconventional writing styles | BAAI/bge-small-en-v1.5 neural embeddings measure conceptual alignment, not word frequency |
| GitHub profile ignored entirely | Async GitHub API fetches repos, languages, topics, commit history, and code quality signals |
| No explanation for why a candidate ranked where they did | Every score broken down by layer; matched/missing skills listed; LLM generates human-readable verdict |
| Strong junior candidates rejected because of experience threshold | Bias detection engine flags "High-Potential Junior" profiles for human review |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (HTML/CSS/JS)                    │
│  index.html · layer1-6.html · styles.css · app.js           │
│  Chart.js radar charts · Dark/light theme · PDF drag-drop   │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP (fetch API)
┌─────────────────────▼───────────────────────────────────────┐
│                  FastAPI + Uvicorn                           │
│                      main.py                                │
│  POST /api/evaluate  ·  POST /api/upload-resume             │
│  POST /api/verdict   ·  POST /api/interview-questions       │
│  GET  /api/export-csv · GET /api/job-descriptions           │
└──────┬──────────┬──────────┬──────────┬────────┬────────────┘
       │          │          │          │        │
       ▼          ▼          ▼          ▼        ▼
  ┌─────────┐ ┌────────┐ ┌──────┐ ┌────────┐ ┌────────┐
  │ Layer 1 │ │Layer 2 │ │  L3  │ │ Layer 4│ │Layer 5 │
  │Semantic │ │Taxonomy│ │ Exp  │ │Projects│ │ GitHub │
  └─────────┘ └────────┘ └──────┘ └────────┘ └────────┘
       │                              │             │
  BAAI embed                    GitHub REST    GitHub REST
  + TF-IDF                      API (httpx)    API (httpx)
  + LRU cache                   async          3 signals
                                               concurrent
```

---

## The 5-Layer Pipeline

### Layer 1 — Semantic Match (`backend/layer_1_semantic.py`)

**Model:** `BAAI/bge-small-en-v1.5` (384-dimensional embeddings)

**How it works:**
1. Both JD and resume text are preprocessed — HTML tags stripped, boilerplate phrases removed, whitespace collapsed
2. JD is encoded once and cached via `@lru_cache(maxsize=128)` keyed by SHA-256 hash
3. Resume text is split into overlapping chunks (`chunk_size=400`, `overlap=50 words`)
4. All chunks are encoded in a single batch call
5. Cosine similarity computed between JD vector and **every** chunk — the **maximum** similarity is taken (best-window strategy)
6. TF-IDF cosine similarity (bigrams, 8000 features) is **always** computed as a parallel signal
7. Final score is blended: `neural × 0.75 + tfidf × 0.25`

**Fallback:** If the neural model fails to load, returns TF-IDF score only.

**Score range:** 0.0 – 100.0

---

### Layer 2 — Skill Taxonomy (`backend/layer_2_taxonomy.py`)

**How it works:**
1. Both JD skills and candidate skills are normalised through a **140+ entry `TAXONOMY_MAP`**
   - Example: `"drf"` → `"django"`, `"k8s"` → `"kubernetes"`, `"amazon web services"` → `"aws"`
2. Normalised skill sets are intersected: `matched = jd_skills ∩ candidate_skills`
3. Any skills remaining in `missing_set` are checked via `difflib.get_close_matches(cutoff=0.90)` for fuzzy resolution
4. Score = `|matched| / |jd_skills| × 100`

**Returns:** `score`, `matched[]`, `missing[]`, `normalized_jd[]`, `normalized_candidate[]`

**Score range:** 0.0 – 100.0

---

### Layer 3 — Experience Scoring (`backend/layer_3_experience.py`)

**Dual-signal scoring (not a simple year ratio):**

**Signal 1 — NLP Date Extraction (60% weight):**
- spaCy `en_core_web_sm` NER identifies DATE entities in raw resume text
- Consecutive DATE entities separated by `-`, `–`, `to`, `until` are paired as work intervals
- `"Present"` / `"Current"` end dates are mapped to `datetime.now()`
- Overlapping intervals are **merged** to prevent double-counting
- Falls back to regex patterns if spaCy is unavailable
- `dateutil.parser` handles flexible date formats: `"Jan 2019"`, `"2018"`, `"March 2020"`
- Capped at 480 months (40 years) maximum

**Signal 2 — Seniority Classification (40% weight):**
- 50+ keyword signals mapped to 5 levels: `junior / mid / senior / staff / executive`
- Expected level derived from `required_years`
- Scoring gap: exact match or above → 100.0, one level below → 65.0, two below → 35.0, three+ below → 10.0

**Composite:** `(date_score × 0.60) + (seniority_score × 0.40)`

**Returns:** `score`, `date_score`, `seniority_score`, `extracted_years`, `seniority_level`, `seniority_confidence`, `extraction_method`, `positions_found`, `date_ranges[]`

---

### Layer 4 — Project Relevance (`backend/layer_4_projects.py`)

**Two paths depending on whether a GitHub username is provided:**

**Path A — GitHub API Analysis (when username exists):**

*Signal 1: Skill Match Score (50%)*
- Fetches all repo languages concurrently via `asyncio.gather`
- Aggregates language bytes across all repos
- Collects repo topics (e.g. `"django"`, `"aws"`)
- Intersects candidate tech fingerprint with normalised JD skills
- Score = `|matched| / |jd_skills| × 100`

*Signal 2: Code Quality Score (50%)*
- **Stars** (log-scale, max 30pts): `log(stars+1) / log(101) × 30`
- **Forks** (linear, max 25pts): `forks / 10 × 25`
- **Documentation** (max 20pts): % of repos with descriptions × 20
- **Recent Activity** (max 25pts): % of non-fork repos updated within last 365 days × 25

**Path B — Semantic Fallback (no GitHub username):**
- TF-IDF cosine similarity between JD text and `projects_text`
- Falls back further to 0.0 if projects_text is empty

**Caching:** All GitHub API responses cached in-memory (`_github_cache` dict) per session.

---

### Layer 5 — GitHub Behavioral Intelligence (`backend/layer_5_behavioral.py`)

**Three signals fetched concurrently via `asyncio.gather`:**

**Signal 1 — Repo & Follower Score (30%):**
- `repo_score = min(public_repos × 2, 50)`
- `follower_score = min(followers × 5, 50)`
- Total max: 100 pts

**Signal 2 — Contribution Pattern Analysis (40%):**
- Fetches up to 100 public events from GitHub Events API
- Filters to `PushEvent` types only
- Counts: `total_commits`, `active_days`, `avg_commits_per_push`
- **Consistency points** (max 50): `min(active_days / 10, 1.0) × 50`
- **Volume points** (max 30): `log(commits+1) / log(51) × 30`
- **Discipline points** (max 20): 20 pts for 3–15 avg commits/push, tapered outside range


**Signal 3 — Code Quality (30%):**
- Same star/fork/docs/activity signals as Layer 4
- Applied to the user's full repo list

**Composite:** `S1 × 0.30 + S2 × 0.40 + S3 × 0.30`

**Neutral fallback (50.0):** Returned when username is empty, profile not found, or API fails — never penalises candidates for missing data.

---

## Features

- **PDF Resume Upload** — pdfplumber extracts text and embedded hyperlinks; `resume_parser.py` auto-fills name, email, GitHub username, phone, LinkedIn, portfolio URLs, skills, projects, and years of experience
- **Multi-JD Mode** — 3 built-in JD templates (Python Backend, Full-Stack JS, ML Engineer); switch roles and re-rank instantly
- **Concurrent Evaluation** — all candidates scored in parallel via `asyncio.gather`; wall-clock time ≈ single-candidate time for N candidates
- **Adjustable Layer Weights** — 5 sliders; weights auto-normalised to sum to 1.0
- **Bias Detection Engine** — 5 automated fairness flags (see section below)
- **Gemini LLM Verdicts** — 2-3 sentence professional hiring recommendation via Gemini 2.5 Flash; deterministic rule-based fallback when API key absent
- **Interview Question Generator** — 3 personalised technical questions with rationale (matched skill deep-dive, missing skill probe, situational fit)
- **Radar Chart Visualisation** — per-candidate Chart.js radar chart across all 5 layers
- **CSV Export** — 13-field CSV: rank, composite, per-layer scores, GitHub persona, matched/missing skills, recommendation
- **Dark / Light Theme** — persistent via localStorage
- **Layer Detail Pages** — `layer1.html` through `layer6.html` explain each scoring component

---

## Project Structure

```
resume_checker-main/
│
├── main.py                        # FastAPI app — all endpoints, concurrent evaluation
│
├── backend/
│   ├── layer_1_semantic.py        # Neural embeddings + TF-IDF blend + LRU cache
│   ├── layer_2_taxonomy.py        # 140+ alias map + difflib fuzzy matching
│   ├── layer_3_experience.py      # spaCy NER date extraction + seniority classifier
│   ├── layer_4_projects.py        # Async GitHub repo/language/quality analysis
│   ├── layer_5_behavioral.py      # Async 3-signal GitHub behavioral intelligence
│   ├── bias_detector.py           # 5 fairness flag types — rule-based, no LLM
│   ├── llm_verdict.py             # Gemini 2.5 Flash hiring verdict + fallback
│   ├── llm_interview.py           # Gemini 2.5 Flash interview question generator
│   ├── resume_parser.py           # Structured extraction from raw PDF text
│   └── data.py                    # 3 JD templates + 3 archetype candidate profiles
│
├── frontend/
│   ├── index.html                 # Main app shell — landing + evaluation platform
│   ├── layer1.html                # Semantic layer explainer page
│   ├── layer2.html                # Taxonomy layer explainer page
│   ├── layer3.html                # Experience layer explainer page
│   ├── layer4.html                # Projects layer explainer page
│   ├── layer5.html                # GitHub behavioral layer explainer page
│   ├── layer6.html                # Bias detection + LLM verdict explainer page
│   ├── app.js                     # All frontend logic — API calls, rendering, charts
│   ├── styles.css                 # Base design system — dark/light theme tokens
│   └── hackathon-premium.css      # Premium UI enhancements
│
├── requirements.txt               # All Python dependencies with versions
├── .env.example                   # Template for environment variables
└── .gitignore                     # Standard Python + Node + OS excludes
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Neural NLP** | `BAAI/bge-small-en-v1.5` via sentence-transformers | Higher accuracy on technical/professional text vs MiniLM; chunked max-sim strategy handles long resumes |
| **Classical NLP** | scikit-learn `TfidfVectorizer` (bigrams, 8k features) | Exact keyword fallback; blended 25% into L1 for robustness |
| **Date Extraction** | spaCy `en_core_web_sm` + `python-dateutil` | NER-based date entity extraction with consecutive-entity pairing; handles `"Jan 2019"`, `"Present"`, regional formats |
| **Skill Matching** | `difflib.get_close_matches(cutoff=0.90)` | Catches spelling variants not in the taxonomy map |
| **Backend** | FastAPI 0.111 + Uvicorn 0.29 | Native async support; Pydantic validation; auto-generated `/docs` |
| **Async HTTP** | HTTPX | Non-blocking GitHub API calls compatible with FastAPI event loop |
| **PDF Parsing** | pdfplumber | Text + embedded hyperlink extraction; multi-page support |
| **LLM** | Google Gemini 2.5 Flash (`google-genai`) | Structured output with `VERDICT:` / `RECOMMENDATION:` parsing; async `client.aio.models.generate_content` |
| **Frontend** | Vanilla HTML + CSS + JavaScript | Zero dependency; works offline; no build step needed |
| **Charts** | Chart.js 4.4.2 | Radar charts for 5-layer visualisation per candidate |
| **Icons** | Lucide (CDN) | Consistent icon set |
| **Config** | python-dotenv | `GEMINI_API_KEY` and `GITHUB_TOKEN` from `.env` |

---

## Setup & Installation

### Prerequisites

- Python 3.11 (from [python.org](https://www.python.org/downloads/)) 
- Git

### Step 1 — Clone the repository

```bash
git clone https://github.com/Yasxh01/resume_checker.git
cd resume_checker
```

### Step 2 — Create and activate a virtual environment

```bash
# Windows
python -3.11 -m venv .venv
.venv\Scripts\activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

> ⏳ First install takes 5–6 minutes. `sentence-transformers` downloads PyTorch (~500MB). Subsequent runs are instant.

### Step 4 — Download spaCy language model

```bash
python -m spacy download en_core_web_sm
```

> This is a one-time ~12MB download. Without it, Layer 3 falls back to regex-only date extraction (still functional, slightly less accurate).

### Step 5 — Verify installation

```bash
python -c "import fastapi, sentence_transformers, sklearn, spacy, pdfplumber, httpx; print('All packages OK ✓')"
```

---

## Configuration (.env)

Create a file named `.env` in the project root (same folder as `main.py`):

```env
# Required for GitHub analysis (Layers 4 & 5)
# Without token: 60 API requests/hour (may hit limit during demos)
# With token:  5000 API requests/hour (safe for any demo)
# Get from: https://github.com/settings/tokens → Generate new token (classic) → public_repo scope
GITHUB_TOKEN=ghp_your_token_here

# Required for LLM verdicts and interview question generation
# Get from: https://aistudio.google.com
# Without key: deterministic rule-based fallback is used automatically
GEMINI_API_KEY=your_gemini_api_key_here
```

Both keys are **optional** — the system runs fully without them using built-in fallbacks.

---

## Running the Application

```bash
# From the project root (where main.py lives)
uvicorn main:app --reload --port 8000
```

Then open your browser at:

```
http://localhost:8000
```

The frontend is served as static files by FastAPI. The API documentation is available at:

```
http://localhost:8000/docs
```

---

## API Reference

### `GET /api/health`
Returns server status, version, and PDF support flag.

```json
{ "status": "healthy", "version": "2.0.0", "pdf_support": true }
```

---

### `GET /api/job-descriptions`
Returns all available JD templates and default candidate profiles.

---

### `POST /api/evaluate`
Runs the full 5-layer pipeline on all candidates concurrently.

**Request body:**
```json
{
  "jd_text": "We are looking for a Python Backend Engineer...",
  "jd_skills": ["python", "django", "aws", "postgresql"],
  "required_years": 3,
  "candidates": [
    {
      "name": "Jane Doe",
      "resume_text": "5 years experience...",
      "skills": ["python", "django", "aws"],
      "years_of_experience": 5,
      "projects_text": "Built a Django REST API...",
      "github_username": "janedoe"
    }
  ],
  "weights": { "w1": 8.0, "w2": 7.0, "w3": 6.0, "w4": 5.0, "w5": 4.0 },
  "generate_verdicts": true,
  "gemini_api_key": "optional-runtime-key"
}
```

**Response:** Sorted ranked results with per-layer scores, bias flags, normalised weights, and LLM verdicts.

---

### `POST /api/upload-resume`
Accepts a PDF file upload. Extracts text, embedded links, and auto-parses structured data.

**Request:** `multipart/form-data` with field `file`.

**Response:**
```json
{
  "success": true,
  "extracted_text": "...",
  "parsed_data": {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "github_username": "janedoe",
    "skills": ["Python", "Django", "AWS"],
    "years_of_experience": 5,
    "projects_text": "..."
  }
}
```

---

### `POST /api/verdict`
Generates a Gemini LLM verdict for a single candidate (called on-demand from the UI).

---

### `POST /api/interview-questions`
Generates 3 personalised technical interview questions with rationale.

---

### `GET /api/export-csv`
Downloads the last evaluation as a CSV file with 13 fields per candidate.

**Fields:** Rank, Candidate, Composite %, Semantic %, Taxonomy %, Experience %, Projects %, GitHub %, GitHub Persona, Matched Skills, Missing Skills, Years Experience, Recommendation.

---

## Scoring Formula

```
Composite Score = (S₁ × W₁) + (S₂ × W₂) + (S₃ × W₃) + (S₄ × W₄) + (S₅ × W₅)

Where:
  S₁ = Layer 1 Semantic Score        (0.0 – 100.0)
  S₂ = Layer 2 Taxonomy Score        (0.0 – 100.0)
  S₃ = Layer 3 Experience Score      (0.0 – 100.0)
  S₄ = Layer 4 Project Score         (0.0 – 100.0)
  S₅ = Layer 5 GitHub Score          (0.0 – 100.0)

  W₁–W₅ = Normalised weights (Wᵢ = wᵢ / Σwⱼ, so ΣWᵢ = 1.0)
  Default raw weights: w₁=8, w₂=7, w₃=6, w₄=5, w₅=4
  Default normalised:  W₁≈26.7%, W₂≈23.3%, W₃≈20%, W₄≈16.7%, W₅≈13.3%
```

---

## Bias Detection Engine

`backend/bias_detector.py` automatically scans results after every evaluation and raises flags when patterns suggest unfair penalisation. No LLM is involved — all rules are deterministic.

| Flag | Condition | Severity | Recommendation |
|---|---|---|---|
| **GitHub Data Gap** | L5 < 55 AND avg(L1–L4) > 70 | Warning | Request GitHub username or accept portfolio alternatives |
| **High-Potential Junior** | L3 < 50 AND L1 > 72 AND L2 > 65 | Info | Consider junior variant of role or fast-track interview |
| **Possible Alias Gap** | L1 > 75 AND L2 < 50 | Info | Review raw skill list for unlisted aliases; update TAXONOMY_MAP |
| **Project-Resume Mismatch** | L1 > 72 AND L4 < 45 | Warning | Request portfolio links to verify practical application of skills |
| **Potential Overqualification** | raw_exp_ratio > 150% AND composite > 75 | Info | Assess role fit and compensation alignment |

---

## Resume Parser

`backend/resume_parser.py` structures raw PDF text into a typed profile. It is called automatically on every PDF upload.

| Field | Extraction Method |
|---|---|
| `name` | First 1–3 lines matching `^([A-Z][a-z]+ ){1,3}[A-Z][a-z]+$` |
| `email` | RFC 5322 regex |
| `phone` | International + local format regex |
| `github_username` | `github.com/<username>` URL pattern |
| `linkedin` | `linkedin.com/in/<username>` URL pattern |
| `portfolio` | All URLs excluding GitHub and LinkedIn |
| `education` | Keyword matching: PhD > Master's > Bachelor's |
| `years_of_experience` | Layer 3 NLP date extraction (`extract_years_from_resume`) |
| `skills` | 120+ `COMMON_SKILLS` + all `TAXONOMY_MAP` keys/values scanned via regex with word-boundary matching |
| `projects_text` | Heading-based section extraction; falls back to bullet-point heuristics |

---

## LLM Integration

### Gemini Verdict (`llm_verdict.py`)

- Model: `gemini-2.5-flash`
- Called only for the **top 3** candidates per evaluation (cost and latency control)
- Structured prompt enforces `VERDICT:` and `RECOMMENDATION:` output format
- Recommendation parsed to exactly one of: `Strong Hire`, `Consider`, `Pass`
- Fully async via `client.aio.models.generate_content`
- **Fallback**: deterministic score-threshold verdict when API key absent or call fails

### Interview Questions (`llm_interview.py`)

- Generates exactly 3 questions per candidate:
  1. **Matched Skill Deep-Dive** — verifies expertise in a confirmed skill
  2. **Adaptability & Missing Skills** — assesses ability to bridge a skill gap
  3. **Situational Fit** — architecture/problem-solving aligned to JD
- Returns structured JSON: `{ type, question, rationale }[]`
- **Fallback**: 3 generic but contextualised questions using matched/missing skill names

---

## Frontend Pages

| File | Purpose |
|---|---|
| `index.html` | Main landing page + full evaluation platform (single-page) |
| `layer1.html` | Deep-dive explainer: semantic matching, embeddings, chunking |
| `layer2.html` | Deep-dive explainer: taxonomy map, alias resolution, fuzzy matching |
| `layer3.html` | Deep-dive explainer: NLP date extraction, seniority classification |
| `layer4.html` | Deep-dive explainer: GitHub repo analysis, code quality signals |
| `layer5.html` | Deep-dive explainer: contribution patterns, GitHub persona |
| `layer6.html` | Deep-dive explainer: bias detection flags, LLM verdict engine |

---

## Mock Data & JD Templates

`backend/data.py` ships with 3 JD templates and 3 archetype candidate profiles for instant demos:

**JD Templates:** Python Backend Engineer · Full Stack JavaScript Engineer · Machine Learning Engineer

**Candidate Archetypes:**

| Candidate | Profile Type | Tests |
|---|---|---|
| **Ananya Sharma** | High skill match, 1 yr exp | Skill-vs-seniority tension; High-Potential Junior flag |
| **Rishav Kumar** | Alias keywords, 2 yrs exp | Taxonomy alias resolution (`"amazon web services"` → `"aws"`) |
| **Sheetal Bajaj** | Fully balanced ideal, 5 yrs | Benchmark — should rank #1 across all layers |


---

## Performance Optimisations

| Optimisation | Where | Impact |
|---|---|---|
| LRU embedding cache (`maxsize=128`) | `layer_1_semantic.py` | JD encoded once; reused for all N candidates |
| Chunked max-sim encoding | `layer_1_semantic.py` | Handles resumes longer than model's context window |
| `asyncio.gather` for all candidates | `main.py` | Wall-clock time ≈ single-candidate time for N candidates |
| Concurrent GitHub API calls (3 signals) | `layer_5_behavioral.py` | Profile + events + repos fetched simultaneously |
| Concurrent repo language fetching | `layer_4_projects.py` | All repo language URLs fetched in one `asyncio.gather` |
| In-memory GitHub response cache | `layer_4_projects.py`, `layer_5_behavioral.py` | Prevents duplicate API calls for same username in a session |
| `@lru_cache(maxsize=512)` on skill normalisation | `layer_2_taxonomy.py` | Taxonomy lookups O(1) with memoisation |
| LLM called for top-3 only | `main.py` | Controls Gemini API cost and latency |
| TF-IDF as always-available fallback | `layer_1_semantic.py` | Zero latency fallback; no model loading required |

---

## License

MIT — free to use, modify, and distribute.