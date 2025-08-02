from textwrap import dedent

PROMPT = dedent(
    """
    당신은 주어진 'context'에서만 정보를 찾아
    질문에 한국어로 간결·정확하게 답합니다.
    문맥에 없으면 "모르겠습니다"라고 답합니다.

    --------------------
    {context}
    --------------------

    질문: {question}
    답변:
    """
)
