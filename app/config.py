# -*- coding: utf-8 -*-
import os
from pathlib import Path
from dotenv import load_dotenv

# .env 로딩
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
INDEX_DIR             = _getenv("INDEX_DIR",             "app/data/index.faiss")  # 호환용 별칭 유지
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
# 정적/퍼블릭
STATIC_URL_PREFIX = _getenv("STATIC_URL_PREFIX", "/static")
STATIC_DIR        = str((Path(__file__).resolve().parent / "static").resolve())
CENTER_IMG_SUBDIR = _getenv("CENTER_IMG_SUBDIR", "")
PUBLIC_BASE_URL   = _getenv("PUBLIC_BASE_URL", "")

# ─────────────────────────────────────────────────────────
# CORS
# 쉼표로 구분된 리스트
_CORS = _getenv(
    "CORS_ORIGINS",
    "http://localhost,http://127.0.0.1,"
    "http://localhost:8666,http://127.0.0.1:8666,"
    "http://localhost:8667,http://222.116.135.71:8666"
)
CORS_ORIGINS = [s.strip() for s in _CORS.split(",") if s.strip()]

# ─────────────────────────────────────────────────────────
# 네트워크/크롤링
HTTP_USER_AGENT    = _getenv("HTTP_USER_AGENT", "Mozilla/5.0 (compatible; CheonanURC-CleanBot/1.0)")
REQUEST_TIMEOUT_SEC= _getenv("REQUEST_TIMEOUT_SEC", 30, int)
CONCURRENCY        = _getenv("CONCURRENCY", 6, int)
BATCH_GATHER       = _getenv("BATCH_GATHER", 64, int)

SEEDS_FILE         = _getenv("SEEDS_FILE", None)

# 로컬 이미지 일괄 인제스트(선택)
LOCAL_IMAGE_ROOT   = _getenv("LOCAL_IMAGE_ROOT", "")
LOCAL_IMAGE_DEFAULT_CATEGORY = _getenv("LOCAL_IMAGE_DEFAULT_CATEGORY", "센터소개")

# ─────────────────────────────────────────────────────────
# OCR (크롤러)
ENABLE_OCR        = _getenv("ENABLE_OCR", "1") == "1"
OCR_BACKENDS      = [s.strip().lower() for s in _getenv("OCR_BACKENDS", "paddle,tesseract").split(",") if s.strip()]
OCR_LANG          = _getenv("OCR_LANG", "kor+eng")
OCR_MIN_CHARS     = _getenv("OCR_MIN_CHARS", 15, int)
OCR_ATTACH_TO_MD  = _getenv("OCR_ATTACH_TO_MD", "1") == "1"

OCR_MIN_CONF      = _getenv("OCR_MIN_CONF", 0.5, float)
PADDLE_OCR_LANG   = _getenv("PADDLE_OCR_LANG", None)
TESSERACT_CMD     = _getenv("TESSERACT_CMD", None)
MAX_GIF_FRAMES    = _getenv("MAX_GIF_FRAMES", 10, int)

OCR_USE_ENS       = _getenv("OCR_USE_ENS", "1") == "1"
OCR_ROTATE_ALL    = _getenv("OCR_ROTATE_ALL", "1") == "1"
OCR_SCALE_UP      = _getenv("OCR_SCALE_UP", 1.6, float)

# ─────────────────────────────────────────────────────────
# 기타
CHAT_PATH         = _getenv("CHAT_PATH", "/api/chat")
URC_STATE_TTL     = _getenv("URC_STATE_TTL", 1800, int)
URC_DEBUG         = _getenv("URC_DEBUG", "0") == "1"

def validate_runtime_env():
    missing = []
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if missing:
        raise RuntimeError(f"Missing runtime env: {', '.join(missing)}")
