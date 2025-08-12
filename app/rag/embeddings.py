# app/rag/embeddings.py
import os
import torch
from functools import lru_cache
from langchain_community.embeddings import HuggingFaceEmbeddings

try:
    # 안전한 config (기본값 제공)
    from app.config import EMBED_MODEL_ID
except Exception:
    EMBED_MODEL_ID = os.getenv("EMBED_MODEL_ID", "intfloat/e5-large-v2")

@lru_cache(maxsize=1)
def get_embedder() -> HuggingFaceEmbeddings:
    """한 번 로드 후 재사용"""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return HuggingFaceEmbeddings(
        model_name=EMBED_MODEL_ID,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True, "batch_size": 32},
    )
