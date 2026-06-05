import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # API Keys
    apollo_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    apollo_match_url: str = "https://api.apollo.io/api/v1/people/match"
    reveal_personal_emails: bool = False
    reveal_phone_number: bool = False

    # Seller/Company Profile Config (decides the Prompt dynamically)
    seller_company: str = "Clarion Technologies"
    seller_services: str = "offshore custom mobile app development, React Native, Flutter, enterprise mobile solutions, SaaS and web development"
    seller_value_props: str = "up to 60% cost reduction, dedicated teams onboarded in 1-2 weeks, ISO certified, experienced developers (5-15 years), 20+ years track record, free proof-of-concept, no long-term lock-in"

    # Redis Config
    redis_url: str = "redis://redis:6379/0"

    # Celery Config
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"

    # Rate Limiting Settings
    rate_limit_requests: int = 10  # number of requests allowed
    rate_limit_window_seconds: int = 60  # per 60 seconds (1 minute)

    # Server Settings
    host: str = "0.0.0.0"
    port: int = 1010
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
