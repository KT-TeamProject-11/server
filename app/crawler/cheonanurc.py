# app/crawler/cheonanurc.py
# -*- coding: utf-8 -*-
import re
import csv
import asyncio
import hashlib
from pathlib import Path
from collections import deque
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import aiohttp
from bs4 import BeautifulSoup

# ────────────────────────────────────────────────────────────
BASE = "https://www.cheonanurc.or.kr"
RAW_BASE = Path(__file__).resolve().parent.parent / "data" / "raw"

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

    # 내부 카테고리 (요청한 이름 그대로)
    "센터소개": [
        "https://www.cheonanurc.or.kr/24",   # 인사말
        "https://www.cheonanurc.or.kr/79",   # 목표와 비전
        "https://www.cheonanurc.or.kr/101",  # 센터 연혁
        "https://www.cheonanurc.or.kr/25",   # 조직 및 담당
        "https://www.cheonanurc.or.kr/131",  # 오시는 길(본센터)
        "https://www.cheonanurc.or.kr/133",  # 봉명지구
        "https://www.cheonanurc.or.kr/128",  # 오룡지구
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
        "https://www.cheonanurc.or.kr/new",  # 공지
        "https://www.cheonanurc.or.kr/41",   # 센터 프로그램 신청
        "https://www.cheonanurc.or.kr/64",   # 도시재생투어(상위)
        "https://www.cheonanurc.or.kr/78",   # 일반코스1
        "https://www.cheonanurc.or.kr/97",   # 일반코스2
        "https://www.cheonanurc.or.kr/98",   # 전문코스1
        "https://www.cheonanurc.or.kr/99",   # 전문코스2
        "https://www.cheonanurc.or.kr/100",  # 전문코스3
    ],
    "아카이브": [
        "https://www.cheonanurc.or.kr/36",   # 발간물
        # 잘못된 URL 제거: https://www.cheonanurc.or.kr/httpswww...
        "https://www.cheonanurc.or.kr/35",   # 도시재생뉴스(외부 기사 링크)
        "https://www.cheonanurc.or.kr/37",   # 전문가 오피니언
        "https://www.cheonanurc.or.kr/108",  # 마을기자단 및 인터뷰
    ],
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CheonanURCBot/1.0)"}
CONCURRENCY = 6
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
BATCH_GATHER = 64  # 한 번에 모아서 gather할 태스크 수

# ────────────────────────────────────────────────────────────
def normalize_url(u: str) -> str:
    """쿼리의 추적 파라미터 제거, fragment 제거, 말미 슬래시 정리."""
    pu = urlparse(u)
    clean_query = "&".join(
        p for p in pu.query.split("&")
        if p and not p.lower().startswith(("utm_", "fbclid"))
    )
    return urlunparse((pu.scheme, pu.netloc, pu.path.rstrip("/"), pu.params, clean_query, ""))

def slugify(title: str) -> str:
    """제목 → 파일 시스템 안전한 슬러그(한글/영문/숫자 유지)."""
    title = re.sub(r"\s+", " ", title or "").strip()
    s = re.sub(r"[^0-9A-Za-z가-힣]+", "-", title).strip("-")
    return s[:80] if s else "page"

def page_id_from_path(path: str) -> Optional[str]:
    m = re.search(r"/(\d+)$", path or "")
    return m.group(1) if m else None

async def fetch(session: aiohttp.ClientSession, url: str) -> Tuple[int, str]:
    """간단 리트라이 포함 GET."""
    for attempt in range(3):
        try:
            async with session.get(url, timeout=REQUEST_TIMEOUT) as r:
                text = await r.text(errors="ignore")
                return r.status, text
        except Exception:
            await asyncio.sleep(0.8 * (attempt + 1))
    return 0, ""

