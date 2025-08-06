#!/usr/bin/env python3
import sys
import os

# 1) 프로젝트 루트를 PYTHONPATH에 추가 (–m 모드로 실행하면 필요 없습니다)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import glob
import json
import csv
import xml.etree.ElementTree as ET
from pathlib import Path

from bs4 import BeautifulSoup
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.rag.embeddings import get_embedder
from langchain_community.vectorstores import FAISS

# 크롤링된 원본 데이터 디렉터리
RAW_DIR = Path("app/data/raw")
# 생성할 FAISS 인덱스 경로
INDEX_OUT = Path("app/data/index.faiss")

# 텍스트 청크 분할기
splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=40)

texts, metas = [], []

# ── 1) HTML 파일 처리 ─────────────────
for fp in glob.glob(str(RAW_DIR / "*.html")):
    raw = Path(fp).read_text(encoding="utf-8", errors="ignore")
    txt = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    for chunk in splitter.split_text(txt):
        texts.append(chunk)
        metas.append({"source": fp})

# ── 2) CSV 파일 처리 ──────────────────
for fp in glob.glob(str(RAW_DIR / "*.csv")):
    with open(fp, newline="", encoding="utf-8", errors="ignore") as fh:
        reader = csv.reader(fh)
        for row in reader:
            row_txt = " | ".join(row)
            for chunk in splitter.split_text(row_txt):
                texts.append(chunk)
                metas.append({"source": fp})

# ── 3) JSON 파일 처리 ─────────────────
def _flatten(obj):
    if isinstance(obj, dict):
        return " ".join(_flatten(v) for v in obj.values())
    if isinstance(obj, list):
        return " ".join(_flatten(v) for v in obj)
    return str(obj)

for fp in glob.glob(str(RAW_DIR / "*.json")):
    with open(fp, encoding="utf-8", errors="ignore") as fh:
        data = json.load(fh)
    txt = _flatten(data)
    for chunk in splitter.split_text(txt):
        texts.append(chunk)
        metas.append({"source": fp})

# ── 4) XML 파일 처리 ──────────────────
for fp in glob.glob(str(RAW_DIR / "*.xml")):
    tree = ET.parse(fp)
    root = tree.getroot()
    txt = " ".join(elem.text.strip() for elem in root.iter() if elem.text)
    for chunk in splitter.split_text(txt):
        texts.append(chunk)
        metas.append({"source": fp})

# ── 5) FAISS 인덱스 생성 & 저장 ────────
store = FAISS.from_texts(
    texts,
    get_embedder(),
    metadatas=metas
)

# 인덱스 디렉터리 없으면 생성
INDEX_OUT.parent.mkdir(parents=True, exist_ok=True)
store.save_local(str(INDEX_OUT))

print("✅ FAISS 인덱스 생성 완료:", INDEX_OUT)
