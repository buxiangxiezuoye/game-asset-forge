from __future__ import annotations
import io
from PIL import Image
from app.config import settings


class SpriteSheetService:
    """横向排列 sprite sheet，每帧间加入透明间距。"""

    @staticmethod
    def build_from_pil(
        images: list[Image.Image],
        frame_w: int,
        frame_h: int,
    ) -> tuple[bytes, dict]:
        """
        横向拼接 sprite sheet。

        Args:
            images: 帧列表（RGBA PIL Image）
            frame_w: 期望帧宽
            frame_h: 期望帧高

        Returns:
            (PNG bytes, metadata dict)
        """
        if not images:
            return b"", {}

        n = len(images)
        pad = settings.spritesheet_padding  # 帧间间距
        # 总宽 = n * 帧宽 + (n+1) * 间距 （首尾也留白）
        sheet_w = n * frame_w + (n + 1) * pad
        sheet_h = frame_h + 2 * pad

        sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
        frames = []

        for i, img in enumerate(images):
            # 统一帧尺寸
            if img.size != (frame_w, frame_h):
                img = img.resize((frame_w, frame_h), Image.NEAREST)
            # 贴入带间距的位置
            x = pad + i * (frame_w + pad)
            y = pad
            sheet.paste(img, (x, y))
            frames.append({
                "filename": f"frame_{i}.png",
                "x": x,
                "y": y,
                "w": frame_w,
                "h": frame_h,
                "duration": 100 if i == 0 else 150,
            })

        buf = io.BytesIO()
        sheet.save(buf, format="PNG")
        return buf.getvalue(), {
            "size": [sheet_w, sheet_h],
            "frameWidth": frame_w,
            "frameHeight": frame_h,
            "frameCount": n,
            "layout": "horizontal",
            "padding": pad,
            "frames": frames,
        }
