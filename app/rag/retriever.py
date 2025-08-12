# app/rag/retriever.py
from functools import lru_cache
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers.merger_retriever import MergerRetriever
from app.rag.embeddings import get_embedder
from app.config import INDEX_DIR, RETRIEVER_K, VEC_WEIGHT, BM25_WEIGHT

@lru_cache(maxsize=1)
def get_vectorstore():
    return FAISS.load_local(
        INDEX_DIR,
        get_embedder(),
        allow_dangerous_deserialization=True,
    )

@lru_cache(maxsize=1)
def get_retriever():
    vs = get_vectorstore()
    vect_ret = vs.as_retriever(search_type="mmr", k=RETRIEVER_K)
    # 내부 속성 의존(업데이트 시 주의). 추후 Documents 별도 저장으로 개선 가능.
    bm25 = BM25Retriever.from_documents(vs.docstore._dict.values(), k=RETRIEVER_K)
    return MergerRetriever(retrievers=[vect_ret, bm25], weights=[VEC_WEIGHT, BM25_WEIGHT])
