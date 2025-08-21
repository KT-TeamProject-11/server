# 천안재생센터 챗봇 백엔드 (FastAPI + RAG) 

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.1x-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Uvicorn](https://img.shields.io/badge/Uvicorn-Server-222222.svg)](https://www.uvicorn.org/)
[![FAISS](https://img.shields.io/badge/FAISS-RAG-1E90FF.svg)](https://github.com/facebookresearch/faiss)
[![HuggingFace](https://img.shields.io/badge/HuggingFace-Embeddings-ffcc4d.svg?logo=huggingface&logoColor=white)](https://huggingface.co/)


천안시 도시재생지원센터 전용 챗봇 백엔드입니다.    
FastAPI 서버에 RAG 파이프라인(FAISS + BM25 + 임베딩)을 얹어 `/api/chat`으로 들어온 질문에 답합니다.   
런타임 설정은 모두 `.env`로 관리합니다.  

---

## 목차
- [디렉터리 구조](#디렉터리-구조)
- [빠른 시작](#빠른-시작)
- [API](#api)
  - [POST `/api/chat`](#post-apichat)
  - [TTS (edge-tts)](#tts-edge-tts)
- [아키텍처 개요](#아키텍처-개요)
- [주요 환경변수](#주요-환경변수)
- [Makefile](#makefile)
- [프론트엔드 연동](#프론트엔드-연동)


---
## 디렉터리 구조

```
   ~~`~ server/
    ├─ app/
    │  ├─ __init__.py
    │  ├─ main.py                # FastAPI 시작점 (CORS/정적/라우터 마운트)
    │  ├─ config.py              # 모든 설정의 단일 진입점(.env 로드)
    │  ├─ api/
    │  │  ├─ routes.py           # /api/chat 등 일반 API 라우트
    │  │  └─ tts.py              # /api/tts/* (edge-tts; VOICE/RATE/VOLUME 환경변수화)
    │  ├─ crawler/
    │  │  └─ cheonanurc_clean.py # 크롤러+OCR(내/외부 SEEDS, 로컬 이미지 인제스트)
    │  └─ rag/
    │     ├─ __init__.py
    │     ├─ chatbot.py          # ask() 메인 로직
    │     ├─ retriever.py        # FAISS+BM25 병합 리트리버
    │     ├─ reranker.py         # (옵션) CrossEncoder 재랭크
    │     ├─ verifier.py         # fact_check()
    │     ├─ embeddings.py       # HuggingFace 임베더 (환경변수화)
    │     ├─ prompt.py           # LLM 프롬프트 템플릿
    │     └─ programs.py / faq.py 등
    ├─ data/
    │  ├─ raw/                   # 원본 자료(HTML/CSV/JSON/XML 등)
    │  └─ clean/                 # 크롤링/정제 산출물 (텍스트/이미지/OCR)
    ├─ build_index.py            # (예) 인덱스 생성 스크립트(FAISS 등)
    ├─ requirements.txt
    ├─ .env                      # 실제 환경설정 (비공개)
    ├─ .env.example              # 예시 환경설정
    └─ Makefile                  # `make run`, `make ingest` 등~`~~
```


---

## 빠른 시작

### 1) 저장소 클론
    git clone https://github.com/KT-TeamProject-11/server
    cd server

### 2) 가상환경 & 설치
    python -m venv venv
    source venv/bin/activate          # Windows: .\venv\Scripts\activate
    pip install -r requirements.txt   # 또는: make install

### 3) 환경변수 설정
    cp .env.example .env
    # .env 열어 OPENAI_API_KEY 등 값 채우기 (공백 포함 값은 "따옴표" 필수)

### 4) 데이터 준비
- (선택) **크롤링+OCR**로 `app/data/clean` 생성:
    
        python -m app.crawler.cheonanurc_clean

- (예시) **인덱스 생성**:
    
        python build_index.py

### 5) 개발 서버 실행
    uvicorn app.main:app --reload --env-file .env
    # 또는
    make run

Swagger UI:
- **Docs**: http://localhost:8555/docs

---

## API

### POST `/api/chat`
챗봇에게 질문을 보내고 답변을 받는 메인 엔드포인트.

**Request**
    
        { "message": "질문 내용" }

**Response**
    
        { "answer": "챗봇 응답" }

**cURL**
    
        curl -X POST http://localhost:8555/api/chat \
          -H "Content-Type: application/json" \
          -d '{"message":"센터 운영시간 알려줘"}'

---

### TTS (edge-tts)

- **POST** `/api/tts/speak`  
- **GET**  `/api/tts/speak?text=...&voice=...`  
- **GET**  `/api/tts/ping` (상태/현재 설정 확인)

`voice` 파라미터를 생략하면 `.env`의 `TTS_VOICE`를 사용합니다.

**예시**
    
        # GET
        curl -G http://localhost:8555/api/tts/speak --data-urlencode "text=안녕하세요"
        # POST
        curl -X POST http://localhost:8555/api/tts/speak \
          -H "Content-Type: application/json" \
          -d '{"text":"안녕하세요","voice":"ko-KR-SunHiNeural"}' --output out.mp3

---

## 아키텍처 개요

    [Client / Frontend]
            │  HTTP (POST /api/chat)
            ▼
    [FastAPI - app.main / app.api.routes]
            │  ask()
            ▼
    [RAG 파이프라인]
      1) FAQ/URL/규칙 확인
      2) Retriever(FAISS+BM25) → 문맥 수집
      3) (옵션) Reranker(CrossEncoder)
      4) LLM 프롬프트 구성 & 응답 생성
            ▼
    [JSON 응답: { "answer": "..." }]

---

## 주요 환경변수

```
    # LLM/OpenAI
    OPENAI_API_KEY=sk-xxxx
    OPENAI_MODEL=gpt-4o-mini
    OPENAI_TEMPERATURE=0.2
    MAX_COMPLETION_TOKENS=1024

    # RAG / 임베딩/인덱스
    EMBED_MODEL_ID=intfloat/e5-large-v2
    INDEX_DIR=app/data/index
    CLEAN_DIR=app/data/clean

    # Retriever 가중치
    RETRIEVER_K=12
    VEC_WEIGHT=0.7
    BM25_WEIGHT=0.3

    # (옵션) Reranker
    RERANK_MODEL_ID=khoj-ai/mxbai-rerank-base-v1
    RERANK_TOP_N=4

    # 캐시/Redis
    REDIS_URL=redis://localhost:6379/0
    CACHE_TTL_SEC=600

    # CORS (쉼표로 구분)
    CORS_ORIGINS=http://localhost,http://127.0.0.1,http://localhost:8666

    # 정적/퍼블릭
    STATIC_URL_PREFIX=/static
    PUBLIC_BASE_URL=http://localhost:8555

    # TTS
    TTS_VOICE=ko-KR-SunHiNeural
    TTS_RATE=-4%
    TTS_VOLUME=+0%
    TTS_MEDIA_TYPE=audio/mpeg

    # 크롤러/네트워크
    HTTP_USER_AGENT=Mozilla/5.0 (compatible; CheonanURC-CleanBot/1.0)
    REQUEST_TIMEOUT_SEC=30
    CONCURRENCY=6
    BATCH_GATHER=64

    # OCR
    ENABLE_OCR=1
    OCR_BACKENDS=paddle,tesseract
    OCR_LANG=kor+eng
    PADDLE_OCR_LANG=korean
    TESSERACT_CMD=/usr/bin/tesseract
    OCR_MIN_CONF=0.65
    OCR_MIN_CHARS=15
    OCR_USE_ENS=1
    OCR_ROTATE_ALL=1
    OCR_SCALE_UP=1.8
    MAX_GIF_FRAMES=10
    OCR_ATTACH_TO_MD=1

    # 로컬 이미지 인제스트
    # LOCAL_IMAGE_ROOT=/path/to/local/images
    LOCAL_IMAGE_DEFAULT_CATEGORY=센터소개

    # (선택) 외부 SEEDS 정의 파일
    # SEEDS_FILE=/path/to/seeds.json
```

---

## Makefile

    install:
    	pip install -r requirements.txt

    ingest:
    	python build_index.py

    run:
    	uvicorn app.main:app --reload --env-file .env

    health:
    	curl -s http://localhost:8555/ | jq .

    clean:
    	find . -type d -name "__pycache__" -exec rm -rf {} + || true

---


## 프론트엔드 연동

- (예시) 별도 프론트엔드 레포: https://github.com/KT-TeamProject-11/client_v2
- 기본은 백엔드 `http://localhost:8555`에 연결합니다.  
  프록시/도메인을 쓰는 경우 `.env` 또는 프런트 설정에서 API 베이스 URL을 맞춰 주세요.

