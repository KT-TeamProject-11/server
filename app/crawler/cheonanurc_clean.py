# -*- coding: utf-8 -*-
"""
천안 URC 크롤러(클린 버전) + 이미지 OCR(개선판) + 로컬 이미지 인제스트
- 내부 도메인: BFS 확장하여 본문/이미지 저장
- 외부 도메인: 1-hop 저장
- 공통: 저장 즉시 OCR → .txt 사이드카 저장 + manifest.jsonl 기록
- 로컬 이미지 인제스트: app/crawler/images/<문서폴더>/*.png|jpg|gif ...
  (폴더 1개 = 문서 1개로 취급)
개선점:
- PaddleOCR 기반 한국어 강화 + 전처리 앙상블 + 회전 시도 + 한글 띄어쓰기 보정
"""

import os
import re
import io
import json
import shutil
import asyncio
import hashlib
import contextlib
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse

import aiohttp
from bs4 import BeautifulSoup

# ────────────────────────────────────────────────────────────
# OCR 옵션 (환경변수로 제어)
ENABLE_OCR: bool   = os.getenv("ENABLE_OCR", "1") == "1"
OCR_BACKEND: str   = os.getenv("OCR_BACKEND", "paddle").lower()  # "paddle" | "tesseract"
OCR_LANG: str      = os.getenv("OCR_LANG", "kor+eng")            # tesseract 호환 표기
OCR_MIN_CHARS: int = int(os.getenv("OCR_MIN_CHARS", "15"))       # 너무 짧은 노이즈는 버림
OCR_ATTACH_TO_MD: bool = os.getenv("OCR_ATTACH_TO_MD", "1") == "1"

# 인식률 개선용 옵션
OCR_MIN_CONF: float = float(os.getenv("OCR_MIN_CONF", "0.5"))    # PaddleOCR 신뢰도 필터
PADDLE_OCR_LANG: Optional[str] = os.getenv("PADDLE_OCR_LANG")    # 기본 None → 자동 유추
TESSERACT_CMD: Optional[str] = os.getenv("TESSERACT_CMD")        # /usr/bin/tesseract 등
MAX_GIF_FRAMES: int = int(os.getenv("MAX_GIF_FRAMES", "10"))

# 앙상블/회전/스케일 옵션
OCR_USE_ENS: bool   = os.getenv("OCR_USE_ENS", "1") == "1"       # 전처리 앙상블 사용
OCR_ROTATE_ALL: bool= os.getenv("OCR_ROTATE_ALL", "1") == "1"    # 0/90/180/270 모두 시도
OCR_SCALE_UP: float = float(os.getenv("OCR_SCALE_UP", "1.6"))    # 작은 글자 확대 배율(<=2 추천)

# pytesseract / PIL
_TESS_AVAILABLE = False
try:
    import pytesseract
    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    from PIL import Image, ImageOps, ImageSequence, ImageChops, ImageFilter
    _TESS_AVAILABLE = True
except Exception:
    Image = None            # type: ignore
    ImageOps = None         # type: ignore
    ImageSequence = None    # type: ignore
    ImageChops = None       # type: ignore
    ImageFilter = None      # type: ignore

# OpenCV
try:
    import cv2
    _CV2 = True
except Exception:
    _CV2 = False

# PaddleOCR (기본 백엔드)
_PADDLE_AVAILABLE = False
_paddle_ocr = None
try:
    from paddleocr import PaddleOCR  # type: ignore
    _PADDLE_AVAILABLE = True
except Exception:
    _PADDLE_AVAILABLE = False

def _infer_paddle_lang(ocr_lang: str, explicit: Optional[str]) -> str:
    """
    PaddleOCR 언어 우선순위 추론:
      - 명시 env(PADDLE_OCR_LANG) 있으면 그 값
      - OCR_LANG에 'kor'/'ko' 포함 → 'korean'
      - 그 외 → 'en'
    """
    if explicit:
        return explicit
    s = (ocr_lang or "").lower()
    if "kor" in s or "ko" in s:
        return "korean"
    return "en"

if ENABLE_OCR and _PADDLE_AVAILABLE and OCR_BACKEND == "paddle":
    with contextlib.suppress(Exception):
        _paddle_ocr = PaddleOCR(
            lang=_infer_paddle_lang(OCR_LANG, PADDLE_OCR_LANG),
            use_angle_cls=True,    # 각도 분류기 사용
            show_log=False
        )

