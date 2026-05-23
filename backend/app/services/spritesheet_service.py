from __future__ import annotations
import io
from PIL import Image


class SpriteSheetService:
    @staticmethod
    def build_from_pil(
        images: list[Image.Image],
        frame_w: int,
        frame_h: int,
    ) -> tuple[bytes, dict]:
        """横向排列拼接 sprite sheet，返回 (PNG bytes, frame_metadata)。"""
        if not images:
            return b"", {}

        n = len(images)
        sheet_w = n * frame_w
        sheet_h = frame_h

        sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
        frames = []

        for i, img in enumerate(images):
            x = i * frame_w
            if img.size != (frame_w, frame_h):
                img = img.resize((frame_w, frame_h), Image.NEAREST)
            sheet.paste(img, (x, 0))
            frames.append({
                "filename": f"frame_{i}.png",
                "x": x,
                "y": 0,
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
            "frames": frames,
        }
