import os
from typing import List, Tuple

import torch
from sentence_transformers import CrossEncoder

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_ID = os.getenv("RERANK_MODEL_ID", "khoj-ai/mxbai-rerank-base-v1")

_model = CrossEncoder(MODEL_ID, device=DEVICE, max_length=512)


def rerank(query: str, docs: List[str], top_n: int = 4) -> Tuple[List[str], float]:
    """점수 기반 상위 top_n 문서와 최고점 반환"""
    if not docs:
        return [], 0.0

    scores = _model.predict([(query, d) for d in docs], convert_to_numpy=True)
    ranked = sorted(zip(docs, scores), key=lambda t: -t[1])
    return [d for d, _ in ranked[:top_n]], float(max(scores))
