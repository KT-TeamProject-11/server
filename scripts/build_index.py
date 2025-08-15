# app/rag/build_index.py
from __future__ import annotations
import json, re
from pathlib import Path
from typing import List, Tuple, Optional

from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.rag.embeddings import get_embedder

try:
    from app.config import CLEAN_DIR as _CLEAN_DIR
except Exception:
    _CLEAN_DIR = "app/data/clean"
try:
    from app.config import INDEX_DIR as _INDEX_DIR
except Exception:
    _INDEX_DIR = "app/data/index"

CLEAN_DIR = Path(_CLEAN_DIR)
INDEX_DIR = Path(_INDEX_DIR)

_HDR_LINE   = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
_SOURCE_ROW = re.compile(r"^>\s*Source:\s*(.+)$", re.MULTILINE)

def split_markdown_sections(md_text: str) -> List[Tuple[str, str]]:
    lines = md_text.splitlines()
    sections: List[Tuple[str, str]] = []
    stack: List[Tuple[int, str]] = []
    buf: List[str] = []
    current_path = ""

    def push():
        if buf:
            sections.append((current_path.strip(), "\n".join(buf).strip()))
            buf.clear()

    for line in lines:
        m = _HDR_LINE.match(line)
        if not m:
            buf.append(line); continue
        push()
        level = len(m.group(1))
        text  = m.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, text))
        current_path = " > ".join([t for _, t in stack])

    push()
    sections = [(h, t) for h, t in sections if t.strip()]
    return sections or [("", md_text.strip())]

def first_heading(md_text: str) -> Optional[str]:
    m = _HDR_LINE.search(md_text)
    return m.group(2).strip() if m else None

def extract_source_url_from_md(md_text: str) -> Optional[str]:
    m = _SOURCE_ROW.search(md_text)
    return m.group(1).strip() if m else None

def iter_markdowns() -> List[Tuple[Path, str, str, str]]:
    items: List[Tuple[Path, str, str, str]] = []
    for md in CLEAN_DIR.glob("**/*.md"):
        if md.name.lower() == "readme.md": 
            continue
        try:
            category = md.parents[1].name
        except Exception:
            category = md.parent.name
        text = md.read_text(encoding="utf-8", errors="ignore")
        title = first_heading(text) or md.stem
        url = extract_source_url_from_md(text) or ""
        items.append((md, category, title, url))
    return items

def build():
    items = iter_markdowns()
    if not items:
        raise RuntimeError(f"❗ 인덱싱할 md가 없습니다: {CLEAN_DIR}/**/*.md")

    splitter = RecursiveCharacterTextSplitter(
        separators=["\n### ", "\n## ", "\n# ", "\n\n", "\n", " "],
        chunk_size=800, chunk_overlap=120
    )

    docs: List[Document] = []
    for md_path, category, title, url in items:
        raw = md_path.read_text(encoding="utf-8", errors="ignore")
        sections = split_markdown_sections(raw)
        for heading_path, text in sections:
            for ch in splitter.split_text(text):
                meta = {
                    "source": str(md_path),
                    "category": category,
                    "title": title,
                    "section": heading_path,
                    "url": url,
                }
                payload = f"[{title}{(' · ' + heading_path) if heading_path else ''}]\n{ch}"
                docs.append(Document(page_content=payload, metadata=meta))

        # OCR 사이드카(.txt)가 있고, md에 붙이지 않았다면 별도 문서로 인덱스
        img_dir = md_path.parents[1] / "images"
        if img_dir.exists():
            for txt in img_dir.glob("**/*.txt"):
                try:
                    ocr_txt = txt.read_text(encoding="utf-8", errors="ignore").strip()
                except Exception:
                    ocr_txt = ""
                if not ocr_txt:
                    continue
                meta = {
                    "source": str(txt),
                    "category": category,
                    "title": f"{title} (OCR)",
                    "section": txt.name,
                    "url": url,
                }
                docs.append(Document(page_content=f"[{title} · OCR]\n{ocr_txt}", metadata=meta))

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    vs = FAISS.from_documents(docs, get_embedder())
    vs.save_local(str(INDEX_DIR))
    print(f"✅ 인덱스 저장 완료: {INDEX_DIR} (docs={len(docs)})")

if __name__ == "__main__":
    build()
