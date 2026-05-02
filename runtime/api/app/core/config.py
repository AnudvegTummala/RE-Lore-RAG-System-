from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    qdrant_url: str = "http://localhost:6333"

    clip_service_url: str = "http://localhost:8001"

    groq_api_key: str = ""
    groq_model: str = "llama3-70b-8192"

    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
