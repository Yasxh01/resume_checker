# ============================================================
# backend/layer_1_semantic.py — Semantic Similarity Engine
# ============================================================

import logging
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_embedding_model = None

def _load_model():
    global _embedding_model
    try:
        logger.info("Layer 1: Loading 'all-MiniLM-L6-v2' embedding model...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Layer 1: Neural model loaded successfully. ✓")
    except Exception as e:
        logger.warning(f"Layer 1: Could not load neural model — {e}. Will use TF-IDF fallback.")
        _embedding_model = None

_load_model()


def calculate_semantic_match(jd_text: str, resume_text: str) -> float:
    """
    Computes semantic similarity between job description and resume.
    Returns float 0.0 to 100.0.
    Primary: Neural embeddings. Fallback: TF-IDF.
    """
    if not jd_text or not jd_text.strip():
        return 0.0
    if not resume_text or not resume_text.strip():
        return 0.0

    # Stage 1: Neural Embedding
    if _embedding_model is not None:
        try:
            jd_embedding     = _embedding_model.encode(jd_text,     convert_to_numpy=True)
            resume_embedding = _embedding_model.encode(resume_text, convert_to_numpy=True)
            similarity_matrix = cosine_similarity(
                jd_embedding.reshape(1, -1),
                resume_embedding.reshape(1, -1)
            )
            return round(float(similarity_matrix[0][0]) * 100, 2)
        except Exception as e:
            logger.warning(f"Layer 1: Neural scoring failed — {e}. Using TF-IDF.")

    # Stage 2: TF-IDF Fallback
    try:
        vectorizer   = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform([jd_text, resume_text])
        similarity_matrix = cosine_similarity(tfidf_matrix[0], tfidf_matrix[1])
        return round(float(similarity_matrix[0][0]) * 100, 2)
    except Exception as e:
        logger.error(f"Layer 1: TF-IDF fallback failed — {e}. Returning 0.0.")
        return 0.0
