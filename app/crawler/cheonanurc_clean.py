# app/crawler/cheonanurc_clean.py
# -*- coding: utf-8 -*-
import os
import re
import json
import asyncio
import hashlib
from pathlib import Path
from typing import Optional, Tuple, List
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse

import aiohttp
from bs4 import BeautifulSoup

# ────────────────────────────────────────────────────────────
# 이 파일 내부에서 관리할 SEEDS (원본 크롤러와 별개)
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
    "센터소개": [
        "https://www.cheonanurc.or.kr/24",
        "https://www.cheonanurc.or.kr/79",
        "https://www.cheonanurc.or.kr/101",
        "https://www.cheonanurc.or.kr/25",
        "https://www.cheonanurc.or.kr/131",
        "https://www.cheonanurc.or.kr/133",
        "https://www.cheonanurc.or.kr/128",
    ],
    "사업소개": [
        "https://www.cheonanurc.or.kr/68",
        "https://www.cheonanurc.or.kr/27",
        "https://www.cheonanurc.or.kr/71",
        "https://www.cheonanurc.or.kr/70",
        "https://www.cheonanurc.or.kr/72",
        "https://www.cheonanurc.or.kr/74",
        "https://www.cheonanurc.or.kr/75",
        "https://www.cheonanurc.or.kr/73",
        "https://www.cheonanurc.or.kr/140",
    ],
    "커뮤니티": [
        "https://www.cheonanurc.or.kr/92",
        "https://www.cheonanurc.or.kr/95",
        "https://www.cheonanurc.or.kr/121",
    ],
    "도시재생+": [
        "https://www.cheonanurc.or.kr/new",
        "https://www.cheonanurc.or.kr/41",
        "https://www.cheonanurc.or.kr/64",
        "https://www.cheonanurc.or.kr/78",
        "https://www.cheonanurc.or.kr/97",
        "https://www.cheonanurc.or.kr/98",
        "https://www.cheonanurc.or.kr/99",
        "https://www.cheonanurc.or.kr/100",
    ],
    "아카이브": [
        "https://www.cheonanurc.or.kr/36",
        "https://www.cheonanurc.or.kr/35",
        "https://www.cheonanurc.or.kr/37",
        "https://www.cheonanurc.or.kr/108",
    ],
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CheonanURC-CleanBot/1.0)"}
CONCURRENCY = 6
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
BATCH_GATHER = 64

CLEAN_BASE = Path(__file__).resolve().parent.parent / "data" / "clean"

# 저장할 이미지 확장자 (범위 확장)
IMG_EXTS = (
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg",
    ".bmp", ".tif", ".tiff", ".avif", ".jp2"
)

# ────────────────────────────────────────────────────────────
def normalize_url(u: str) -> str:
    pu = urlparse(u)
    clean_query = "&".join(
        p for p in pu.query.split("&") if p and not p.lower().startswith(("utm_", "fbclid"))
    )
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
    """메뉴/푸터/유틸 잡영역 제거 + 노이즈 텍스트 블록 제거"""
    selectors = [
        "nav", "header", "footer", "aside", "form", "iframe", "noscript",
        ".gnb", ".lnb", ".breadcrumb", ".breadcrumbs", ".pagination",
        ".pager", ".skip", ".sr-only", ".sr_only",
        ".sns", ".share", ".social", ".banner", ".ad", ".advert", ".visual",
        ".btn", ".btn-group", ".btns", ".actions", ".toolbar",
        "#gnb", "#lnb", "#footer", "#header", "#nav", "#quick"
    ]
    for sel in selectors:
        for t in soup.select(sel):
            t.decompose()

    noise_keywords = [
        "뒤로", "더보기", "접기", "열기", "로그인", "로그아웃", "마이페이지",
        "Alarm", "공지사항", "바로가기", "TOP", "맨위로", "검색",
        "내 글 반응", "게시물 알림"
    ]
    for a in list(soup.find_all(["a", "button", "span", "div"])):
        txt = (a.get_text(" ", strip=True) or "")[:20]
        if any(k in txt for k in noise_keywords):
            a.decompose()