# ────────────────────────────────────────────────────────────
# 로컬 이미지 기본 루트들: images / img 둘 다 자동 탐지
_DEFAULT_LOCAL_ROOTS = [
    Path(__file__).resolve().parent / "images",
    Path(__file__).resolve().parent / "img",
]
_LOCAL_ENV = os.getenv("LOCAL_IMAGE_ROOT", "")
LOCAL_IMAGE_ROOTS = [Path(_LOCAL_ENV)] if _LOCAL_ENV else [p for p in _DEFAULT_LOCAL_ROOTS if p.exists()]

# 저장 베이스: app/data/clean
CLEAN_BASE = Path(__file__).resolve().parent.parent / "data" / "clean"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CheonanURC-CleanBot/1.0)"}
CONCURRENCY = 6
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
BATCH_GATHER = 64

# 저장할 이미지 확장자 (OCR는 래스터 이미지에만 적용)
IMG_EXTS    = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".avif", ".jp2", ".svg")
RASTER_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".jp2", ".gif")  # svg/avif는 OCR 스킵

# ────────────────────────────────────────────────────────────
# 홈페이지 SEEDS
SEEDS = {
    "main": ["https://www.cheonanurc.or.kr/"],
    "instagram": [
        "https://www.instagram.com/cheonan_urc/?hl=ko",
        "https://www.instagram.com/cheonan.want/?hl=ko",
        "https://www.instagram.com/cheonan_base/",
    ],
    "blog": [
        "https://blog.naver.com/urc-cheonan",
        "https://blog.naver.com/tongdol2020",
    ],
    "youtube": ["https://www.youtube.com/channel/UCnmu-XM_ssRWVnwmCUVmFGg"],
    "band": ["https://www.band.us/band/86255676"],

    # 내부 카테고리
    "센터소개": ["https://www.cheonanurc.or.kr/24","https://www.cheonanurc.or.kr/79","https://www.cheonanurc.or.kr/101","https://www.cheonanurc.or.kr/25","https://www.cheonanurc.or.kr/131","https://www.cheonanurc.or.kr/133","https://www.cheonanurc.or.kr/128"],
    "사업소개": ["https://www.cheonanurc.or.kr/68","https://www.cheonanurc.or.kr/27","https://www.cheonanurc.or.kr/71","https://www.cheonanurc.or.kr/70","https://www.cheonanurc.or.kr/72","https://www.cheonanurc.or.kr/74","https://www.cheonanurc.or.kr/75","https://www.cheonanurc.or.kr/73","https://www.cheonanurc.or.kr/140"],
    "커뮤니티": ["https://www.cheonanurc.or.kr/92","https://www.cheonanurc.or.kr/95","https://www.cheonanurc.or.kr/121"],
    "도시재생+": ["https://www.cheonanurc.or.kr/new","https://www.cheonanurc.or.kr/41","https://www.cheonanurc.or.kr/64","https://www.cheonanurc.or.kr/78","https://www.cheonanurc.or.kr/97","https://www.cheonanurc.or.kr/98","https://www.cheonanurc.or.kr/99","https://www.cheonanurc.or.kr/100", "https://www.cheonanurc.or.kr/144"],
    "아카이브": ["https://www.cheonanurc.or.kr/36","https://www.cheonanurc.or.kr/35","https://www.cheonanurc.or.kr/37","https://www.cheonanurc.or.kr/108"],
}

# ────────────────────────────────────────────────────────────
def normalize_url(u: str) -> str:
    pu = urlparse(u)
    clean_query = "&".join(p for p in pu.query.split("&") if p and not p.lower().startswith(("utm_", "fbclid")))
    return urlunparse((pu.scheme, pu.netloc, pu.path.rstrip("/"), pu.params, clean_query, ""))

def slugify(title: str) -> str:
    title = re.sub(r"\s+", " ", (title or "")).strip()
    s = re.sub(r"[^0-9A-Za-z가-힣]+", "-", title).strip("-")
    return s[:80] if s else "page"

def page_id_from_path(path: str) -> Optional[str]:
    m = re.search(r"/(\d+)$", path or "")
    return m.group(1) if m else None

