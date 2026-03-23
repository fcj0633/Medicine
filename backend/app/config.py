import os

SECRET_KEY = os.getenv("SECRET_KEY", "medication-reminder-secret-key-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

DATABASE_URL = "mysql+pymysql://root:274226@localhost:3306/medication_reminder?charset=utf8mb4"

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audio")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
