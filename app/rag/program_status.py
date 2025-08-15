# app/rag/program_status.py
import re
import glob
from pathlib import Path
from app.config import CLEAN_DIR

def _load_markdown(path: Path) -> str:
    """Markdown 파일을 안전하게 읽어 문자열로 반환"""
    try:
        return path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return ''

def parse_current_programs(category: str = '도시재생+') -> list[str]:
    """
    CLEAN_DIR 하위 크롤링된 md 파일에서
    '## 현재 진행중인 프로그램' 섹션을 찾아 목록을 추출
    """
    programs = []
    text_dir = Path(CLEAN_DIR) / category / 'text'
    if not text_dir.exists():
        return programs

    for md_path in glob.glob(str(text_dir / '*.md')):
        md_text = _load_markdown(Path(md_path))
        # 해당 섹션 찾기
        parts = md_text.split('## 현재 진행중인 프로그램', 1)
        if len(parts) < 2:
            continue
        section = parts[1]
        # 다음 섹션 시작 전까지 잘라내기
        section = section.split('## ', 1)[0]
        # 리스트 항목 추출
        items = re.findall(r'^-\s*(.+)', section, flags=re.MULTILINE)
        programs.extend([item.strip() for item in items if item.strip()])

    # 중복 제거
    return list(dict.fromkeys(programs))

def get_program_status_answer() -> str:
    """현재 진행중인 프로그램 상태를 문장 형태로 반환"""
    current = parse_current_programs()
    if not current:
        return '현재 진행중인 프로그램이 없습니다.'
    return '현재 진행중인 프로그램은 다음과 같습니다:\n' + '\n'.join(f'- {p}' for p in current)
