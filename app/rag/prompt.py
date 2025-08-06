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

ALL_SOURCES_PROMPT = dedent(
    """
    아래 세 가지 출처를 참고하여 질문에 대한 최선의 답변을 제공하세요.
    1) 로컬 문서:
    {local_ctx}

    2) 룰 기반 결과:
    {rule_ctx}

    3) 웹 검색 결과:
    {web_ctx}

    위에 없으면 모델 지식을 활용해 답을 작성하세요.

    질문: {question}
    답변:
    """
)