# ────────────────────────────────────────────────────────────
def strip_chrome(soup: BeautifulSoup) -> None:
    selectors = [
        "nav","header","footer","aside","form","iframe","noscript",".gnb",".lnb",".breadcrumb",".breadcrumbs",".pagination",
        ".pager",".skip",".sr-only",".sr_only",".sns",".share",".social",".banner",".ad",".advert",".visual",".btn",".btn-group",".btns",".actions",".toolbar",
        "#gnb","#lnb","#footer","#header","#nav","#quick"
    ]
    for sel in selectors:
        for t in soup.select(sel):
            t.decompose()
    noise_keywords = ["뒤로","더보기","접기","열기","로그인","로그아웃","마이페이지","Alarm","공지사항","바로가기","TOP","맨위로","검색","내 글 반응","게시물 알림"]
    for a in list(soup.find_all(["a","button","span","div"])):
        txt = (a.get_text(" ", strip=True) or "")[:20]
        if any(k in txt for k in noise_keywords):
            a.decompose()

def pick_main_node(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    strip_chrome(soup)
    candidates: List[Tuple[float, int, BeautifulSoup]] = []
    priors = ["article","#content",".content","#main",".entry-content",".post",".board_view",".sub_content",".view"]
    for sel in priors:
        for node in soup.select(sel):
            text = node.get_text(" ", strip=True)
            if len(text) >= 100:
                candidates.append((len(text), 3, node))
    if not candidates:
        for node in soup.find_all(["section","div"]):
            raw = node.get_text(" ", strip=True)
            if len(raw) < 200: continue
            links = len(node.find_all("a"))
            words = max(1, len(raw.split()))
            link_ratio = links / words
            score = len(raw) * (1.0 - min(link_ratio, 0.6))
            candidates.append((score, 1, node))
    if not candidates:
        return soup.body or soup
    candidates.sort(key=lambda t: (-t[1], -t[0]))
    return candidates[0][2]

def html_table_to_md(tbl: BeautifulSoup) -> str:
    headers = []
    thead = tbl.find("thead")
    if thead:
        ths = thead.find_all(["th","td"])
        headers = [th.get_text(" ", strip=True) for th in ths if th.get_text(strip=True)]
    rows = []
    tbody = tbl.find("tbody") or tbl
    for tr in tbody.find_all("tr"):
        cells = tr.find_all(["th","td"])
        if not cells: continue
        row = [c.get_text(" ", strip=True) for c in cells]
        if any(cell for cell in row):
            rows.append(row)
    md = []
    if headers:
        md.append("| " + " | ".join(headers) + " |")
        md.append("| " + " | ".join("---" for _ in headers) + " |")
    for r in rows:
        md.append("| " + " | ".join(r) + " |")
    return "\n".join(md)

def html_to_markdown(node: BeautifulSoup) -> str:
    for tag in node.find_all(["br"]): tag.replace_with("\n")
    for tag in node.find_all(["p","li","blockquote"]):
        if tag.text and not tag.text.endswith("\n"): tag.append("\n")
    for tag in node.find_all(["h1","h2","h3","h4","h5","h6"]):
        level = int(tag.name[1]); prefix = "#" * min(level, 6)
        content = tag.get_text(" ", strip=True); tag.clear(); tag.append(f"{prefix} {content}\n")
    for tbl in node.find_all("table"):
        md_tbl = html_table_to_md(tbl)
        tbl.replace_with(BeautifulSoup("\n"+md_tbl+"\n", "html.parser"))
    for junk in node.select("script, style"): junk.decompose()
    text = node.get_text("\n", strip=True)
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    cleaned = []
    for ln in lines:
        if ln.startswith("| ") or ln.startswith("#"): cleaned.append(ln); continue
        if len(ln) < 2: continue
        cleaned.append(ln)
    dedup = []
    for ln in cleaned:
        if not dedup or dedup[-1] != ln: dedup.append(ln)
    return "\n".join(dedup).strip()

# ────────────────────────────────────────────────────────────
def extract_text_and_images(soup: BeautifulSoup, base_url: str) -> Tuple[str, List[str]]:
    main = pick_main_node(soup)
    if not main:
        return "", []
    md_text = html_to_markdown(main)
    urls = set()
    og = soup.select_one('meta[property="og:image"]')
    if og and og.get("content"): urls.add(urljoin(base_url, og["content"].strip()))
    for img in main.select("img[src]"):
        src = (img.get("src") or "").strip()
        if not src: continue
        absu = urljoin(base_url, src)
        ext = os.path.splitext(urlparse(absu).path.lower())[1]
        if not ext or ext in IMG_EXTS:
            urls.add(absu)
    return md_text, list(urls)

async def fetch_html(session: aiohttp.ClientSession, url: str) -> Tuple[int, str]:
    for attempt in range(3):
        try:
            async with session.get(url, timeout=REQUEST_TIMEOUT) as r:
                return r.status, await r.text(errors="ignore")
        except Exception:
            await asyncio.sleep(0.8 * (attempt + 1))
    return 0, ""

async def fetch_image_bytes(session: aiohttp.ClientSession, url: str) -> bytes:
    for attempt in range(2):
        try:
            async with session.get(url, timeout=REQUEST_TIMEOUT) as r:
                if r.status != 200:
                    continue
                return await r.read()
        except Exception:
            await asyncio.sleep(0.5 * (attempt + 1))
    return b""

def paths_for_clean(category: str, slug: str, suffix: str):
    base_dir = CLEAN_BASE / category
    text_dir = base_dir / "text"
    img_dir  = base_dir / "images" / f"{slug}-{suffix}"
    text_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)
    manifest_fp = base_dir / "manifest.jsonl"
    return text_dir, img_dir, manifest_fp

