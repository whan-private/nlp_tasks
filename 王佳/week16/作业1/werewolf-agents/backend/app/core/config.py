from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，从 .env 文件和环境变量加载。"""

    # ---- 应用 ----
    APP_NAME: str = "Werewolf Agents"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ---- LLM ----
    OPENAI_API_KEY: str = "sk-7458206891744b7aa46d6f7366fecdd5"
    OPENAI_MODEL: str = "qwen-plus"
    OPENAI_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 500

    # ---- 数据库 ----
    DATABASE_URL: str = "mysql+pymysql://root:wangjia%40123456@localhost:3306/werewolf"

    # ---- 游戏 ----
    DEFAULT_PLAYER_COUNT: int = 9
    MAX_SPEAK_LENGTH: int = 500
    VOTE_TIMEOUT_SECONDS: int = 30

    # ---- 日志 ----
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json / text
    LOG_DIR: str = "../logs"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