# ────────────────────────────────────────────────────────────
async def crawl_internal(category: str, seeds: list):
    """내부 도메인만 BFS. 외부 링크는 큐잉하지 않음."""
    out_dir = RAW_BASE / category
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_fp = out_dir / "manifest.csv"
    wrote_header = not manifest_fp.exists()

    seen: set = set()
    q = deque(normalize_url(s) for s in seeds)
    sem = asyncio.Semaphore(CONCURRENCY)

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # 동기 파일 컨텍스트는 별도로 열기 (3.9 호환)
        with open(manifest_fp, "a", newline="", encoding="utf-8") as mf:
            wr = csv.writer(mf)
            if wrote_header:
                wr.writerow(["category", "url", "saved_path", "title", "status", "content_md5"])

            async def handle(u: str):
                nu = normalize_url(u)
                if nu in seen:
                    return
                seen.add(nu)

                async with sem:
                    status, html = await fetch(session, nu)

                if status != 200 or not html:
                    wr.writerow([category, nu, "", "", status, ""])
                    return

                soup = BeautifulSoup(html, "html.parser")
                title = soup.title.get_text(strip=True) if soup.title else "제목없음"

                # 파일명: <slug>-<id or md5_8>.html
                slug = slugify(title)
                pid = page_id_from_path(urlparse(nu).path)
                suffix = pid or hashlib.md5(nu.encode()).hexdigest()[:8]
                fname = f"{slug}-{suffix}.html"
                fpath = out_dir / fname

                # 중복 콘텐츠 방지(본문 텍스트 해시)
                text_md5 = hashlib.md5(
                    soup.get_text(" ", strip=True).encode("utf-8")
                ).hexdigest()

                if fpath.exists():
                    old = fpath.read_text(encoding="utf-8", errors="ignore")
                    old_md5 = hashlib.md5(
                        BeautifulSoup(old, "html.parser").get_text(" ", strip=True).encode("utf-8")
                    ).hexdigest()
                    if old_md5 == text_md5:
                        wr.writerow([category, nu, str(fpath), title, status, text_md5])
                        return

                fpath.write_text(html, encoding="utf-8")
                wr.writerow([category, nu, str(fpath), title, status, text_md5])

                # 내부 링크만 큐잉
                for a in soup.select("a[href]"):
                    href = (a.get("href") or "").split("#")[0].strip()
                    if not href:
                        continue
                    nxt = urljoin(nu, href)
                    if urlparse(nxt).netloc.endswith("cheonanurc.or.kr"):
                        q.append(normalize_url(nxt))

            # 작업 실행 (배치로 gather)
            tasks = []
            while q:
                tasks.append(asyncio.create_task(handle(q.popleft())))
                if len(tasks) >= BATCH_GATHER:
                    await asyncio.gather(*tasks)
                    tasks.clear()
            if tasks:
                await asyncio.gather(*tasks)

# ────────────────────────────────────────────────────────────
async def save_external_once(category: str, seeds: list):
    """외부 도메인은 1-hop으로 저장만 수행(확장 금지)."""
    out_dir = RAW_BASE / category
    out_dir.mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        for u in seeds:
            status, html = await fetch(session, u)
            if status != 200 or not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            title = soup.title.get_text(strip=True) if soup.title else urlparse(u).netloc
            slug = slugify(title)
            suf = hashlib.md5(u.encode()).hexdigest()[:8]
            (out_dir / f"{slug}-{suf}.html").write_text(html, encoding="utf-8")

# ────────────────────────────────────────────────────────────
async def main():
    RAW_BASE.mkdir(parents=True, exist_ok=True)

    # 외부: instagram/blog/youtube/band → 1-hop 저장
    external_cats = ["instagram", "blog", "youtube", "band"]
    internal_cats = [k for k in SEEDS.keys() if k not in external_cats]

    for cat in external_cats:
        await save_external_once(cat, SEEDS[cat])

    for cat in internal_cats:
        await crawl_internal(cat, SEEDS[cat])

if __name__ == "__main__":
    asyncio.run(main())
