from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./storyweave.db"
    openai_base_url: str = ""
    openai_api_key: str = ""
    openai_model: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    seed_enabled: bool = False
    url_fetch_allowed_hosts: str = ""
    url_fetch_timeout_seconds: float = 10
    url_fetch_max_bytes: int = 2_000_000
    web_search_endpoint: str = "https://html.duckduckgo.com/html/"
    web_retrieval_provider: str = "auto"
    mcp_search_command: str = "/usr/local/bin/python"
    mcp_search_server_path: str = "/opt/mcp-searxng/server.py"
    mcp_search_timeout_seconds: float = 20
    mcp_fetch_max_chars: int = 8000
    searxng_url: str = ""
    llm_timeout_seconds: float = 180
    context_budget_chars: int = 24_000
    context_history_max_chars: int = 10_000
    context_web_max_chars: int = 5_000
    context_digest_target_chars: int = 4_000
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]

    @property
    def fetch_allowed_hosts(self) -> set[str]:
        return {value.strip().lower() for value in self.url_fetch_allowed_hosts.split(",") if value.strip()}

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
