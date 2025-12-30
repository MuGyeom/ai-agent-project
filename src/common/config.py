from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # [Infra]
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:29092"
    KAFKA_BROKER: str | None = None
    KAFKA_TOPIC_RAW: str = "topic_raw"
    KAFKA_TOPIC_API: str = "api-queue"
    KAFKA_TOPIC_SEARCH: str = "search-queue"
    KAFKA_TOPIC_AI: str = "ai-queue"

    KAFKA_GROUP_API: str = "api-group"
    KAFKA_GROUP_SEARCH: str = "search-group"
    KAFKA_GROUP_AI: str = "ai-group"

    # [Search]
    SEARCH_ENGINE_API_KEY: str | None = None

    # [AI]
    OPENAI_API_KEY: str | None = None

    # [Database]
    DATABASE_URL: str = "postgresql://agent:agent_password@postgres:5432/ai_agent"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # 정의되지 않은 환경변수가 있어도 에러 내지 않음
    )


# 인스턴스 생성 (이걸 import 해서 씀)
settings = Settings()
