from __future__ import annotations
import io
import json
import zipfile
from datetime import datetime
from PIL import Image
import base64
from app.models import AssetResult, ExportFormat
from app.services.spritesheet_service import SpriteSheetService


class ExportService:
    @staticmethod
    def export(assets: list[AssetResult], fmt: ExportFormat) -> tuple[bytes, str, str]:
        """返回 (bytes, mime_type, filename)"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        if fmt == ExportFormat.PNG and len(assets) == 1:
            return ExportService._export_single_png(assets[0])

        if fmt == ExportFormat.SPRITE_SHEET:
            return ExportService._export_spritesheet(assets, ts)

        if fmt == ExportFormat.ZIP:
            return ExportService._export_zip(assets, ts)

        return b"", "application/octet-stream", "export.bin"

    @staticmethod
    def _export_single_png(asset: AssetResult) -> tuple[bytes, str, str]:
        img_bytes = base64.b64decode(asset.image_base64)
        fname = f"{asset.asset_type.value}_{asset.id}.png"
        return img_bytes, "image/png", fname

    @staticmethod
    def _export_spritesheet(assets: list[AssetResult], ts: str) -> tuple[bytes, str, str]:
        png_bytes, frame_data = SpriteSheetService.build(assets)
        json_bytes = json.dumps(frame_data, ensure_ascii=False, indent=2).encode("utf-8")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("spritesheet.png", png_bytes)
            zf.writestr("spritesheet.json", json_bytes)
        fname = f"spritesheet_{ts}.zip"
        return buf.getvalue(), "application/zip", fname

    @staticmethod
    def _export_zip(assets: list[AssetResult], ts: str) -> tuple[bytes, str, str]:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # 单张 PNG
            for asset in assets:
                img_bytes = base64.b64decode(asset.image_base64)
                zf.writestr(f"sprites/{asset.asset_type.value}_{asset.id}.png", img_bytes)

            # Sprite Sheet
            png_bytes, frame_data = SpriteSheetService.build(assets)
            zf.writestr("spritesheet/sheet.png", png_bytes)
            zf.writestr("spritesheet/sheet.json",
                       json.dumps(frame_data, ensure_ascii=False, indent=2).encode("utf-8"))

            # metadata.json
            meta = {
                "version": "1.0",
                "generated_at": datetime.now().isoformat(),
                "generator": "game-asset-forge",
                "assets": [
                    {
                        "id": a.id,
                        "file": f"sprites/{a.asset_type.value}_{a.id}.png",
                        "prompt": a.prompt,
                        "type": a.asset_type.value,
                        "style": a.style.value,
                        "size": a.size,
                        "pivot": a.metadata.get("pivot", [a.size // 2, a.size // 2]),
                        "tags": a.metadata.get("tags", []),
                        "seed": a.seed,
                    }
                    for a in assets
                ],
            }
            zf.writestr("metadata.json", json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8"))

            # README
            readme = ExportService._build_readme(assets)
            zf.writestr("README.txt", readme.encode("utf-8"))

        fname = f"asset_export_{ts}.zip"
        return buf.getvalue(), "application/zip", fname

    @staticmethod
    def _build_readme(assets: list[AssetResult]) -> str:
        return f"""Game Asset Forge — 导出素材包
================================
生成时间: {datetime.now().isoformat()}
素材数量: {len(assets)}

使用方法:
  Unity:
    1. 将 sprites/ 文件夹拖入 Assets 窗口
    2. 选择图片，在 Inspector 中设置 Texture Type = Sprite (2D and UI)
    3. 如需使用 Tilemap，设置 Texture Type = Sprite，Sprite Mode = Multiple
    4. 导入 spritesheet/sheet.json 查看帧数据

  Godot:
    1. 将 sprites/ 文件夹复制到项目目录
    2. 在 Import 选项卡中将图片导入为 Texture
    3. 使用 Sprite2D 节点引用素材
    4. sprite sheet 可直接作为 AtlasTexture 使用

素材列表:
"""
        for a in assets:
            readme += f"  - {a.asset_type.value}/{a.id}.png  \"{a.prompt}\"  {a.size}×{a.size}\n"
        return readme
