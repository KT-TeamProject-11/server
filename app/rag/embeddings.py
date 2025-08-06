import os
import torch
from functools import lru_cache
from langchain_community.embeddings import HuggingFaceEmbeddings

_MODEL_ID = os.getenv("EMBED_MODEL_ID", "intfloat/e5-large-v2")  #모델 교체
# 다른 선택지 ->  "intfloat/bge-m3-small" 

@lru_cache(maxsize=1)
def get_embedder() -> HuggingFaceEmbeddings:
    """한 번 로드 후 재사용: multilingual-e5-large (또는 bge-m3)"""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return HuggingFaceEmbeddings(
        model_name=_MODEL_ID,
        model_kwargs={"device": device},
        encode_kwargs={
            "normalize_embeddings": True,
            "batch_size": 32,       # 처리량 향상
        },
    )
