_PROGRAM_URLS = {
    "도시재생지원센터": "https://www.cheonanurc.or.kr/",
    "청년몰 지원사업": "https://cheonan.go.kr/youthmall",
    "원도심 도시재생": "https://cheonan.go.kr/urbanrenewal",
    # 필요시 지속 확장
}

def get_program_url(prog_name: str) -> str | None:
    return _PROGRAM_URLS.get(prog_name)
