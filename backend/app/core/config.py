# backend/app/core/config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # 大厂通用路由配置
    PROJECT_NAME: str = "FDE-Intelligent-Product-Engineering"
    
    # LLM 基础设施路由层配置 (默认通过 OpenRouter 或大厂专属骨干网中转)
    OPENAI_API_KEY: str = "你的KEY"
    OPENAI_BASE_URL: str = "你的模型URL"
    MODEL_NAME: str = "gpt-oss-120b"
    
    # 灰度监控与安全防线硬阈值
    TOKEN_BUDGET_PER_SESSION: int = 50000  # 单次会话 Token 熔断上限
    P99_LATENCY_ALERT_MS: float = 35000.0  # P99 延迟报警阈值 (35秒)
    COST_LIMIT_RMB: float = 50.0            # 资损报警财务红线

    class Config:
        env_file = ".env"

settings = Settings()