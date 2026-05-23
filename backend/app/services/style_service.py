from __future__ import annotations
from app.models import StyleId, StyleInfo

STYLE_DATA: dict[StyleId, dict] = {
    StyleId.PIXEL_ART: {
        "name": "像素艺术",
        "description": "经典 8-bit/16-bit 像素风格，硬边缘、有限色板，复古游戏感",
        "promptPrefix": "pixel art, 16-bit, sprite, game asset, sharp edges, limited palette, retro game",
        "negativePrompt": "blurry, smooth, realistic, 3d, photo, gradient, anti-aliased",
        "defaultPalette": ["#2c3e50", "#e74c3c", "#3498db", "#2ecc71", "#f1c40f", "#ecf0f1"],
        "recommendedSizes": [16, 32, 48, 64],
    },
    StyleId.FLAT_CARTOON: {
        "name": "扁平卡通",
        "description": "简洁圆润的扁平设计，高饱和配色、清晰描边，适合休闲手游",
        "promptPrefix": "flat cartoon, 2d game asset, bold outlines, vibrant colors, simple shapes, casual game art",
        "negativePrompt": "realistic, 3d, photo, complex shading, noise, grain, dark moody",
        "defaultPalette": ["#e74c3c", "#f39c12", "#2ecc71", "#3498db", "#9b59b6", "#ffffff"],
        "recommendedSizes": [32, 64, 128, 256],
    },
}


class StyleService:
    @staticmethod
    def list_styles() -> list[StyleInfo]:
        return [
            StyleInfo(
                id=preset,
                name=data["name"],
                description=data["description"],
                promptPrefix=data["promptPrefix"],
                negativePrompt=data["negativePrompt"],
                defaultPalette=data["defaultPalette"],
                recommendedSizes=data["recommendedSizes"],
            )
            for preset, data in STYLE_DATA.items()
        ]

    @staticmethod
    def get_style(preset: StyleId) -> dict:
        return STYLE_DATA.get(preset, STYLE_DATA[StyleId.PIXEL_ART])
