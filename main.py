# ============================================================
# main.py — FastAPI Application Server
# ============================================================
# PURPOSE:
#   This is the central API server. It exposes REST endpoints
#   that the HTML/JS frontend calls via fetch().
#
# HOW TO RUN:
#   cd backend
#   uvicorn main:app --reload --port 8000
#
# API ENDPOINTS:
#   GET  /api/health           → Server health check
#   GET  /api/job-descriptions → List all available JDs
#   POST /api/evaluate         → Run full pipeline
#   POST /api/upload-resume    → Parse uploaded PDF
#   POST /api/verdict          → Generate LLM verdict
#   GET  /api/export-csv       → Download results as CSV
# ============================================================

import io
import csv
import json
import logging

from typing import List, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel



from backend.layer_1_semantic   import calculate_semantic_match
from backend.layer_2_taxonomy   import calculate_taxonomy_score
from backend.layer_3_experience import calculate_experience_score
from backend.layer_4_projects   import calculate_project_relevance
from backend.layer_5_behavioral import calculate_github_score
from backend.bias_detector      import detect_bias_flags
from backend.llm_verdict        import generate_verdict
from backend.data               import job_descriptions, candidate_profiles, DEFAULT_JD

# PDF parsing
try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logging.warning("pdfplumber not installed. PDF upload will be disabled.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# FASTAPI APP INITIALIZATION
# ============================================================
app = FastAPI(
    title       = "AI Candidate Ranking Platform API",
    description = "Multi-layer hybrid scoring pipeline for candidate evaluation",
    version     = "2.0.0",
)

# ============================================================
# CORS MIDDLEWARE
# ============================================================
# CORS (Cross-Origin Resource Sharing) allows the HTML frontend
# (running on file:// or a different port) to call this API.
# Without this, browsers block cross-origin requests.
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],  # In production: specify exact frontend URL
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ============================================================
# PYDANTIC MODELS — Request/Response Schemas
# ============================================================
# Pydantic models define the exact shape of JSON data
# that our endpoints accept and return. FastAPI uses these
# for automatic validation and documentation.
# ============================================================

class CandidateInput(BaseModel):
    """Schema for a single candidate profile."""
    name               : str
    resume_text        : str
    skills             : List[str]
    years_of_experience: int
    projects_text      : Optional[str] = ""
    github_username    : Optional[str] = ""


class WeightsInput(BaseModel):
    """Schema for layer weight configuration."""
    w1: float = 8.0   # Semantic
    w2: float = 7.0   # Taxonomy
    w3: float = 6.0   # Experience
    w4: float = 5.0   # Projects
    w5: float = 4.0   # GitHub


class EvaluationRequest(BaseModel):
    """Schema for the full evaluation pipeline request."""
    jd_text: str
    jd_skills: List[str]
    required_years: int
    candidates: List[CandidateInput]
    weights: WeightsInput
    generate_verdicts: bool = False
    gemini_api_key: Optional[str] = ""


class VerdictRequest(BaseModel):
    candidate_name     : str
    scores             : dict
    jd_text            : str
    candidate_skills   : List[str]
    years_of_experience: int
    gemini_api_key     : Optional[str] = ""


class InterviewQuestionsRequest(BaseModel):
    candidate: dict
    jd_text: str
    gemini_api_key: Optional[str] = ""


# ============================================================
# IN-MEMORY RESULTS STORE
# ============================================================
# Stores the last evaluation results so the CSV export
# endpoint can access them without re-running the pipeline.
# In production: use Redis or a database.
# ============================================================
_last_results = []


# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/api/health")
async def health_check():
    """Server health check endpoint."""
    return {
        "status"       : "healthy",
        "version"      : "2.0.0",
        "pdf_support"  : PDF_AVAILABLE,
    }


@app.get("/api/job-descriptions")
async def get_job_descriptions():
    """Returns all available job description templates."""
    return {
        "job_descriptions": {
            key: {
                "text"          : jd["text"],
                "required_skills": jd["required_skills"],
                "required_years" : jd["required_years"],
            }
            for key, jd in job_descriptions.items()
        },
        "default"         : DEFAULT_JD,
        "candidates"      : candidate_profiles,
    }


