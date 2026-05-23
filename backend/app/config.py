from __future__ import annotations
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = Path(__file__).resolve().parent / "storage"
OUTPUTS_DIR = STORAGE_DIR / "outputs"

for d in [STORAGE_DIR, OUTPUTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class Settings:
    ai_provider: str = os.getenv("AI_PROVIDER", "none")
    ai_api_key: str = os.getenv("AI_API_KEY", "")
    ai_base_url: str = os.getenv("AI_BASE_URL", "")
    ai_model: str = os.getenv("AI_MODEL", "")
    max_width: int = 256
    max_height: int = 256
    min_size: int = 16
    max_frames: int = 16


settings = Settings()
