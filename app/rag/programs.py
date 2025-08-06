from typing import Optional
# 모든 프로그램 정보를 담는 _PROGRAMS 딕셔너리
_PROGRAMS = {
    # "도시재생지원센터 센터소개"가 정식 명칭 (Key)

    # 상위 분류
    "도시재생지원센터 센터소개": {
        "url": "https://www.cheonanurc.or.kr/24",
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
    "도시재생지원센터 도시재생+": {
        "url": "https://www.cheonanurc.or.kr/new",
        "aliases": ["도시재생", "도시재생지원센터 도시재생", "재생"]
    },
    "도시재생지원센터 아카이브": {
        "url": "https://www.cheonanurc.or.kr/36",
        "aliases": ["아카이브", "센터 아카이브", "도시재생지원센터 아카이브"]
    },

    # 센터 소개 부분 

    "도시재생지원센터 센터소개 인사말": {
        "url": "https://www.cheonanurc.or.kr/24",
        "aliases": ["인사말", "인사", "센터소개 인사말"] # 별칭 목록
    },

    "도시재생지원센터 센터소개 목표와 비전": {
        "url": "https://www.cheonanurc.or.kr/79",
        "aliases": ["목표와 비전", "센터소개 목표와 비전", "목표", "비전"] # 별칭 목록
    },

    "도시재생지원센터 센터소개 센터 연혁": {
        "url": "https://www.cheonanurc.or.kr/101",
        "aliases": ["센터 연혁", "센터소개 센터 연혁", "연혁"] # 별칭 목록
    },

    "도시재생지원센터 센터소개 조직 및 담당": {
        "url": "https://www.cheonanurc.or.kr/25",
        "aliases": ["조직 및 담당", "센터소개 조직 및 담당", "조직", "담당"] # 별칭 목록
    },

    "도시재생지원센터 센터소개 오시는 길": {
        "url": "https://www.cheonanurc.or.kr/131",
        "aliases": ["오는 길", "오시는 길", "방향"] # 별칭 목록
    },

    # 오시는길 - 하위목록

    "도시재생지원센터 천안시 도시재생지원센터 오시는 길": {
        "url": "https://www.cheonanurc.or.kr/131",
        "aliases": ["천안시 도시재생지원센터 오시는 길", "도시재생지원센터 오시는 길", "센터 오는 길", "센터 위치"]
    },
    "도시재생지원센터 봉명지구 도시재생현장지원센터 오시는 길": {
        "url": "https://www.cheonanurc.or.kr/133",
        "aliases": ["봉명지구 도시재생현장지원센터 오시는 길", "봉명지구 현장지원센터 오는 길", "봉명지구 위치"]
    },
    "도시재생지원센터 오룡지구 도시재생현장지원센터 오시는 길": {
        "url": "https://www.cheonanurc.or.kr/128",
        "aliases": ["오룡지구 도시재생현장지원센터 오시는 길", "오룡지구 현장지원센터 오는 길", "오룡지구 위치"]
    },

    # 사업 소개 부분
    
    "도시재생지원센터 천안 도시재생 총괄사업현황": {
        "url": "https://www.cheonanurc.or.kr/68",
        "aliases": ["천안 도시재생 총괄사업현황", "총괄사업현황", "총괄사업"]
    },

    "도시재생지원센터 천안 도시재생선도사업": {
        "url": "https://www.cheonanurc.or.kr/27",
        "aliases": ["천안 도시재생선도사업", "도시재생선도사업", "선도사업"]
    },

    "도시재생지원센터 천안역세권 도시재생사업": {
        "url": "https://www.cheonanurc.or.kr/71",
        "aliases": ["천안역세권 도시재생사업", "역세권 도시재생", "천안역세권"]
    },

    "도시재생지원센터 남산지구 도시재생사업": {
        "url": "https://www.cheonanurc.or.kr/70",
        "aliases": ["남산지구 도시재생사업", "남산지구"]
    },

    "도시재생지원센터 봉명지구 도시재생사업": {
        "url": "https://www.cheonanurc.or.kr/72",
        "aliases": ["봉명지구 도시재생사업", "봉명지구"]
    },

    "도시재생지원센터 오룡지구 도시재생사업": {
        "url": "https://www.cheonanurc.or.kr/74",
        "aliases": ["오룡지구 도시재생사업", "오룡지구"]
    },

    "도시재생지원센터 천안역세권 혁신지구 도시재생사업": {
        "url": "https://www.cheonanurc.or.kr/75",
        "aliases": ["천안역세권 혁신지구 도시재생사업", "역세권 혁신지구", "혁신지구"]
    },

    "도시재생지원센터 오룡지구 민·관 협력형 도시재생 리츠사업": {
        "url": "https://www.cheonanurc.or.kr/73",
        "aliases": ["오룡지구 민관협력형 도시재생 리츠사업", "오룡지구 리츠사업", "리츠사업"]
    },

    "도시재생지원센터 원성2지구 뉴:빌리지사업": {
        "url": "https://www.cheonanurc.or.kr/140",
        "aliases": ["원성2지구 뉴빌리지사업", "뉴빌리지사업", "원성2지구"]
    },

    # 커뮤니티 부분

    "도시재생지원센터 천안시 도시재생지원센터 커뮤니티": {
        "url": "https://www.cheonanurc.or.kr/92",
        "aliases": ["천안시 도시재생지원센터 커뮤니티", "도시재생지원센터 커뮤니티", "천안시 커뮤니티"]
    },
    "도시재생지원센터 봉명지구 도시재생현장지원센터": {
        "url": "https://www.cheonanurc.or.kr/95",
        "aliases": ["봉명지구 도시재생현장지원센터", "봉명지구 현장지원센터", "봉명지구 커뮤니티"]
    },
    "도시재생지원센터 오룡지구 도시재생현장지원센터": {
        "url": "https://www.cheonanurc.or.kr/121",
        "aliases": ["오룡지구 도시재생현장지원센터", "오룡지구 현장지원센터", "오룡지구 커뮤니티"]
    },

    # 도시재생+ 부분

    "도시재생지원센터 공지사항": {
        "url": "https://www.cheonanurc.or.kr/new",
        "aliases": ["공지사항", "공지", "센터 공지"]
    },
    "도시재생지원센터 센터 프로그램 신청": {
        "url": "https://www.cheonanurc.or.kr/41",
        "aliases": ["센터 프로그램 신청", "프로그램 신청", "센터 프로그램"]
    },
    "도시재생지원센터 도시재생 투어": {
        "url": "https://www.cheonanurc.or.kr/64",
        "aliases": ["도시재생 투어", "투어 신청", "센터 투어"]
    },

    # 도시재생 투어 - 코스 부분

    "도시재생 투어 일반코스 1": {
        "url": "https://www.cheonanurc.or.kr/78",
        "aliases": ["일반코스 1", "도시재생 투어 일반코스 1", "투어 일반코스 1"]
    },
    "도시재생 투어 일반코스 2": {
        "url": "https://www.cheonanurc.or.kr/97",
        "aliases": ["일반코스 2", "도시재생 투어 일반코스 2", "투어 일반코스 2"]
    },
    "도시재생 투어 전문코스 1": {
        "url": "https://www.cheonanurc.or.kr/98",
        "aliases": ["전문코스 1", "도시재생 투어 전문코스 1", "투어 전문코스 1"]
    },
    "도시재생 투어 전문코스 2": {
        "url": "https://www.cheonanurc.or.kr/99",
        "aliases": ["전문코스 2", "도시재생 투어 전문코스 2", "투어 전문코스 2"]
    },
    "도시재생 투어 전문코스 3": {
        "url": "https://www.cheonanurc.or.kr/100",
        "aliases": ["전문코스 3", "도시재생 투어 전문코스 3", "투어 전문코스 3"]
    },

    # 아카이브 부분

    "도시재생지원센터 발간물": {
        "url": "https://www.cheonanurc.or.kr/36",
        "aliases": ["발간물", "센터 발간물", "자료집"]
    },
    "도시재생지원센터 홍보 동영상": {
        "url": "https://www.cheonanurc.or.kr/httpswwwyoutubecomwatchvghzmqbIRJo0",
        "aliases": ["홍보 동영상", "홍보 영상", "동영상 자료"]
    },
    "도시재생지원센터 도시재생 뉴스": {
        "url": "https://www.cheonanurc.or.kr/35",
        "aliases": ["도시재생 뉴스", "뉴스", "센터 뉴스"]
    },
    "도시재생지원센터 전문가 오피니언": {
        "url": "https://www.cheonanurc.or.kr/37",
        "aliases": ["전문가 오피니언", "오피니언", "전문가 칼럼"]
    },
    "도시재생지원센터 마을기자단 및 인터뷰": {
        "url": "https://www.cheonanurc.or.kr/108",
        "aliases": ["마을기자단 및 인터뷰", "마을기자단", "인터뷰"]
    }



}

def get_all_aliases() -> list[str]:
    """모든 프로그램의 별칭(alias)들을 하나의 리스트로 반환합니다."""
    all_aliases = []
    for details in _PROGRAMS.values():
        all_aliases.extend(details["aliases"
        ])
    return all_aliases

def get_program_by_alias(alias: str) -> Optional[dict]:
    """특정 별칭이 속한 프로그램의 전체 정보(URL 포함)를 반환합니다."""
    for details in _PROGRAMS.values():
        if alias in details["aliases"]:
            return details
    return None