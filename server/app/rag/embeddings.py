from functools import lru_cache
import torch
from langchain_community.embeddings import HuggingFaceEmbeddings

_MODEL_ID = "jhgan/ko-sroberta-multitask"     # 한국어 STS·STSbench SOTA

@lru_cache(maxsize=1)
def get_embedder() -> HuggingFaceEmbeddings:
    """1 회 로드 후 재사용(GPU VRAM 절약)"""
    return HuggingFaceEmbeddings(
        model_name  = _MODEL_ID,
        model_kwargs= {"device": "cuda" if torch.cuda.is_available() else "cpu"},
        encode_kwargs = {"normalize_embeddings": True},    # 코사인 정규화
    )