# ────────────────────────────────────────────────────────────
# OCR 유틸 - 전처리/후처리/앙상블

def _cv2_from_pil(img: "Image.Image"):
    import numpy as np
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def _pil_from_cv2(arr) -> "Image.Image":
    import numpy as np
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))

def _resize_scale_up(img: "Image.Image") -> "Image.Image":
    if OCR_SCALE_UP <= 1.01:
        return img
    w, h = img.size
    nw, nh = int(w * OCR_SCALE_UP), int(h * OCR_SCALE_UP)
    return img.resize((nw, nh))

def _preprocess_variants_pil(img: "Image.Image") -> List["Image.Image"]:
    """
    여러 전처리 버전을 생성해 앙상블로 OCR 후 최적 결과 선택
    """
    variants: List["Image.Image"] = []
    base = _resize_scale_up(img)

    # 0) 원본
    variants.append(base)

    if not _CV2:
        # PIL만 있을 때 간단 전처리
        if ImageOps:
            gray = ImageOps.grayscale(base)
            variants.append(gray)
        if ImageFilter:
            sharp = base.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
            variants.append(sharp)
        return variants

    # OpenCV 기반 고급 전처리
    bgr = _cv2_from_pil(base)

    # 1) CLAHE (LAB 공간 L 채널)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    l2 = clahe.apply(l)
    lab2 = cv2.merge([l2, a, b])
    bgr_clahe = cv2.cvtColor(lab2, cv2.COLOR_LAB2BGR)
    variants.append(_pil_from_cv2(bgr_clahe))

    # 2) 언샵 샤프닝
    gauss = cv2.GaussianBlur(bgr, (0,0), 1.0)
    unsharp = cv2.addWeighted(bgr, 1.5, gauss, -0.5, 0)
    variants.append(_pil_from_cv2(unsharp))

    # 3) 적응형 이진화(가독성 향상)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    bin1 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                 cv2.THRESH_BINARY, 35, 11)
    bin1 = cv2.medianBlur(bin1, 3)
    variants.append(Image.fromarray(bin1))

    # 4) 대비↑ + 샤프
    alpha, beta = 1.2, 5  # contrast, brightness
    highc = cv2.convertScaleAbs(bgr, alpha=alpha, beta=beta)
    gauss2 = cv2.GaussianBlur(highc, (0,0), 0.8)
    sharp2 = cv2.addWeighted(highc, 1.4, gauss2, -0.4, 0)
    variants.append(_pil_from_cv2(sharp2))

    return variants