@app.post("/api/evaluate")
async def evaluate_candidates(request: EvaluationRequest):
    """
    Runs the full 5-layer evaluation pipeline on all candidates.

    Process:
    1. Normalize weights to sum to 1.0
    2. For each candidate, run all 5 scoring layers
    3. Calculate composite weighted score
    4. Sort candidates by composite score (descending)
    5. Run bias detection on sorted results
    6. Optionally generate LLM verdicts
    7. Return full results with metadata
    """
    global _last_results

    # ----------------------------------------------------------
    # WEIGHT NORMALIZATION
    # ----------------------------------------------------------
    w = request.weights
    total_weight = w.w1 + w.w2 + w.w3 + w.w4 + w.w5

    if total_weight == 0:
        raise HTTPException(status_code=400, detail="All weights cannot be zero.")

    norm_w1 = w.w1 / total_weight
    norm_w2 = w.w2 / total_weight
    norm_w3 = w.w3 / total_weight
    norm_w4 = w.w4 / total_weight
    norm_w5 = w.w5 / total_weight

    # ----------------------------------------------------------
    # EVALUATE EACH CANDIDATE
    # ----------------------------------------------------------
    results = []

    for candidate in request.candidates:

        logger.info(f"Evaluating: {candidate.name}")

        # Layer 1: Semantic Match
        score_l1 = calculate_semantic_match(
            jd_text     = request.jd_text,
            resume_text = candidate.resume_text,
        )

        # Layer 2: Taxonomy Score (returns dict with matched/missing)
        taxonomy_result = calculate_taxonomy_score(
            jd_skills        = request.jd_skills,
            candidate_skills = candidate.skills,
        )
        score_l2        = taxonomy_result["score"]
        matched_skills  = taxonomy_result["matched"]
        missing_skills  = taxonomy_result["missing"]

        # Layer 3: Experience Score
        exp_result = calculate_experience_score(
            candidate_years = candidate.years_of_experience,
            required_years  = request.required_years,
            resume_text =candidate.resume_text,
        )
        score_l3=exp_result["score"]

        # Layer 4: Project Relevance
        score_l4 = calculate_project_relevance(
            jd_text       = request.jd_text,
            projects_text = candidate.projects_text or "",
        )

        # Layer 5: GitHub Behavioral Score
        github_result = calculate_github_score(
            github_username = candidate.github_username or "",
        )
        score_l5 = github_result["score"]

        # Composite Weighted Score
        composite = (
            score_l1 * norm_w1 +
            score_l2 * norm_w2 +
            score_l3 * norm_w3 +
            score_l4 * norm_w4 +
            score_l5 * norm_w5
        )
        composite = round(composite, 2)

        results.append({
            "name"               : candidate.name,
            "composite"          : composite,
            "score_l1"           : score_l1,
            "score_l2"           : score_l2,
            "score_l3"           : score_l3,
            "score_l4"           : score_l4,
            "score_l5"           : score_l5,
            "matched_skills"     : matched_skills,
            "missing_skills"     : missing_skills,
            "github_data"        : github_result,
            "experience_detail"  : exp_result,
            "years_of_experience": candidate.years_of_experience,
            "required_years"     : request.required_years,
            "skills"             : candidate.skills,
            "verdict"            : None,
        })

    # ----------------------------------------------------------
    # SORT BY COMPOSITE SCORE (Highest First)
    results_sorted = sorted(results, key=lambda x: x["composite"], reverse=True)

    # Assign rank
    for i, r in enumerate(results_sorted):
        r["rank"] = i + 1

    # ----------------------------------------------------------
    # BIAS DETECTION
    # ----------------------------------------------------------
    bias_flags = detect_bias_flags(results_sorted)

    # ----------------------------------------------------------
    # LLM VERDICTS (Optional)
    # ----------------------------------------------------------
    if request.generate_verdicts:
        logger.info("Evaluation complete. Generating verdicts...")
        
        async def _generate_verdict_single(res):
            try:
                v = await generate_verdict(
                    candidate_name      = res.get("name", "Unknown"),
                    scores              = res,
                    jd_text             = request.jd_text,
                    candidate_skills    = res.get("skills", []),
                    years_of_experience = res.get("years_of_experience", 0),
                    api_key             = request.gemini_api_key
                )
                res["verdict"] = v
            except Exception as e:
                logger.error(f"Error generating verdict for {res.get('name')}: {e}")
                res["verdict"] = {"verdict": "Error generating verdict.", "recommendation": "Error", "source": "error"}

        verdict_tasks = [_generate_verdict_single(r) for r in results_sorted]
        await asyncio.gather(*verdict_tasks)
        
    # Store for CSV export
    _last_results = results_sorted

    return {
        "results"    : results_sorted,
        "bias_flags" : bias_flags,
        "weights"    : {
            "w1": round(norm_w1, 4),
            "w2": round(norm_w2, 4),
            "w3": round(norm_w3, 4),
            "w4": round(norm_w4, 4),
            "w5": round(norm_w5, 4),
        },
        "total_candidates": len(results_sorted),
    }


