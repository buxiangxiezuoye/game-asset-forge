from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（优先级：.env.local > .env）
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = Path(__file__).resolve().parent / "storage"
OUTPUTS_DIR = STORAGE_DIR / "outputs"

for d in [STORAGE_DIR, OUTPUTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class Settings:
    # AI Image Provider（可插拔架构）
    image_provider_mode: str = os.getenv("IMAGE_PROVIDER_MODE", "mock")
    image_provider_endpoint: str = os.getenv("IMAGE_PROVIDER_ENDPOINT", "")
    image_provider_api_key: str = os.getenv("IMAGE_PROVIDER_API_KEY", "")
    image_provider_model: str = os.getenv("IMAGE_PROVIDER_MODEL", "")
    image_provider_backend: str = os.getenv("IMAGE_PROVIDER_BACKEND", "auto")
    image_provider_timeout: int = int(os.getenv("IMAGE_PROVIDER_TIMEOUT", "120"))
    image_provider_steps: int = int(os.getenv("IMAGE_PROVIDER_STEPS", "20"))
    image_provider_cfg: float = float(os.getenv("IMAGE_PROVIDER_CFG", "7.0"))
    image_provider_sampler: str = os.getenv("IMAGE_PROVIDER_SAMPLER", "Euler a")
    comfyui_output_dir: str = os.getenv("COMFYUI_OUTPUT_DIR", "")

    # 资源限制
    max_batch_size: int = int(os.getenv("MAX_BATCH_SIZE", "10"))
    max_width: int = 256
    max_height: int = 256
    min_size: int = 16
    max_frames: int = 16

    # Sprite sheet 帧间间距（像素）
    spritesheet_padding: int = 1


settings = Settings()
