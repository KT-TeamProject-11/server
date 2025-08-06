import re
import asyncio
import hashlib
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

BASE_URL = "https://www.cheonanurc.or.kr"
RAW_BASE = Path(__file__).resolve().parent.parent / "data" / "raw"

# 카테고리별 Seed URL 목록
SEED_CATEGORIES = {
    "main": [
        "https://www.cheonanurc.or.kr/"
    ],
    "instagram": [
        "https://www.instagram.com/cheonan_urc/?hl=ko",
        "https://www.instagram.com/cheonan.want/?hl=ko",
        "https://www.instagram.com/cheonan_base/"
    ],
    "blog": [
        "https://blog.naver.com/urc-cheonan",
        "https://blog.naver.com/tongdol2020"
    ],
    "youtube": [
        "https://www.youtube.com/channel/UCnmu-XM_ssRWVnwmCUVmFGg"
    ],
    "band": [
        "https://www.band.us/band/86255676"
    ],
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
        "https://www.cheonanurc.or.kr/httpswwwyoutubecomwatchvghzmqbIRJo0",
        "https://www.cheonanurc.or.kr/35",
        "https://www.cheonanurc.or.kr/37",
        "https://www.cheonanurc.or.kr/108",
    ],
}


async def fetch_and_save(session: aiohttp.ClientSession, url: str, out_dir: Path):
    """URL에서 HTML을 가져와 해시된 파일명으로 저장."""
    try:
        async with session.get(url, timeout=30) as resp:
            resp.raise_for_status()
            html = await resp.text()
    except Exception as e:
        print(f"[ERROR] {url} -> {e}")
        return

    # 파일명: md5(url).html
    fname = hashlib.md5(url.encode("utf-8")).hexdigest() + ".html"
    (out_dir / fname).write_text(html, encoding="utf-8")
    print(f"[SAVED] {url} -> {out_dir / fname}")

    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href]"):
        href = a["href"].split("#")[0]
        if not href:
            continue
        if href.startswith("http"):
            nxt = href
        elif href.startswith("/"):
            nxt = BASE_URL + href
        else:
            continue
        if urlparse(nxt).netloc.endswith("cheonanurc.or.kr") and nxt not in seen:
            queue.append(nxt)


async def crawl_category(category: str, seeds: list[str]):
    """하나의 카테고리에 대해 큐 기반 BFS 크롤링."""
    out_dir = RAW_BASE / category
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== Crawling category: {category} ===")
    global seen, queue
    seen, queue = set(), list(seeds)

    async with aiohttp.ClientSession() as session:
        while queue:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            await fetch_and_save(session, url, out_dir)


async def main():
    RAW_BASE.mkdir(parents=True, exist_ok=True)
    for category, seeds in SEED_CATEGORIES.items():
        await crawl_category(category, seeds)


if __name__ == "__main__":
    asyncio.run(main())
