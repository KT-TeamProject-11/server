# app/rag/reranker.py
from typing import List, Tuple
import torch
from sentence_transformers import CrossEncoder
from app.config import RERANK_MODEL_ID, RERANK_TOP_N

_device = "cuda" if torch.cuda.is_available() else "cpu"
_model = CrossEncoder(RERANK_MODEL_ID, device=_device, max_length=512)

def rerank(query: str, docs: List[str], top_n: int = RERANK_TOP_N) -> Tuple[List[str], float]:
    if not docs:
        return [], 0.0
    scores = _model.predict([(query, d) for d in docs], convert_to_numpy=True)
    pairs = sorted(zip(docs, scores), key=lambda t: -t[1])
    top_docs = [d for d, _ in pairs[:top_n]]
    best = float(pairs[0][1]) if pairs else 0.0
    return top_docs, best
