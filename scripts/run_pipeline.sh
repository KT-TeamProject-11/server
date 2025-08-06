#!/usr/bin/env bash
set -e

# 1) 스크립트 위치를 기준으로 프로젝트 루트로 이동
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "[$(date '+%F %T')] 크롤링 시작..."
# 2) 가상환경 활성화
source venv/bin/activate
# 3) 크롤러 실행 (앱 패키지 인식 가능)
python -m app.crawler.cheonanurc

echo "[$(date '+%F %T')] 인덱스 생성 시작..."
# 4) 인덱스 빌드
python -m scripts.build_index

echo "[$(date '+%F %T')] 서비스 재시작..."
sudo systemctl restart urc-chatbot

echo "[$(date '+%F %T')] 완료."