def _preprocess_for_ocr_cv2(buf: bytes) -> Optional["Image.Image"]:  # type: ignore
    if not _CV2:
        return None
    import numpy as np
    im = cv2.imdecode(np.frombuffer(buf, dtype=np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        return None
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3,3), 0)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    h, w = th.shape
    max_side = 1600
    scale = min(max_side / max(w, h), 2.0)
    if scale > 1.0:
        th = cv2.resize(th, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_LINEAR)
    if Image is None:
        return None
    return Image.fromarray(th)  # type: ignore

def _pil_from_bytes(buf: bytes) -> Optional["Image.Image"]:  # type: ignore
    if Image is None:
        return None
    with contextlib.suppress(Exception):
        return Image.open(io.BytesIO(buf))
    return None

def _preprocess_for_ocr_pil(img: "Image.Image") -> "Image.Image":  # type: ignore
    if ImageOps is None:
        return img
    gray = ImageOps.grayscale(img)  # type: ignore
    max_side = 1600
    w, h = gray.size
    scale = min(max_side / max(w, h), 2.0)
    if scale > 1.0:
        gray = gray.resize((int(w*scale), int(h*scale)))
    return gray

def _extract_pil_frames(buf: bytes) -> List["Image.Image"]:  # type: ignore
    """
    GIF면 여러 프레임 추출(최대 MAX_GIF_FRAMES), 그 외 포맷은 단일 프레임 반환
    중복 프레임은 제거하여 OCR 낭비 최소화
    """
    im = _pil_from_bytes(buf)
    if im is None:
        return []
    frames: List["Image.Image"] = []

    if (im.format or "").upper() == "GIF" and ImageSequence is not None:
        with contextlib.suppress(Exception):
            prev = None
            count = 0
            for fr in ImageSequence.Iterator(im):  # type: ignore
                if count >= MAX_GIF_FRAMES:
                    break
                fr = fr.convert("RGB")
                if prev is not None and ImageChops is not None:
                    diff = ImageChops.difference(prev, fr)  # type: ignore
                    if diff.getbbox() is None:
                        continue
                frames.append(fr)
                prev = fr
                count += 1
    else:
        frames.append(im.convert("RGB"))

    return [_preprocess_for_ocr_pil(f) for f in frames]

# ── 후처리: 한글 분절 자동 결합, 공백/중복 정리 ──────────────────────────
_HANGUL_BLOCK = r"[가-힣]"
def _merge_hangul_separated_words(text: str) -> str:
    """
    '도 시 재 생 센 터' 같이 한글 사이사이 스페이스가 들어간 구간을 붙여줌.
    """
    def _merge_block(m):
        return re.sub(r"\s+", "", m.group(0))
    # 2자 이상 연속한글에 끼어든 공백 패턴을 찾아 합침
    pattern = rf"((?:{_HANGUL_BLOCK}\s+){{1,}}{_HANGUL_BLOCK})"
    return re.sub(pattern, _merge_block, text)

def _post_process_korean(text: str) -> str:
    t = text
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\s*\n\s*", "\n", t)
    t = re.sub(r"([.,!?])\1{2,}", r"\1\1", t)  # 과다한 반복 구두점 축소
    t = _merge_hangul_separated_words(t)
    # 행 단위 중복 제거
    lines = []
    seen = set()
    for ln in t.splitlines():
        k = ln.strip()
        if not k:
            continue
        if k not in seen:
            lines.append(k)
            seen.add(k)
    return "\n".join(lines)

# ── PaddleOCR 실행 ──────────────────────────────────────────
def _paddle_ocr_once(img: "Image.Image") -> Tuple[str, float]:
    """
    단일 이미지에 대해 PaddleOCR 실행 → (텍스트, 총점) 반환
    총점 = Σ(conf * len(text))
    """
    if not _paddle_ocr:
        return "", 0.0
    import numpy as np
    arr = np.array(img)
    res = _paddle_ocr.ocr(arr, cls=True)
    lines: List[str] = []
    score_sum = 0.0
    if isinstance(res, list):
        for page in res:
            if not page:
                continue
            for item in page:
                if not item or len(item) < 2:
                    continue
                info = item[1]
                if not isinstance(info, (list, tuple)) or len(info) < 2:
                    continue
                txt, conf = info[0], float(info[1])
                if conf >= OCR_MIN_CONF and (txt or "").strip():
                    lines.append(txt.strip())
                    score_sum += conf * max(1, len(txt.strip()))
    joined = "\n".join(lines).strip()
    return joined, score_sum

