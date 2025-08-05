# 모든 프로그램 정보를 담는 _PROGRAMS 딕셔너리
_PROGRAMS = {
    # "도시재생지원센터 센터소개"가 정식 명칭 (Key)
    "도시재생지원센터 센터소개": {
        "url": "https://www.cheonanurc.or.kr/67",
        "aliases": ["센터소개", "소개", "도시재생지원센터 센터소개"] # 별칭 목록
    },
    "도시재생지원센터 사업소개": {
        "url": "https://www.cheonanurc.or.kr/68",
        "aliases": ["사업소개", "프로젝트", "도시재생지원센터 사업소개"]
    },
    "도시재생지원센터 커뮤니티": {
        "url": "https://www.cheonanurc.or.kr/92",
        "aliases": ["커뮤니티", "센터 커뮤니티", "도시재생지원센터 커뮤니티"]
    },
    "도시재생지원센터 센터 프로그램 신청": {
        "url": "https://www.cheonanurc.or.kr/41",
        "aliases": ["센터 프로그램 신청", "도시재생지원센터 프로그램 신청", "프로그램 신청"]
    },
    "도시재생지원센터 도시재생 투어": {
        "url": "https://www.cheonanurc.or.kr/64",
        "aliases": ["도시재생 투어", "센터 도시재생 투어", "도시재생지원센터 도시재생 투어"]
    },
}

def get_all_aliases() -> list[str]:
    """모든 프로그램의 별칭(alias)들을 하나의 리스트로 반환합니다."""
    all_aliases = []
    for details in _PROGRAMS.values():
        all_aliases.extend(details["aliases"])
    return all_aliases

def get_program_by_alias(alias: str) -> dict | None:
    """특정 별칭이 속한 프로그램의 전체 정보(URL 포함)를 반환합니다."""
    for details in _PROGRAMS.values():
        if alias in details["aliases"]:
            return details
    return None