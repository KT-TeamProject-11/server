import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from utils.intent_prompt import INTENT_PROMPT_TEMPLATE

def classify_intent_and_extract_entity(q: str, llm_instance: ChatOpenAI) -> dict:
    """LLM을 사용해 사용자의 의도를 분석하고 프로그램 이름을 추출합니다."""

    # ▼▼▼▼▼ 시스템 메시지를 한국어로 수정 ▼▼▼▼▼
    intent_prompt = SystemMessage(content=INTENT_PROMPT_TEMPLATE)

    try:
        response = llm_instance.invoke([intent_prompt, HumanMessage(content=q)])
        result = json.loads(response.content)
        return result
    except (json.JSONDecodeError, TypeError):
        return {"intent": "general_question", "program_name": None}