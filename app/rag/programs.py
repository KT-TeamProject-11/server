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
        "aliases": ["커뮤니티", "센터커뮤니티", "도시재생지원센터 커뮤니티"]
    },
    "도시재생지원센터 도시재생+": {
        "url": "https://www.cheonanurc.or.kr/new",
        "aliases": ["도시재생플러스"]
    },
    "도시재생지원센터 아카이브": {
        "url": "https://www.cheonanurc.or.kr/36",
        "aliases": ["아카이브", "센터아카이브", "도시재생지원센터 아카이브"]
    },

    # 센터 소개 부분 

    "도시재생지원센터 센터소개 인사말": {
        "url": "https://www.cheonanurc.or.kr/24",
        "aliases": ["인사말", "인사", "센터소개 인사말"],
        "tags": ["센터소개"] # <-- 태그 추가
    },
    "도시재생지원센터 센터소개 목표와 비전": {
        "url": "https://www.cheonanurc.or.kr/79",
        "aliases": ["목표와비전", "센터소개목표와비전", "목표", "비전"],
        "tags": ["센터소개"] # <-- 태그 추가
    },
    "도시재생지원센터 센터소개 센터 연혁": {
        "url": "https://www.cheonanurc.or.kr/101",
        "aliases": ["센터연혁", "센터소개센터연혁", "연혁"],
        "tags": ["센터소개"] # <-- 태그 추가
    },
    "도시재생지원센터 센터소개 조직 및 담당": {
        "url": "https://www.cheonanurc.or.kr/25",
        "aliases": ["조직및담당", "센터소개조직및담당", "조직", "담당"],
        "tags": ["센터소개"] # <-- 태그 추가
    },

    # 오시는길 - 하위목록

    "도시재생지원센터 천안시 도시재생지원센터 오시는 길": {
        "url": "https://www.cheonanurc.or.kr/131",
        "aliases": ["천안시도시재생지원센터오시는길", "도시재생지원센터오시는길", "천안시지원센터오는길", "천안시지원센터위치", "천안시센터위치", "천안도시재생센터지도", "천안도시재생센터위치", "천안도시재생지원센터지도", "천안도시재생지원센터위치"],
        "tags": ["오시는길", "오시는길", "가는길", "가는법", "천안", "천안도시재생지원센터", "천안도시재생센터"]
    },
    "도시재생지원센터 봉명지구 도시재생현장지원센터 오시는 길": {
        "url": "https://www.cheonanurc.or.kr/133",
        "aliases": ["봉명지구도시재생현장지원센터오시는길", "봉명지구현장지원센터오는길", "봉명지구지원센터위치", "봉명지구가는법", "봉명지구센터위치", "봉명지구재생센터지도", "봉명지구재생센터위치", "봉명지구도시재생지원센터지도", "봉명지구도시재생지원센터위치"],
        "tags": ["오시는길", "가는길", "가는법", "봉명지구", "현장지원센터", "봉명지구도시재생현장센터"]
    },
    "도시재생지원센터 오룡지구 도시재생현장지원센터 오시는길": {
        "url": "https://www.cheonanurc.or.kr/128",
        "aliases": ["오룡지구 도시재생현장지원센터오시는길", "오룡지구 현장지원센터오는길", "오룡지구지원센터위치", "오룡지구가는법", "오룡지구센터위치", "오룡지구재생센터지도", "오룡지구재생센터위치", "오룡지구도시재생지원센터지도", "오룡지구도시재생지원센터위치"],
        "tags": ["오시는길", "가는길", "가는법", "오룡지구", "현장지원센터", "오룡지구도시재생현장센터"]
    },

    # 사업 소개 부분
    
    "도시재생지원센터 천안 도시재생 총괄사업현황": {
        "url": "https://www.cheonanurc.or.kr/68",
        "aliases": ["천안도시재생총괄사업현황", "총괄사업현황", "총괄사업"],
        "tags": ["도시재생사업", "천안", "천안도시재생지원센터", "천안도시재생센터"]
    },

    "도시재생지원센터 천안 도시재생선도사업": {
        "url": "https://www.cheonanurc.or.kr/27",
        "aliases": ["천안도시재생선도사업", "도시재생선도사업", "선도사업"],
        "tags": ["도시재생사업", "천안", "천안도시재생지원센터", "천안도시재생센터"]
    },

    "도시재생지원센터 천안역세권 도시재생사업": {
        "url": "https://www.cheonanurc.or.kr/71",
        "aliases": ["천안역세권도시재생사업", "역세권도시재생", "천안역세권"],
        "tags": ["도시재생사업", "천안역세권"]
    },

    "도시재생지원센터 남산지구 도시재생사업": {
        "url": "https://www.cheonanurc.or.kr/70",
        "aliases": ["남산지구도시재생사업", "남산지구"],
        "tags": ["도시재생사업", "남산지구"] 
    },

    "도시재생지원센터 봉명지구 도시재생사업": {
        "url": "https://www.cheonanurc.or.kr/72",
        "aliases": ["봉명지구도시재생사업", "봉명지구"],
        "tags": ["도시재생사업", "봉명지구", "봉명지구도시재생현장센터"]
    },

    "도시재생지원센터 오룡지구 도시재생사업": {
        "url": "https://www.cheonanurc.or.kr/74",
        "aliases": ["오룡지구도시재생사업", "오룡지구"],
        "tags": ["도시재생사업", "오룡지구", "오룡지구도시재생현장센터"]
    },

    "도시재생지원센터 천안역세권 혁신지구 도시재생사업": {
        "url": "https://www.cheonanurc.or.kr/75",
        "aliases": ["천안역세권혁신지구도시재생사업", "역세권혁신지구", "혁신지구"],
        "tags": ["도시재생사업", "천안역세권", "천안역세권혁신지구"]
    },

    "도시재생지원센터 오룡지구 민·관 협력형 도시재생 리츠사업": {
        "url": "https://www.cheonanurc.or.kr/73",
        "aliases": ["오룡지구민관협력형도시재생리츠사업", "오룡지구리츠사업", "리츠사업"],
        "tags": ["도시재생사업", "오룡지구", "오룡지구도시재생현장센터"]
    },

    "도시재생지원센터 원성2지구 뉴:빌리지사업": {
        "url": "https://www.cheonanurc.or.kr/140",
        "aliases": ["원성2지구뉴빌리지사업", "뉴빌리지사업", "원성2지구"],
        "tags": ["도시재생사업", "원성2지구"]
    },

    # 커뮤니티 부분

    "도시재생지원센터 천안시 도시재생지원센터 커뮤니티": {
        "url": "https://www.cheonanurc.or.kr/92",
        "aliases": ["천안시도시재생지원센터커뮤니티", "도시재생지원센터커뮤니티", "천안시커뮤니티"],
        "tags": ["현장지원센터", "천안", "천안도시재생지원센터", "천안도시재생센터", "커뮤니티"]
    },
    "도시재생지원센터 봉명지구 도시재생현장지원센터 커뮤니티": {
        "url": "https://www.cheonanurc.or.kr/95",
        "aliases": ["봉명지구도시재생현장지원센터커뮤니티", "봉명지구현장지원센터커뮤니티", "봉명지구커뮤니티", "봉명지구 커뮤니티", "봉명지구도시재생센터커뮤니티"],
        "tags": ["현장지원센터", "봉명지구", "봉명지구도시재생현장센터", "커뮤니티"]
    },
    "도시재생지원센터 오룡지구 도시재생현장지원센터 커뮤니티": {
        "url": "https://www.cheonanurc.or.kr/121",
        "aliases": ["오룡지구도시재생현장지원센터커뮤니티", "오룡지구현장지원센터커뮤니티", "오룡지구커뮤니티", "오룡지구 커뮤니티", "오룡지구도시재생센터커뮤니티"],
        "tags": ["현장지원센터", "오룡지구", "오룡지구도시재생현장센터", "커뮤니티"]
    },

    # 도시재생+ 부분

    "도시재생지원센터 공지사항": {
        "url": "https://www.cheonanurc.or.kr/new",
        "aliases": ["공지사항", "공지", "센터공지"],
        "tags": ["도시재생+", "도시재생플러스"]
    },
    "도시재생지원센터 센터 프로그램 신청": {
        "url": "https://www.cheonanurc.or.kr/41",
        "aliases": ["센터프로그램신청", "프로그램신청", "센터프로그램", "프로그램 신청"],
        "tags": ["도시재생+", "도시재생플러스"]
    },
    "도시재생지원센터 도시재생 투어": {
        "url": "https://www.cheonanurc.or.kr/64",
        "aliases": ["도시재생투어", "투어", "재생투어", "도시재생투어"],
        "tags": ["도시재생+", "도시재생플러스"]
    },

    # 도시재생 투어 - 코스 부분

    "도시재생 투어 일반코스 1": {
        "url": "https://www.cheonanurc.or.kr/78",
        "aliases": ["일반코스1", "도시재생투어일반코스1", "투어일반코스1"],
        "tags": ["일반코스", "도시재생투어", "재생투어"]
    },
    "도시재생 투어 일반코스 2": {
        "url": "https://www.cheonanurc.or.kr/97",
        "aliases": ["일반코스2", "도시재생투어일반코스2", "투어일반코스2"],
        "tags": ["일반코스", "도시재생투어", "재생투어"]
    },
    "도시재생 투어 전문코스 1": {
        "url": "https://www.cheonanurc.or.kr/98",
        "aliases": ["전문코스1", "도시재생투어전문코스1", "투어전문코스1"],
        "tags": ["전문코스", "도시재생투어", "재생투어"]
    },
    "도시재생 투어 전문코스 2": {
        "url": "https://www.cheonanurc.or.kr/99",
        "aliases": ["전문코스2", "도시재생투어전문코스2", "투어전문코스2"],
        "tags": ["전문코스", "도시재생투어", "재생투어"]
    },
    "도시재생 투어 전문코스 3": {
        "url": "https://www.cheonanurc.or.kr/100",
        "aliases": ["전문코스3", "도시재생투어전문코스3", "투어전문코스3"],
        "tags": ["전문코스", "도시재생투어", "재생투어"]
        
    },

    # 아카이브 부분

    "도시재생지원센터 발간물": {
        "url": "https://www.cheonanurc.or.kr/36",
        "aliases": ["발간물", "센터발간물", "자료집"],
        "tags": ["아카이브"]
    },
    "도시재생지원센터 홍보 동영상": {
        "url": "https://www.cheonanurc.or.kr/httpswwwyoutubecomwatchvghzmqbIRJo0",
        "aliases": ["홍보동영상", "홍보영상", "동영상자료"],
        "tags": ["아카이브"]
    },
    "도시재생지원센터 도시재생 뉴스": {
        "url": "https://www.cheonanurc.or.kr/35",
        "aliases": ["도시재생뉴스", "뉴스", "센터뉴스"],
        "tags": ["아카이브"]
    },
    "도시재생지원센터 전문가 오피니언": {
        "url": "https://www.cheonanurc.or.kr/37",
        "aliases": ["전문가오피니언", "오피니언", "전문가칼럼"],
        "tags": ["아카이브"]
    },
    "도시재생지원센터 마을기자단 및 인터뷰": {
        "url": "https://www.cheonanurc.or.kr/108",
        "aliases": ["마을기자단및인터뷰", "마을기자단", "인터뷰"],
        "tags": ["아카이브"]
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

# programs.py 파일 맨 아래에 추가

def get_all_tags() -> list[str]:
    """모든 프로그램의 태그들을 중복 없이 리스트로 반환합니다."""
    all_tags = set()
    for details in _PROGRAMS.values():
        if "tags" in details:
            all_tags.update(details["tags"])
    return list(all_tags)

def get_programs_by_tag(tag: str) -> list[dict]:
    """특정 태그가 포함된 모든 프로그램의 정보를 리스트로 반환합니다."""
    tagged_programs = []
    for name, details in _PROGRAMS.items():
        if "tags" in details and tag in details["tags"]:
            # 정식 명칭(name)을 정보에 추가해서 반환
            program_info = details.copy()
            program_info["name"] = name
            tagged_programs.append(program_info)
    return tagged_programs