@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    """
    Accepts a PDF file upload and returns extracted text.
    Used by the frontend for the PDF resume upload feature.
    """
    if not PDF_AVAILABLE:
        raise HTTPException(
            status_code = 503,
            detail      = "PDF parsing not available. Install pdfplumber."
        )

    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code = 400,
            detail      = "Only PDF files are supported."
        )

    try:
        contents = await file.read()
        pdf_file = io.BytesIO(contents)

        extracted_text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    extracted_text += page_text + "\n"

        extracted_text = extracted_text.strip()

        if not extracted_text:
            raise HTTPException(
                status_code = 422,
                detail      = "Could not extract text from PDF. File may be scanned/image-based."
            )

        return {
            "success"       : True,
            "extracted_text": extracted_text,
            "page_count"    : len(pdf.pages) if hasattr(pdf, 'pages') else 0,
            "filename"      : file.filename,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF parsing error: {e}")
        raise HTTPException(status_code=500, detail=f"PDF parsing failed: {str(e)}")


@app.post("/api/verdict")
async def get_verdict(request: VerdictRequest):
    """Generates LLM verdict for a single candidate."""
    try:
        v = await generate_verdict(
            candidate_name      = request.candidate_name,
            scores              = request.scores,
            jd_text             = request.jd_text,
            candidate_skills    = request.candidate_skills,
            years_of_experience = request.years_of_experience,
            api_key             = request.gemini_api_key
        )
        return v
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/interview-questions")
async def get_interview_questions(request: InterviewQuestionsRequest):
    """Generates personalized LLM interview questions for a candidate."""
    try:
        from backend.llm_interview import generate_interview_questions
        # Determine matched/missing skills based on the candidate's scores
        matched = request.candidate.get("matched_skills", [])
        missing = request.candidate.get("missing_skills", [])
        
        questions = await generate_interview_questions(
            candidate_name = request.candidate.get("name", "Unknown"),
            matched_skills = matched,
            missing_skills = missing,
            jd_text        = request.jd_text,
            api_key        = request.gemini_api_key
        )
        return questions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/export-csv")
async def export_csv():
    """
    Returns the last evaluation results as a downloadable CSV file.
    Must call /api/evaluate first to populate the results.
    """
    global _last_results

    if not _last_results:
        raise HTTPException(
            status_code = 404,
            detail      = "No evaluation results found. Run an evaluation first."
        )

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "Rank", "Candidate", "Composite %",
        "Semantic %", "Taxonomy %", "Experience %",
        "Projects %", "GitHub %",
        "Matched Skills", "Missing Skills",
        "Years Experience", "Recommendation"
    ])

    # Data rows
    for r in _last_results:
        verdict_rec = r.get("verdict", {}) or {}
        writer.writerow([
            r.get("rank", ""),
            r.get("name", ""),
            r.get("composite", ""),
            r.get("score_l1", ""),
            r.get("score_l2", ""),
            r.get("score_l3", ""),
            r.get("score_l4", ""),
            r.get("score_l5", ""),
            ", ".join(r.get("matched_skills", [])),
            ", ".join(r.get("missing_skills", [])),
            r.get("years_of_experience", ""),
            r.get("extracted_years",    ""),
            r.get("seniority_level",    ""),
            r.get("extraction_method",  ""),
            verdict_rec.get("recommendation", ""),
        ])

    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type = "text/csv",
        headers    = {
            "Content-Disposition": "attachment; filename=candidate_rankings.csv"
        }
    )

# ============================================================
# SERVE FRONTEND (STATIC FILES)
# ============================================================
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Calculate absolute path to frontend directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

if os.path.exists(FRONTEND_DIR):
    # Explicitly serve index.html at the root URL
    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
    
    # Mount the rest of the static files (app.js, styles.css)
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    logger.warning(f"Frontend folder not found at {FRONTEND_DIR}. Frontend will not be served.")

if __name__ == "__main__":
    import uvicorn
    print("\n========================================================")
    print("🚀 RecruitIQ Server is starting up...")
    print("👉 Open your browser to: http://localhost:8000")
    print("========================================================\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
