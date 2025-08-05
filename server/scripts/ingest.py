from pathlib import Path
import sys
ROOT_DIR = Path(__file__).resolve().parent.parent  
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
import glob, json, csv, xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from dotenv import load_dotenv, find_dotenv
from tqdm import tqdm
from langchain.text_splitter          import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from app.rag.embeddings               import get_embedder

load_dotenv(find_dotenv())

RAW_DIR   = Path("app/data/raw")
INDEX_OUT = Path("app/data/index.faiss")

splitter  = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=40)
chunks: list[str] = []
metas : list[dict] = []
## hi
# ── 1) HTML ────────────────────────────────────────────────
for fp in glob.glob(f"{RAW_DIR}/**/*.html", recursive=True):
    with open(fp, encoding="utf-8") as fh:
        soup = BeautifulSoup(fh, "html.parser")
    for tag in soup.select("script, style, nav, footer, header"):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    for ck in splitter.split_text(text):
        chunks.append(ck); metas.append({"source": fp})

# ── 2) CSV ─────────────────────────────────────────────────
for fp in glob.glob(f"{RAW_DIR}/**/*.csv", recursive=True):
    with open(fp, newline="", encoding="utf-8") as fh:
        rdr = csv.reader(fh)
        for row in rdr:
            for ck in splitter.split_text(" | ".join(row)):
                chunks.append(ck); metas.append({"source": fp})

# ── 3) JSON ────────────────────────────────────────────────
def _flatten(obj):
    if isinstance(obj, dict):
        return " ".join(_flatten(v) for v in obj.values())
    if isinstance(obj, list):
        return " ".join(_flatten(v) for v in obj)
    return str(obj)

for fp in glob.glob(f"{RAW_DIR}/**/*.json", recursive=True):
    with open(fp, encoding="utf-8") as fh:
        txt = _flatten(json.load(fh))
    for ck in splitter.split_text(txt):
        chunks.append(ck); metas.append({"source": fp})

# ── 4) XML ────────────────────────────────────────────────
for fp in glob.glob(f"{RAW_DIR}/**/*.xml", recursive=True):
    root = ET.parse(fp).getroot()
    txt  = " ".join(e.text.strip() for e in root.iter() if e.text)
    for ck in splitter.split_text(txt):
        chunks.append(ck); metas.append({"source": fp})

if not chunks:
    raise RuntimeError("❗  RAW_DIR 에서 인제스트할 파일을 찾지 못했습니다.")

store = FAISS.from_texts(
    chunks,
    get_embedder(),
    metadatas=metas,
)

INDEX_OUT.parent.mkdir(parents=True, exist_ok=True)
store.save_local(str(INDEX_OUT))
print(f"✅  인제스트 완료  ({len(chunks)} chunks)  ➜  {INDEX_OUT}")
