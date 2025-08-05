import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

def classify_intent_and_extract_entity(q: str, llm_instance: ChatOpenAI) -> dict:
    """LLM을 사용해 사용자의 의도를 분석하고 프로그램 이름을 추출합니다."""

    # ▼▼▼▼▼ 시스템 메시지를 한국어로 수정 ▼▼▼▼▼
    intent_prompt = SystemMessage(content="""
당신은 사용자의 의도를 'find_program_url' 또는 'general_question'으로 분류하고, '프로그램 이름'을 추출하는 전문가입니다.
'find_program_url'은 사용자가 웹사이트나 링크를 물어볼 때의 의도입니다.

- 질문: "센터소개는 어디서 봐?" -> 추출: "센터소개"
- 질문: "사업소개 페이지" -> 추출: "사업소개"
- 질문: "도시재생지원센터에 대해 알려줘" -> 의도: "general_question"

반드시 {"intent": "...", "program_name": "..."} 형식의 JSON 객체로만 응답해야 합니다.
""")

    try:
        response = llm_instance.invoke([intent_prompt, HumanMessage(content=q)])
        result = json.loads(response.content)
        return result
    except (json.JSONDecodeError, TypeError):
        return {"intent": "general_question", "program_name": None}