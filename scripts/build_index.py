#!/usr/bin/env python3
# scripts/build_index.py  (clean 기반 인덱싱)
import os, glob, json
from pathlib import Path
from typing import Dict, Tuple

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from app.rag.embeddings import get_embedder  # ← 경로 주의!

# 1) 인덱싱 소스(클린 산출물)
CLEAN_DIR  = Path("app/data/clean")
# 2) 출력 FAISS 경로
INDEX_OUT  = Path("app/data/index.faiss")

splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=40)
texts, metas = [], []

def add_text(txt: str, meta: Dict):
    txt = (txt or "").strip()
    if not txt:
        return
    for ck in splitter.split_text(txt):
        if ck.strip():
            texts.append(ck)
            metas.append(meta)

def read_manifest(cat_dir: Path) -> Dict[str, Dict]:
    """
    카테고리 폴더의 manifest.jsonl 읽어서
    key=파일베이스명(slug-suffix) → {url, images[]} 매핑 반환
    """
    man = {}
    mf = cat_dir / "manifest.jsonl"
    if not mf.exists():
        return man
    with mf.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            text_path = obj.get("text_path", "")
            base = Path(text_path).stem if text_path else None
            if base:
                man[base] = {
                    "url": obj.get("url"),
                    "images": obj.get("images") or []
                }
    return man

def parse_markdown_title(md: str) -> Tuple[str, str]:
    """
    파일 상단의 '# 제목'과 '> Source: URL'을 찾아 반환.
    (없으면 빈 문자열)
    """
    title, source = "", ""
    for line in md.splitlines():
        s = line.strip()
        if not title and s.startswith("# "):
            title = s[2:].strip()
        elif not source and s.lower().startswith("> source:"):
            source = s.split(":", 1)[-1].strip()
        if title and source:
            break
    return title, source

# ─────────────────────────────────────────────────────────────
if not CLEAN_DIR.exists():
    raise RuntimeError(f"❗ 클린 디렉터리가 없습니다: {CLEAN_DIR}")

for cat_dir in sorted(p for p in CLEAN_DIR.iterdir() if p.is_dir()):
    text_dir = cat_dir / "text"
    if not text_dir.exists():
        continue

    manifest = read_manifest(cat_dir)

    # 모든 md 파일 재귀 스캔
    for fp in glob.glob(str(text_dir / "**" / "*.md"), recursive=True):
        p = Path(fp)
        md = p.read_text(encoding="utf-8", errors="ignore")
        title_md, src_in_md = parse_markdown_title(md)

        base = p.stem
        man = manifest.get(base, {})
        url = src_in_md or man.get("url")
        images = man.get("images") or []

        meta = {
            "source": fp,                  # 원본 md 경로
            "category": cat_dir.name,      # 카테고리명(센터소개/사업소개 등)
            "title": title_md,             # md 첫 헤더
            "url": url,                    # manifest 혹은 md 헤더에서 추출
            "images": images,              # 연관 이미지 경로 리스트
        }
        add_text(md, meta)

if not texts:
    raise RuntimeError(f"❗ 인덱싱할 텍스트가 없습니다: {CLEAN_DIR}/**/text/*.md")

store = FAISS.from_texts(texts, get_embedder(), metadatas=metas)
INDEX_OUT.parent.mkdir(parents=True, exist_ok=True)
store.save_local(str(INDEX_OUT))
print(f"✅ FAISS 인덱스 생성 완료: {INDEX_OUT} (chunks={len(texts)})")
