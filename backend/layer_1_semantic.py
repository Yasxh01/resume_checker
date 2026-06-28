# ============================================================
# backend/layer_1_semantic.py — Semantic Similarity Engine
# ============================================================

import re
import hashlib
import logging
from functools import lru_cache
from typing import Optional
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#constants
NEURAL_WEIGHT = 0.75   
TFIDF_WEIGHT  = 0.25   
CACHE_SIZE    = 128 

#boilerplate striper
_STRIP_PHRASES = [
    r"equal opportunity employer",
    r"we are looking for",
    r"the ideal candidate",
    r"responsibilities include",
    r"you will be responsible for",
    r"about us",
    r"about the role",
    r"what you.ll do",
    r"what we offer",
    r"nice to have",
    r"good to have",
    r"benefits.*?(?=\n|$)",
]
_STRIP_RE = re.compile("|".join(_STRIP_PHRASES), re.IGNORECASE)

from sentence_transformers import SentenceTransformer

_embedding_model = None

def _load_model():
    global _embedding_model
    try:
        logger.info("Layer 1: Loading 'all-MiniLM-L6-v2'...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Layer 1: Neural model loaded ✓")
    except Exception as e:
        logger.warning(f"Layer 1: Could not load neural model — {e}")
        _embedding_model = None

_load_model()
       

#  TEXT PREPROCESSOR

def _preprocess(text: str) -> str:
    """
    Cleans raw text before encoding.
    1. Strip HTML tags
    2. Remove boilerplate phrases
    3. Collapse whitespace
    """
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)   # strip HTML
    text = _STRIP_RE.sub(" ", text)          # strip boilerplate
    text = re.sub(r"\s+", " ", text).strip() # collapse whitespace
    return text

# LRU EMBEDDING CACHE

@lru_cache(maxsize=CACHE_SIZE)
def _cached_encode(text_hash: str, text: str) -> np.ndarray:
        """
         Encodes text into embeddings using an LRU cache.
         SHA-256 hashes are used as compact cache keys.
        """
        model=_embedding_model
        if model is None:
            raise RuntimeError("Model not loaded")
        return model.encode (text, convert_to_numpy=True)


def _get_embedding(text: str) -> Optional[np.ndarray]:
    """Wrapper: computes hash key and calls _cached_encode."""
    if _embedding_model is None:
        return None
    try:
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        return _cached_encode(text_hash, text)
    except Exception as e:
        logger.warning(f"Layer 1: Embedding failed — {e}")
        return None


# TF-IDF SCORER

def _tfidf_score(jd_text: str, resume_text: str) -> float:
    """
    TF-IDF cosine similarity. Always available, no model needed.
    ngram_range=(1,2) adds bigrams: "machine learning", "data science".
    """
    try:
        vectorizer   = TfidfVectorizer(
            stop_words   = "english",
            ngram_range  = (1, 2),
            max_features = 8000,
        )
        tfidf_matrix = vectorizer.fit_transform([jd_text, resume_text])
        sim          = cosine_similarity(tfidf_matrix[0], tfidf_matrix[1])
        return round(float(sim[0][0]) * 100, 2)
    except Exception as e:
        logger.warning(f"Layer 1: TF-IDF scoring failed — {e}")
        return 0.0
    

# CORE SCORING LOGIC    

def _score(jd_text: str, resume_text: str) -> float:
    """
    Shared scoring logic.
 
    Strategy:
      1. Preprocess both texts
      2. Always compute TF-IDF (fast, no model needed)
      3. Attempt neural embedding (cached)
      4. If neural available → blend: neural×0.75 + tfidf×0.25
         If neural unavailable → return TF-IDF only
    """
    if not jd_text or not jd_text.strip():   return 0.0
    if not resume_text or not resume_text.strip(): return 0.0
 
    clean_jd     = _preprocess(jd_text)
    clean_resume = _preprocess(resume_text)
    if not clean_jd or not clean_resume:     return 0.0
 
    # Always compute TF-IDF
    tfidf = _tfidf_score(clean_jd, clean_resume)
 
    # Attempt neural
    jd_emb     = _get_embedding(clean_jd)
    resume_emb = _get_embedding(clean_resume)
 
    if jd_emb is not None and resume_emb is not None:
        try:
            sim    = cosine_similarity(jd_emb.reshape(1, -1), resume_emb.reshape(1, -1))
            neural = round(float(sim[0][0]) * 100, 2)
            blended = round(neural * NEURAL_WEIGHT + tfidf * TFIDF_WEIGHT, 2)
            logger.info(
                f"Layer 1: neural={neural}% · tfidf={tfidf}% · "
                f"blended={blended}% "
                f"(cache: {_cached_encode.cache_info().currsize}/{CACHE_SIZE})"
            )
            return blended
        except Exception as e:
            logger.warning(f"Layer 1: Neural blend failed — {e}. Returning TF-IDF.")
 
    logger.info(f"Layer 1 (TF-IDF only): {tfidf}%")
    return tfidf

    

#PUBLIC API







def calculate_semantic_match(jd_text: str, resume_text: str) -> float:
    """
    Computes semantic similarity between job description and resume.
    Returns float 0.0 to 100.0.
    """
    return _score(jd_text,resume_text)

# CACHE UTILITIES
def get_cache_info() -> dict:
    """Returns embedding cache stats. Used by /api/health."""
    info = _cached_encode.cache_info()
    return {
        "hits"        : info.hits,
        "misses"      : info.misses,
        "maxsize"     : info.maxsize,
        "currsize"    : info.currsize,
        "model_loaded": _embedding_model is not None,
    }
 
 
def clear_embedding_cache() -> None:
    """Clears the LRU embedding cache."""
    _cached_encode.cache_clear()
    logger.info("Layer 1: Embedding cache cleared.")