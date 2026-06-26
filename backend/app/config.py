"""PI Vision AI - Application configuration."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PI Vision AI"
    app_env: str = "production"
    app_debug: bool = False
    secret_key: str = "change-me"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173"

    database_url: str = "postgresql+asyncpg://pivision:pivision@localhost:5432/pivision"

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    jwt_secret_key: str = "change-me-jwt"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 480
    jwt_refresh_token_expire_days: int = 7

    storage_path: str = "/data/storage"
    snapshots_path: str = "/data/storage/snapshots"
    clips_path: str = "/data/storage/clips"
    logs_path: str = "/data/storage/logs"
    evidence_pre_seconds: int = 10
    evidence_post_seconds: int = 20

    ai_model: str = "yolov8s.pt"
    ai_confidence: float = 0.35
    ai_min_object_size: int = 20
    ai_analysis_width: int = 640
    ai_imgsz: int = 1280
    ai_default_fps: int = 5
    ai_load_profile: str = "medium"
    ai_device: str = "cpu"
    tensorrt_enabled: bool = False

    llm_enabled: bool = False
    llm_provider: str = "ollama"
    llm_analyze_on_event: bool = True
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "llava"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    llm_max_tokens: int = 800
    llm_system_prompt: str = ""
    llm_describe_cooldown_seconds: int = 3600

    rtsp_timeout: int = 10
    rtsp_reconnect_delay: int = 5
    rtsp_max_retries: int = 10
    use_substream_for_ai: bool = True

    dahua_poll_interval: int = 2
    dahua_event_buffer_size: int = 100

    webhook_enabled: bool = True
    webhook_default_url: str = ""
    mqtt_enabled: bool = False
    mqtt_broker: str = "mqtt://localhost:1883"
    mqtt_topic: str = "pivision/events"
    mqtt_username: str = ""
    mqtt_password: str = ""

    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    health_check_interval: int = 30
    degraded_mode_cpu_threshold: int = 85
    degraded_mode_gpu_threshold: int = 90

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
