import os
from functools import lru_cache

from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers.merger_retriever import MergerRetriever

from .embeddings import get_embedder

# 환경변수
INDEX_DIR      = os.getenv("INDEX_DIR",    "app/data/index.faiss")
VEC_WEIGHT     = float(os.getenv("VEC_WEIGHT",  0.7))   # 벡터 검색 가중치
BM25_WEIGHT    = float(os.getenv("BM25_WEIGHT", 0.3))   # BM25 가중치
RETRIEVER_TOPK = int(os.getenv("RETRIEVER_K",  12))     # 각 검색기 k

_total = VEC_WEIGHT + BM25_WEIGHT
VEC_WEIGHT  /= _total
BM25_WEIGHT /= _total
# ────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_retriever():
    # 1) FAISS 벡터 검색기 (MMR)
    vs = FAISS.load_local(
        INDEX_DIR,
        get_embedder(),
        allow_dangerous_deserialization=True,
    )
    vect_ret = vs.as_retriever(search_type="mmr", k=RETRIEVER_TOPK)

    # 2) BM25 검색기
    bm25 = BM25Retriever.from_documents(
        vs.docstore._dict.values(), k=RETRIEVER_TOPK
    )

    # 3) 두 결과를 가중 병합
    return MergerRetriever(
        retrievers=[vect_ret, bm25],
        weights=[VEC_WEIGHT, BM25_WEIGHT],
    )