def pick_main_node(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    """가중치 기반 본문 후보 선택"""
    strip_chrome(soup)
    candidates: List[Tuple[float, int, BeautifulSoup]] = []

    priors = [
        "article", "#content", ".content", "#main",
        ".entry-content", ".post", ".board_view", ".sub_content", ".view"
    ]
    for sel in priors:
        for node in soup.select(sel):
            text = node.get_text(" ", strip=True)
            if len(text) >= 100:
                candidates.append((len(text), 3, node))

    if not candidates:
        for node in soup.find_all(["section", "div"]):
            raw = node.get_text(" ", strip=True)
            if len(raw) < 200:
                continue
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
    """<table> → Markdown"""
    headers = []
    thead = tbl.find("thead")
    if thead:
        ths = thead.find_all(["th", "td"])
        headers = [th.get_text(" ", strip=True) for th in ths if th.get_text(strip=True)]
    rows = []
    tbody = tbl.find("tbody") or tbl
    for tr in tbody.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
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
    """본문 노드를 마크다운 텍스트로 변환"""
    for tag in node.find_all(["br"]):
        tag.replace_with("\n")
    for tag in node.find_all(["p", "li", "blockquote"]):
        if tag.text and not tag.text.endswith("\n"):
            tag.append("\n")
    for tag in node.find_all(["h1","h2","h3","h4","h5","h6"]):
        level = int(tag.name[1])
        prefix = "#" * min(level, 6)
        content = tag.get_text(" ", strip=True)
        tag.clear()
        tag.append(f"{prefix} {content}\n")
    for tbl in node.find_all("table"):
        md_tbl = html_table_to_md(tbl)
        tbl.replace_with(BeautifulSoup("\n"+md_tbl+"\n", "html.parser"))
    for junk in node.select("script, style"):
        junk.decompose()

    text = node.get_text("\n", strip=True)
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    cleaned = []
    for ln in lines:
        if ln.startswith("| ") or ln.startswith("#"):
            cleaned.append(ln); continue
        if len(ln) < 2:
            continue
        cleaned.append(ln)
    dedup = []
    for ln in cleaned:
        if not dedup or dedup[-1] != ln:
            dedup.append(ln)
    return "\n".join(dedup).strip()

# ────────────────────────────────────────────────────────────
def extract_text_and_images(soup: BeautifulSoup, base_url: str) -> Tuple[str, List[str]]:
    main = pick_main_node(soup)
    if not main:
        return "", []

    md_text = html_to_markdown(main)

    urls = set()
    og = soup.select_one('meta[property="og:image"]')
    if og and og.get("content"):
        urls.add(urljoin(base_url, og["content"].strip()))
    for img in main.select("img[src]"):
        src = (img.get("src") or "").strip()
        if not src:
            continue
        absu = urljoin(base_url, src)
        ext = os.path.splitext(urlparse(absu).path.lower())[1]
        # 확장자 체크(넓은 범위) — 필요 없으면 이 if도 제거 가능
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

    # .md로 저장 + 문서 헤더(제목/원본 URL)
    text_fp = text_dir / f"{slug}-{suffix}.md"
    header = f"# {title}\n\n> Source: {url}\n\n"
    text_fp.write_text(header + (text or ""), encoding="utf-8")

    saved_imgs = []
    for i, iu in enumerate(img_urls, start=1):
        b = await fetch_image_bytes(session, iu)
        if not b:   # 크기/해상도 제한 없이 모두 저장
            continue
        ext = os.path.splitext(urlparse(iu).path.lower())[1] or ".jpg"
        out = img_dir / f"img{i}{ext}"
        out.write_bytes(b)
        saved_imgs.append(str(out))

    rec = {"category": category, "url": url, "title": title,
           "text_path": str(text_fp), "images": saved_imgs}
    with open(manifest_fp, "a", encoding="utf-8") as mf:
        mf.write(json.dumps(rec, ensure_ascii=False) + "\n")

# ────────────────────────────────────────────────────────────
CONCURRENCY = 6
BATCH_GATHER = 64

async def crawl_internal_clean(category: str, seeds: List[str]):
    """내부 도메인만 BFS 확장하여 텍스트/이미지를 'clean' 폴더에 저장."""
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

            # 저장
            await save_clean_outputs(session, category, nu, title, slug, suffix, soup)

            # 내부 링크 큐잉
            for a in soup.select("a[href]"):
                href = (a.get("href") or "").split("#")[0].strip()
                if not href:
                    continue
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
    """외부 도메인은 1-hop 저장만(확장 X)."""
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
async def main():
    CLEAN_BASE.mkdir(parents=True, exist_ok=True)
    external_cats = ["instagram", "blog", "youtube", "band"]
    internal_cats = [k for k in SEEDS.keys() if k not in external_cats]

    for cat in external_cats:
        await save_external_once_clean(cat, SEEDS[cat])
    for cat in internal_cats:
        await crawl_internal_clean(cat, SEEDS[cat])

if __name__ == "__main__":
    asyncio.run(main())