def _ocr_paddle_frames_ensemble(frames: List["Image.Image"]) -> str:  # type: ignore
    """
    프레임 단위로 전처리 앙상블 + 회전 시도 → 최고 스코어 결과 채택
    """
    if not frames or not _paddle_ocr:
        return ""

    best_texts: List[str] = []
    for i, base_frame in enumerate(frames, 1):
        candidates: List[Tuple[str, float]] = []

        rotations = [0]
        if OCR_ROTATE_ALL:
            rotations = [0, 90, 180, 270]

        for deg in rotations:
            if deg != 0:
                fr = base_frame.rotate(deg, expand=True)
            else:
                fr = base_frame

            variants = _preprocess_variants_pil(fr) if OCR_USE_ENS else [fr]
            for v in variants:
                txt, score = _paddle_ocr_once(v)
                if txt:
                    candidates.append((txt, score))

        if candidates:
            # 최고 점수 선택
            txt, _ = max(candidates, key=lambda x: x[1])
            best_texts.append(f"[frame {i}] {txt}" if len(frames) > 1 else txt)

    merged = "\n\n".join([t for t in best_texts if t.strip()]).strip()
    return merged

# ── Tesseract 경로(폴백) ────────────────────────────────────
def _ocr_tesseract_frames(frames: List["Image.Image"], lang: str) -> str:  # type: ignore
    if not (_TESS_AVAILABLE and frames):
        return ""
    parts: List[str] = []
    for i, frame in enumerate(frames, 1):
        with contextlib.suppress(Exception):
            txt = pytesseract.image_to_string(frame, lang=lang)  # type: ignore
            txt = (txt or "").strip()
            txt = re.sub(r"[^\S\r\n]+", " ", txt)
            if len(txt) >= OCR_MIN_CHARS:
                parts.append(f"[frame {i}] {txt}" if len(frames) > 1 else txt)
    return "\n\n".join(parts).strip()

def ocr_image_bytes(buf: bytes, lang: str = OCR_LANG) -> str:
    if not ENABLE_OCR:
        return ""

    # 1) OpenCV 단일 쓰기 전처리(빠름) → 실패 시 GIF 포함 프레임 추출
    pil_frames: List["Image.Image"] = []  # type: ignore
    if _CV2:
        with contextlib.suppress(Exception):
            pf = _preprocess_for_ocr_cv2(buf)
            if pf:
                pil_frames = [pf]
    if not pil_frames:
        pil_frames = _extract_pil_frames(buf)
    if not pil_frames:
        return ""

    # 2) 백엔드 시도: Paddle → 실패/부족하면 Tesseract 폴백
    text = ""
    if OCR_BACKEND == "paddle" and _paddle_ocr:
        text = _ocr_paddle_frames_ensemble(pil_frames)
    if not text and _TESS_AVAILABLE:
        text = _ocr_tesseract_frames(pil_frames, lang)

    text = (text or "").strip()
    if not text:
        return ""

    # 3) 한글 후처리(띄어쓰기 결합 등)
    text = _post_process_korean(text)
    if len(text) >= OCR_MIN_CHARS:
        return text
    return ""

