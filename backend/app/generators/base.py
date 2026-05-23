from __future__ import annotations
import io
import base64
import random
from abc import ABC, abstractmethod
from PIL import Image
from app.models import GenerateRequest


class BaseGenerator(ABC):
    def __init__(self, request: GenerateRequest):
        self.req = request
        self.seed = request.seed if request.seed is not None else random.randint(0, 2**31 - 1)
        self.rng = random.Random(self.seed)
        self.pc = self._hex_to_rgb(self._pick_color(request))

    def _pick_color(self, req: GenerateRequest) -> str:
        """如果没有传入主色，从 prompt 关键词推断"""
        color_map = {
            "火焰": "#e74c3c", "火": "#e74c3c", "红": "#e74c3c",
            "冰": "#3498db", "水": "#3498db", "蓝": "#3498db",
            "草": "#2ecc71", "森林": "#27ae60", "绿": "#2ecc71",
            "毒": "#8e44ad", "暗": "#2c3e50", "黑": "#2c3e50",
            "光": "#f1c40f", "金": "#f39c12", "黄": "#f1c40f",
            "银": "#bdc3c7", "血": "#c0392b", "紫": "#9b59b6",
            "天空": "#87ceeb", "土": "#d35400",
        }
        prompt = req.prompt
        for kw, clr in color_map.items():
            if kw in prompt:
                return clr
        return "#3498db"

    def generate_single(self, frame_index: int = 0) -> tuple[Image.Image, dict]:
        """生成单帧素材"""
        w, h = self.req.width, self.req.height
        bg = (0, 0, 0, 0) if self.req.transparent else (255, 255, 255, 255)
        img = Image.new("RGBA", (w, h), bg)
        meta = self._draw(img, frame_index)
        meta.update({
            "seed": self.seed,
            "width": w,
            "height": h,
            "style": self.req.styleId.value,
            "asset_type": self.req.assetType.value,
            "prompt": self.req.prompt,
            "animation": self.req.animation.value,
            "frame": frame_index,
            "pivot": [w // 2, h // 2],
        })
        return img, meta

    @abstractmethod
    def _draw(self, img: Image.Image, frame_index: int = 0) -> dict: ...

    # ========== 工具方法 ==========

    def to_base64(self, img: Image.Image) -> str:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    def save_png(self, img: Image.Image, path: str) -> None:
        img.save(path, format="PNG")

    def _shift_color(self, base: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
        return tuple(max(0, min(255, int(c * factor + self.rng.randint(-20, 20)))) for c in base)

    def _darker(self, base: tuple[int, int, int], amount: int = 50) -> tuple[int, int, int]:
        return tuple(max(0, c - amount) for c in base)

    def _lighter(self, base: tuple[int, int, int], amount: int = 50) -> tuple[int, int, int]:
        return tuple(min(255, c + amount) for c in base)

    @staticmethod
    def _hex_to_rgb(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    @staticmethod
    def _alpha(c: tuple[int, int, int], a: int) -> tuple[int, int, int, int]:
        return (c[0], c[1], c[2], a)
