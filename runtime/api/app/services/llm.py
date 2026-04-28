from functools import lru_cache

from langchain_groq import ChatGroq

from app.core.config import settings


@lru_cache(maxsize=1)
def get_llm() -> ChatGroq:
    return ChatGroq(
        model=settings.groq_model,
        groq_api_key=settings.groq_api_key,
        streaming=True,
        temperature=0.2,
    )
