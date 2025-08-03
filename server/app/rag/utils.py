import re

def extract_program_name(q: str) -> str | None:
    patterns = [
        r"(.+?)\s*(?:프로그램|사업|서비스)?(?:은|는)?\s*어디(서|에서)\s*볼 수",
        r"(.+?)\s*(?:를)?\s*(?:어디서|어디에서)?\s*확인할 수",
        r"(.+?)\s*(?:페이지|사이트|홈페이지)?\s*알려줘",
        r"(.+?)\s*(?:사이트|홈페이지)?(?:은|는)?\s*어디야",
    ]
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            return match.group(1).strip()
    return None
