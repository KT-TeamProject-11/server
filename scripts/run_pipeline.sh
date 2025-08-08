#!/usr/bin/env bash
set -euo pipefail

# ── 설정 ─────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

VENV_DIR="venv"
SERVICE_NAME="urc-chatbot"

MODE="${1:-clean}"         # clean | raw
RESTART="${2:-yes}"        # yes | no

usage() {
  cat <<'EOF'
Usage: bash scripts/run_pipeline.sh [clean|raw] [yes|no]
  clean : app/crawler/cheonanurc_clean.py 실행 후 scripts/build_index.py로 인덱싱 (기본)
  raw   : app/crawler/cheonanurc.py 실행 후 scripts/build_index.py로 인덱싱 (raw만 쓰려면 스크립트 수정 필요)
  yes/no: 마지막에 systemctl restart urc-chatbot 수행 여부 (기본 yes)
Examples:
  bash scripts/run_pipeline.sh                # clean + restart
  bash scripts/run_pipeline.sh clean no       # clean만 돌리고 재시작 안 함
  bash scripts/run_pipeline.sh raw yes        # raw 크롤링 후 인덱싱 + 재시작
EOF
}

# ── venv 체크 ────────────────────────────────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
  echo "❗ ${VENV_DIR} 가 없습니다. 먼저 가상환경을 생성하세요."
  exit 1
fi

echo "[$(date '+%F %T')] 가상환경 활성화..."
# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

# ── 크롤링 ──────────────────────────────────────────────────
echo "[$(date '+%F %T')] 크롤링 시작... (mode=${MODE})"
case "$MODE" in
  clean)
    # 텍스트(.md) + 주요 이미지 추출
    python -m app.crawler.cheonanurc_clean
    ;;
  raw)
    # 원본 HTML 중심 크롤링
    python -m app.crawler.cheonanurc
    ;;
  *)
    usage; exit 1;;
esac

# ── 인덱싱 ──────────────────────────────────────────────────
echo "[$(date '+%F %T')] 인덱스 생성 시작..."
python -m scripts.build_index

# ── 서비스 재시작 ───────────────────────────────────────────
if [[ "${RESTART}" == "yes" ]]; then
  echo "[$(date '+%F %T')] 서비스 재시작..."
  sudo systemctl restart "${SERVICE_NAME}"
else
  echo "[$(date '+%F %T')] 서비스 재시작 건너뜀."
fi

echo "[$(date '+%F %T')] 완료."
