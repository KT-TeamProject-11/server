# -*- coding: utf-8 -*-
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def _getenv(key: str, default=None, cast=None):
    val = os.getenv(key, None)
    if val is None or val == "":
        return default
    if cast:
        try:
            return cast(val)
        except Exception:
            return default
    return val

# ─────────────────────────────────────────────────────────
# 인덱스/RAG/검색 기본값
EMBED_MODEL_ID        = _getenv("EMBED_MODEL_ID",        "intfloat/e5-large-v2")
RERANK_MODEL_ID       = _getenv("RERANK_MODEL_ID",       "khoj-ai/mxbai-rerank-base-v1")
RERANK_TOP_N          = _getenv("RERANK_TOP_N",          4,    int)
INDEX_DIR             = _getenv("INDEX_DIR",             "app/data/index.faiss")
RETRIEVER_K           = _getenv("RETRIEVER_K",           12,   int)
VEC_WEIGHT            = _getenv("VEC_WEIGHT",            0.7,  float)
BM25_WEIGHT           = _getenv("BM25_WEIGHT",           0.3,  float)

SEARCH_HITS           = _getenv("SEARCH_HITS",           5,    int)
FUZZ_LIMIT            = _getenv("FUZZ_LIMIT",            20,   int)
FUZZ_SCORE            = _getenv("FUZZ_SCORE",            80,   int)
THRESH                = _getenv("THRESH",                0.5,  float)

REDIS_URL             = _getenv("REDIS_URL",             "redis://localhost:6379/0")
CACHE_TTL_SEC         = _getenv("CACHE_TTL_SEC",         600,  int)

OPENAI_API_KEY        = _getenv("OPENAI_API_KEY",        "")
OPENAI_MODEL          = _getenv("OPENAI_MODEL",          "gpt-4o-mini")
OPENAI_TEMPERATURE    = _getenv("OPENAI_TEMPERATURE",    0.2,  float)
MAX_COMPLETION_TOKENS = _getenv("MAX_COMPLETION_TOKENS", 1024, int)

LLAMA_API             = _getenv("LLAMA_API",             "")

# 호환 별칭
DDG_HITS         = SEARCH_HITS
CACHE_TTL        = CACHE_TTL_SEC
LOCAL_HIT_THRES  = THRESH
RETRIEVER_TOP_K  = RETRIEVER_K
INDEX_PATH       = INDEX_DIR
FAISS_INDEX_PATH = INDEX_DIR
CLEAN_DIR        = _getenv("CLEAN_DIR", "app/data/clean")

# ─────────────────────────────────────────────────────────
# 정적 파일 (이미지)
# 반드시 같은 오리진(/static)으로 제공
STATIC_URL_PREFIX = "/static"
STATIC_DIR        = str((Path(__file__).resolve().parent / "static").resolve())

# 하위폴더가 따로 없으면 빈 문자열 유지
CENTER_IMG_SUBDIR = ""

# 🔒 외부 베이스 URL 끔(동일 오리진만 사용)
PUBLIC_BASE_URL   = ""

def validate_runtime_env():
    missing = []
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if missing:
        raise RuntimeError(f"Missing runtime env: {', '.join(missing)}")