# ────────────────────────────────────────────────────────────
async def save_clean_outputs(
    session: aiohttp.ClientSession,
    category: str,
    url: str,
    title: str,
    slug: str,
    suffix: str,
    soup: BeautifulSoup,
):
    text, img_urls = extract_text_and_images(soup, url)
    if not text and not img_urls:
        return
    text_dir, img_dir, manifest_fp = paths_for_clean(category, slug, suffix)

    # .md 저장 (+ 헤더)
    text_fp = text_dir / f"{slug}-{suffix}.md"
    header = f"# {title}\n\n> Source: {url}\n\n"
    md_body = header + (text or "")
    ocr_summary_blocks: List[str] = []
    saved_imgs: List[str] = []
    saved_ocr_txts: List[str] = []

    # 이미지 저장 (+ OCR)
    for i, iu in enumerate(img_urls, start=1):
        b = await fetch_image_bytes(session, iu)
        if not b:
            continue
        ext = os.path.splitext(urlparse(iu).path.lower())[1] or ".jpg"
        out = img_dir / f"img{i}{ext}"
        with contextlib.suppress(Exception):
            out.write_bytes(b)
            saved_imgs.append(str(out))

        if ENABLE_OCR and ext.lower() in RASTER_EXTS:
            txt = await asyncio.to_thread(ocr_image_bytes, b, OCR_LANG)
            if txt:
                ocr_fp = out.with_suffix(out.suffix + ".txt")  # img1.jpg.txt
                with contextlib.suppress(Exception):
                    ocr_fp.write_text(txt, encoding="utf-8")
                    saved_ocr_txts.append(str(ocr_fp))
                    if OCR_ATTACH_TO_MD:
                        ocr_summary_blocks.append(f"### OCR: {out.name}\n{txt}\n")

    if OCR_ATTACH_TO_MD and ocr_summary_blocks:
        md_body += "\n\n## 이미지 OCR 추출 텍스트\n\n" + "\n\n".join(ocr_summary_blocks)

    with contextlib.suppress(Exception):
        text_fp.write_text(md_body, encoding="utf-8")

    rec: Dict[str, object] = {
        "category": category,
        "url": url,
        "title": title,
        "text_path": str(text_fp),
        "images": saved_imgs,
        "image_ocr_texts": saved_ocr_txts,
    }
    with open(manifest_fp, "a", encoding="utf-8") as mf:
        mf.write(json.dumps(rec, ensure_ascii=False) + "\n")

# ────────────────────────────────────────────────────────────
# 로컬 images 폴더 인제스트 (폴더 1개 = 문서 1개)
def _iter_local_docs_flat(root: Path) -> List[Path]:
    if not root.exists():
        return []
    return [p for p in sorted(root.iterdir()) if p.is_dir()]

def _load_local_map(root: Path) -> Dict[str, Dict]:
    """
    선택: images/_map.json 있으면 폴더별 카테고리/제목 매핑
    예)
    {
      "센터연혁": {"category": "센터소개", "title": "센터 연혁"},
      "조직도": {"category": "센터소개", "title": "조직도"}
    }
    """
    mp = root / "_map.json"
    if not mp.exists():
        return {}
    with contextlib.suppress(Exception):
        return json.loads(mp.read_text(encoding="utf-8"))
    return {}

async def ingest_local_images(root: Path, default_category: str = "센터소개"):
    """
    images/<문서폴더>/*.png|jpg|gif ... → 한 문서로 인제스트 + OCR
    - 카테고리: _map.json에 없으면 default_category 사용
    - Source: local://images/<문서폴더>
    """
    CLEAN_BASE.mkdir(parents=True, exist_ok=True)

    fmap = _load_local_map(root)
    doc_dirs = _iter_local_docs_flat(root)
    if not doc_dirs:
        return

    for doc_dir in doc_dirs:
        folder = doc_dir.name
        meta = fmap.get(folder, {})
        category = meta.get("category") or default_category
        title = meta.get("title") or folder

        slug = slugify(title)
        suffix = "local-" + hashlib.md5(str(doc_dir).encode()).hexdigest()[:8]
        text_dir, img_dir, manifest_fp = paths_for_clean(category, slug, suffix)

        # .md 본문(헤더)
        text_fp = text_dir / f"{slug}-{suffix}.md"
        source_url = f"local://images/{folder}"
        header = f"# {title}\n\n> Source: {source_url}\n\n"
        md_body = header + "(로컬 이미지 OCR 문서입니다.)\n"
        ocr_summary_blocks: List[str] = []
        saved_imgs: List[str] = []
        saved_ocr_txts: List[str] = []

        # 폴더 안의 이미지들만 (재귀 X)
        imgs = [p for p in sorted(doc_dir.iterdir()) if p.is_file() and p.suffix.lower() in IMG_EXTS]
        for i, in_fp in enumerate(imgs, start=1):
            ext = in_fp.suffix.lower()
            out_fp = img_dir / f"img{i}{ext}"
            with contextlib.suppress(Exception):
                out_fp.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(in_fp), str(out_fp))
                saved_imgs.append(str(out_fp))

            # OCR (래스터 + GIF)
            if ENABLE_OCR and ext in RASTER_EXTS:
                with contextlib.suppress(Exception):
                    b = in_fp.read_bytes()
                if b:
                    txt = await asyncio.to_thread(ocr_image_bytes, b, OCR_LANG)
                    if txt:
                        ocr_fp = out_fp.with_suffix(out_fp.suffix + ".txt")
                        with contextlib.suppress(Exception):
                            ocr_fp.write_text(txt, encoding="utf-8")
                            saved_ocr_txts.append(str(ocr_fp))
                            if OCR_ATTACH_TO_MD:
                                ocr_summary_blocks.append(f"### OCR: {out_fp.name}\n{txt}\n")

        if OCR_ATTACH_TO_MD and ocr_summary_blocks:
            md_body += "\n\n## 이미지 OCR 추출 텍스트\n\n" + "\n\n".join(ocr_summary_blocks)

        with contextlib.suppress(Exception):
            text_fp.write_text(md_body, encoding="utf-8")

        rec: Dict[str, object] = {
            "category": category,
            "url": source_url,
            "title": title,
            "text_path": str(text_fp),
            "images": saved_imgs,
            "image_ocr_texts": saved_ocr_txts,
        }
        with open(manifest_fp, "a", encoding="utf-8") as mf:
            mf.write(json.dumps(rec, ensure_ascii=False) + "\n")

