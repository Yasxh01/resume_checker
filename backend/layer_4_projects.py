# ============================================================
# backend/layer_4_projects.py — Project Relevance Engine
# ============================================================
# FIXED: No longer imports _embedding_model from layer_1_semantic.
# Instead references the shared model via a module-level accessor
# function that works safely under uvicorn's Windows subprocess
# reloader without causing circular import or spawn errors.
# ============================================================

import logging
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_model():
    """
    Safely retrieves the shared SentenceTransformer model.
    Imports layer_1_semantic at call-time (not module load-time)
    to avoid Windows multiprocessing spawn issues with uvicorn.
    Falls back to None if unavailable.
    """
    try:
        import layer_1_semantic
        return layer_1_semantic._embedding_model
    except Exception:
        return None


def calculate_project_relevance(jd_text: str, projects_text: str) -> float:
    """
    Calculates semantic relevance of candidate's projects vs JD.
    Returns 0.0 instantly if no project text exists.

    Args:
        jd_text       (str): Full job description text.
        projects_text (str): Candidate's project descriptions.

    Returns:
        float: Relevance score 0.0 to 100.0.
    """
    # Guard: empty project text
    if not projects_text or not projects_text.strip():
        logger.warning("Layer 4: No project text provided. Returning 0.0.")
        return 0.0

    # Guard: empty JD text
    if not jd_text or not jd_text.strip():
        logger.warning("Layer 4: No JD text provided. Returning 0.0.")
        return 0.0

    # Stage 1: Neural Embedding (shared model from Layer 1)
    embedding_model = _get_model()

    if embedding_model is not None:
        try:
            logger.info("Layer 4: Computing project relevance via neural embeddings...")
            jd_emb       = embedding_model.encode(jd_text,       convert_to_numpy=True)
            projects_emb = embedding_model.encode(projects_text, convert_to_numpy=True)
            sim          = cosine_similarity(
                jd_emb.reshape(1, -1),
                projects_emb.reshape(1, -1)
            )
            score = round(float(sim[0][0]) * 100, 2)
            logger.info(f"Layer 4 (Neural): Project relevance = {score}%")
            return score
        except Exception as e:
            logger.warning(f"Layer 4: Neural scoring failed — {e}. Switching to TF-IDF.")

    # Stage 2: TF-IDF Fallback
    try:
        logger.info("Layer 4: Using TF-IDF fallback for project relevance...")
        vectorizer   = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform([jd_text, projects_text])
        sim          = cosine_similarity(tfidf_matrix[0], tfidf_matrix[1])
        score        = round(float(sim[0][0]) * 100, 2)
        logger.info(f"Layer 4 (TF-IDF): Project relevance = {score}%")
        return score
    except Exception as e:
        logger.error(f"Layer 4: TF-IDF fallback failed — {e}. Returning 0.0.")
        return 0.0
