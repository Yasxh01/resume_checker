# ============================================================
# backend/layer_1_semantic.py — Semantic Similarity Engine
# ============================================================

import re
import hashlib
import logging
import numpy as np
from functools import lru_cache
from typing import Optional
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#constants
NEURAL_WEIGHT = 0.75   
TFIDF_WEIGHT  = 0.25
CACHE_SIZE = 128
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

_embedding_model = None

def _load_model():
    global _embedding_model
    try:
        logger.info("Layer 1: Loading 'BAAI/bge-small-en-v1.5' embedding model...")
        _embedding_model = SentenceTransformer("BAAI/bge-small-en-v1.5")
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
def _cached_encode(text_hash: str, text: str):
    if _embedding_model is not None:
        return _embedding_model.encode(text, convert_to_numpy=True)
    return None


def _get_jd_embedding(jd_text: str):
    if _embedding_model is None:
        return None
    try:
        text_hash = hashlib.sha256(jd_text.encode()).hexdigest()
        return _cached_encode(text_hash, jd_text)
    except Exception as e:
        logger.warning(f"Layer 1: Embedding failed — {e}")
        return None

def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """Splits long text into overlapping chunks of words."""
    words = text.split()
    if not words:
        return []
    chunks = []
    for i in range(0, len(words), max(1, chunk_size - overlap)):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        if i + chunk_size >= len(words):
            break
    return chunks

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

def calculate_semantic_match(jd_text: str, resume_text: str) -> float:
    """
    Computes semantic similarity between job description and resume.
    Returns float 0.0 to 100.0.
    Primary: Blended Chunked Neural (75%) + TF-IDF (25%).
    Fallback: TF-IDF only.
    """
    if not jd_text or not jd_text.strip():
        return 0.0
    if not resume_text or not resume_text.strip():
        return 0.0

    # 1. Clean the texts
    clean_jd = _preprocess(jd_text)
    clean_resume = _preprocess(resume_text)
    
    if not clean_jd or not clean_resume:
        return 0.0

    # 2. Always compute TF-IDF
    tfidf = _tfidf_score(clean_jd, clean_resume)

    # 3. Attempt Neural Embedding (Chunked)
    if _embedding_model is not None:
        try:
            jd_embedding = _get_jd_embedding(clean_jd)
            
            # Chunk the cleaned resume text
            resume_chunks = _chunk_text(clean_resume, chunk_size=400, overlap=50)
            if resume_chunks:
                chunk_embeddings = _embedding_model.encode(resume_chunks, convert_to_numpy=True)
                
                # Compare JD against all chunks
                similarity_matrix = cosine_similarity(
                    jd_embedding.reshape(1, -1),
                    chunk_embeddings
                )
                
                # Take the maximum similarity across any chunk
                max_sim = float(np.max(similarity_matrix))
                neural = round(max_sim * 100, 2)
                
                # Blend
                blended = round(neural * NEURAL_WEIGHT + tfidf * TFIDF_WEIGHT, 2)
                logger.info(
                    f"Layer 1: neural={neural}% · tfidf={tfidf}% · "
                    f"blended={blended}% "
                    f"(cache: {_cached_encode.cache_info().currsize}/{CACHE_SIZE})"
                )
                return blended
        except Exception as e:
            logger.warning(f"Layer 1: Neural scoring failed — {e}. Using TF-IDF fallback.")

    # 4. Fallback if Neural model fails
    logger.info(f"Layer 1 (TF-IDF only): {tfidf}%")
    return tfidf

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