# ────────────────────────────────────────────────────────────
async def crawl_internal_clean(category: str, seeds: List[str]):
    CLEAN_BASE.mkdir(parents=True, exist_ok=True)
    (CLEAN_BASE / category).mkdir(parents=True, exist_ok=True)

    seen = set()
    q = deque(normalize_url(s) for s in seeds)
    sem = asyncio.Semaphore(CONCURRENCY)

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async def handle(u: str):
            nu = normalize_url(u)
            if nu in seen:
                return
            seen.add(nu)

            async with sem:
                status, html = await fetch_html(session, nu)
            if status != 200 or not html:
                return

            soup = BeautifulSoup(html, "html.parser")
            title = soup.title.get_text(strip=True) if soup.title else "제목없음"
            slug = slugify(title)
            pid = page_id_from_path(urlparse(nu).path)
            suffix = pid or hashlib.md5(nu.encode()).hexdigest()[:8]

            await save_clean_outputs(session, category, nu, title, slug, suffix, soup)

            # 내부 링크 큐잉
            for a in soup.select("a[href]"):
                href = (a.get("href") or "").split("#")[0].strip()
                if not href: continue
                nxt = urljoin(nu, href)
                if urlparse(nxt).netloc.endswith("cheonanurc.or.kr"):
                    q.append(normalize_url(nxt))

        tasks = []
        while q:
            tasks.append(asyncio.create_task(handle(q.popleft())))
            if len(tasks) >= BATCH_GATHER:
                await asyncio.gather(*tasks); tasks.clear()
        if tasks:
            await asyncio.gather(*tasks)

async def save_external_once_clean(category: str, seeds: List[str]):
    CLEAN_BASE.mkdir(parents=True, exist_ok=True)
    (CLEAN_BASE / category).mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        for u in seeds:
            status, html = await fetch_html(session, u)
            if status != 200 or not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            title = soup.title.get_text(strip=True) if soup.title else urlparse(u).netloc
            slug = slugify(title)
            suf = hashlib.md5(u.encode()).hexdigest()[:8]
            await save_clean_outputs(session, category, u, title, slug, suf, soup)

# ────────────────────────────────────────────────────────────
async def ingest_all_locals():
    for root in LOCAL_IMAGE_ROOTS:
        print(f"[LOCAL-INGEST] {root}")
        await ingest_local_images(root, default_category=os.getenv("LOCAL_IMAGE_DEFAULT_CATEGORY", "센터소개"))

async def main():
    CLEAN_BASE.mkdir(parents=True, exist_ok=True)

    # 1) 외부(1-hop)
    external_cats = ["instagram", "blog", "youtube", "band"]
    for cat in external_cats:
        await save_external_once_clean(cat, SEEDS[cat])

    # 2) 내부(BFS)
    internal_cats = [k for k in SEEDS.keys() if k not in external_cats]
    for cat in internal_cats:
        await crawl_internal_clean(cat, SEEDS[cat])

    # 3) 로컬 이미지 인제스트
    await ingest_all_locals()

if __name__ == "__main__":
    asyncio.run(main())
