from langchain_openai import ChatOpenAI

_judge = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)


def fact_check(question: str, answer: str) -> bool:
    prompt = (
        "주어진 Q&A 의 사실 여부를 판단하세요. "
        "정확하면 'YES', 부정확·모호하면 'NO' 만 출력합니다.\n\n"
        f"Q: {question}\nA: {answer}\n판단:"
    )
    verdict = _judge.predict(prompt).strip().upper()   # 문자열 직접 입력
    return verdict.startswith("Y")
