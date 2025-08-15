# app/rag/retriever.py
from __future__ import annotations
from functools import lru_cache
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers.merger_retriever import MergerRetriever
from langchain.schema import Document

from app.rag.embeddings import get_embedder

try:
    from app.config import INDEX_DIR, RETRIEVER_K, VEC_WEIGHT, BM25_WEIGHT
except Exception:
    INDEX_DIR = "app/data/index"
    RETRIEVER_K = 6
    VEC_WEIGHT = 0.6
    BM25_WEIGHT = 0.4

@lru_cache(maxsize=1)
def get_vectorstore():
    return FAISS.load_local(
        INDEX_DIR,
        get_embedder(),
        allow_dangerous_deserialization=True,
    )

def _bm25_docs_from_vs(vs) -> List[Document]:
    out: List[Document] = []
    for doc in vs.docstore._dict.values():
        meta = doc.metadata or {}
        head = " ".join(str(meta.get(k, "")) for k in ("title", "section", "category") if meta.get(k)).strip()
        prefix = f"{head}\n" if head else ""
        out.append(Document(page_content=prefix + doc.page_content, metadata=meta))
    return out

@lru_cache(maxsize=1)
def get_retriever():
    vs = get_vectorstore()
    vect_ret = vs.as_retriever(search_type="mmr", search_kwargs={"k": RETRIEVER_K})

    bm25_docs = _bm25_docs_from_vs(vs)
    bm25 = BM25Retriever.from_documents(bm25_docs)
    bm25.k = RETRIEVER_K

    return MergerRetriever(
        retrievers=[vect_ret, bm25],
        weights=[VEC_WEIGHT, BM25_WEIGHT],
    )
