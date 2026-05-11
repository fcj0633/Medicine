from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BASE_DIR.parent


class Settings(BaseSettings):
    secret_key: str = "medication-reminder-secret-key-2024"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    database_url: str = "mysql+pymysql://root:274226@localhost:3306/medication_reminder?charset=utf8mb4"

    upload_dir: str = str(BASE_DIR / "uploads")
    audio_dir: str = str(BASE_DIR / "audio")

    ocr_provider: str = "hybrid"
    baidu_ocr_api_key: str | None = None
    baidu_ocr_secret_key: str | None = None
    baidu_ocr_timeout: float = 10.0

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()

SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
DATABASE_URL = settings.database_url

UPLOAD_DIR = settings.upload_dir
AUDIO_DIR = settings.audio_dir

OCR_PROVIDER = settings.ocr_provider.strip().lower()
BAIDU_OCR_API_KEY = settings.baidu_ocr_api_key
BAIDU_OCR_SECRET_KEY = settings.baidu_ocr_secret_key
BAIDU_OCR_TIMEOUT = settings.baidu_ocr_timeout

Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(AUDIO_DIR).mkdir(parents=True, exist_ok=True)
