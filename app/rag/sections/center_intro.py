from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Tuple

# 크롤링 산출물 경로 (config.CLEAN_DIR에서 주입될 수 있음)
DEFAULT_CLEAN_DIR = Path("app/data/clean")

SECTION_ANCHORS = {
    "인사말": ["인사말", "인사", "환영"],
    "연혁": ["연혁", "발자취", "히스토리", "history"],
    "조직도": ["조직도", "조직", "팀구성"],
    "목표비전": ["목표", "비전", "목표와비전", "비전과목표"],
}

# OCR이 없거나 부족한 경우 대비한 안전한 Fallback
FALLBACK_TEXT: Dict[str, List[str]] = {
    "인사말": [
        "천안시 도시재생지원센터 홈페이지를 방문해 주셔서 감사합니다. "
        "저희 센터는 주민과 행정의 가교로서 지역 맞춤형 도시재생을 지원합니다.",
    ],
    "연혁": [
        "2015년 개소 이후 도시재생 뉴딜·혁신지구, 현장지원센터 운영 등 다양한 사업을 추진해 왔습니다.",
    ],
    "조직도": [
        "센터장, 사무국, 기초사업팀, 현장운영1·2팀으로 구성되어 있으며, "
        "천안역세권·봉명·오룡지구 현장지원센터를 운영합니다.",
    ],
    "목표비전": [
        "주민 주도의 지속가능한 도시재생을 목표로 지역 공동체 회복과 생활권 활성화를 지향합니다.",
    ],
}


def _read_all_md(clean_dir: Path) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    if not clean_dir.exists():
        return out
    for md in clean_dir.glob("**/*.md"):
        try:
            txt = md.read_text(encoding="utf-8", errors="ignore")
            out.append((str(md), txt))
        except Exception:
            continue
    return out


def build_center_intro_index(clean_dir: Path = DEFAULT_CLEAN_DIR) -> Dict[str, List[str]]:
    """
    크롤링된 마크다운에서 섹션별 블록을 대략적으로 모아 둡니다.
    """
    buckets: Dict[str, List[str]] = {k: [] for k in SECTION_ANCHORS.keys()}
    for _, txt in _read_all_md(clean_dir):
        for sec_key, anchors in SECTION_ANCHORS.items():
            for a in anchors:
                # 간단한 헤더/문장 매칭
                if re.search(rf"(#\s*{a}\b|{a}\s*[:：])", txt, flags=re.IGNORECASE):
                    # 해당 줄부터 20줄 정도 떼오기
                    lines = txt.splitlines()
                    for i, line in enumerate(lines):
                        if re.search(rf"(#\s*{a}\b|{a}\s*[:：])", line, flags=re.IGNORECASE):
                            snippet = "\n".join(lines[i : i + 20]).strip()
                            if snippet and snippet not in buckets[sec_key]:
                                buckets[sec_key].append(snippet)
    # Fallback 보강
    for k, v in FALLBACK_TEXT.items():
        if not buckets.get(k):
            buckets[k] = list(v)
    return buckets


def query_section(index: Dict[str, List[str]], key: str) -> List[str]:
    return index.get(key, [])[:2]


def query_contact(index: Dict[str, List[str]]) -> List[str]:
    # 간단 요약 (하드코딩 안전값)
    return [
        "- 주소: 충남 천안시 동남구 은행길 15, 두드림센터 5층",
        "- Tel: 041-417-4061~5 / Fax: 041-417-4069",
        "- 오시는 길: 센터·봉명·오룡 각 센터 지도 이미지를 요청하시면 이미지로 안내해 드립니다.",
    ]