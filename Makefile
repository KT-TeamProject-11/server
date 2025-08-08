# 스크립트 실행을 위해 bash 셸을 기본으로 설정합니다.
SHELL := /bin/bash

# --- 변수 정의 ---
PYTHON   = python3
UVICORN  = uvicorn
APP      = app.main:app
PORT     = 8555
HOST     = 0.0.0.0
ENV_FILE ?= .env

# .PHONY: 파일 이름과 충돌하지 않도록 가상 타겟을 선언합니다.
.PHONY: help default install ingest run check-env health clean

# `make`만 입력했을 때 기본으로 실행될 목표를 'help'로 지정합니다.
default: help

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo "  install    - requirements.txt를 기반으로 패키지를 설치합니다."
	@echo "  ingest     - 데이터 인덱싱 스크립트를 실행합니다."
	@echo "  run        - FastAPI 개발 서버를 시작합니다. (환경 변수 체크 포함)"
	@echo "  check-env  - .env 파일과 필수 변수(OPENAI_API_KEY)의 존재 여부를 확인합니다."
	@echo "  health     - 실행 중인 서버의 상태를 확인합니다."
	@echo "  clean      - 임시 파이썬 파일(__pycache__, .pyc)을 삭제합니다."

install:
	@echo "--> 📦 의존성 패키지를 설치합니다..."
	@$(PYTHON) -m pip install -U pip
	@$(PYTHON) -m pip install -r requirements.txt

ingest:
	@echo "--> 🚚 데이터 인덱싱을 시작합니다..."
	@$(PYTHON) scripts/ingest.py

# 'run'을 실행하기 전에 'check-env'를 먼저 실행하여 환경을 검증합니다.
run: check-env
	@echo "--> 🚀 FastAPI 서버를 http://$(HOST):$(PORT) 에서 시작합니다..."
	@# 셸에서 직접 .env 파일을 로드한 후 uvicorn을 실행하여 안정성을 높입니다.
	@set -a; source "$(ENV_FILE)"; set +a; \
	exec $(UVICORN) $(APP) --host $(HOST) --port $(PORT) --reload

check-env:
	@echo "--> 🧐 .env 환경 설정을 확인합니다..."
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "🚨 오류: $(ENV_FILE) 파일을 찾을 수 없습니다." >&2; \
		exit 1; \
	fi
	@set -a; source "$(ENV_FILE)"; set +a; \
	if [ -z "$${OPENAI_API_KEY}" ]; then \
		echo "🚨 오류: $(ENV_FILE) 파일에 OPENAI_API_KEY가 설정되지 않았습니다." >&2; \
		exit 1; \
	fi
	@echo "--> ✅ 환경 설정이 올바릅니다."

health:
	@echo "--> ❤️ 서버 상태를 확인합니다..."
	@curl -s -o /dev/null -w "서버 상태: %{http_code}\n" http://localhost:$(PORT)/ || echo "🚨 오류: 서버에 연결할 수 없습니다."

clean:
	@echo "--> 🧹 임시 파일들을 삭제합니다..."
	@find . -type f -name '*.py[co]' -delete
	@find . -type d -name '__pycache__' -exec rm -rf {} +