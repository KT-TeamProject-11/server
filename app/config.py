from dotenv import load_dotenv
import os

load_dotenv()  
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY 가 설정되지 않았습니다!")
