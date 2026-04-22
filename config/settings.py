from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "火眼智擎—汽配领域知产保护分析助手"
    debug: bool = True

    # 单账号密码鉴权（方案一）
    auth_enabled: bool = True
    auth_username: str = "admin"
    auth_password: str = "change-this-password"

    # 数据库配置
    database_path: Path = BASE_DIR / "data" / "intellectual_property.db"

    # 数据目录
    data_dir: Path = BASE_DIR / "data"
    upload_dir: Path = BASE_DIR / "data" / "uploads"

    class Config:
        env_file = BASE_DIR / ".env"


settings = Settings()


def _resolve_project_path(path: Path) -> Path:
    resolved_path = Path(path)
    if resolved_path.is_absolute():
        return resolved_path
    return (BASE_DIR / resolved_path).resolve()


settings.database_path = _resolve_project_path(settings.database_path)
settings.data_dir = _resolve_project_path(settings.data_dir)
settings.upload_dir = _resolve_project_path(settings.upload_dir)

# 确保目录存在
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.database_path.parent.mkdir(parents=True, exist_ok=True)
