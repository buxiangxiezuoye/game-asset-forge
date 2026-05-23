from __future__ import annotations
from app.models import StyleId, StyleInfo

STYLE_DATA: dict[StyleId, dict] = {
    StyleId.PIXEL_ART: {
        "name": "像素艺术",
        "description": "经典 8-bit/16-bit 像素风格，硬边缘、有限色板，复古游戏感，适合 Roguelike 和平台跳跃游戏",
        "promptPrefix": "pixel art, 16-bit, sprite, game asset, sharp edges, limited palette, retro game",
        "negativePrompt": "blurry, smooth, realistic, 3d, photo, gradient, anti-aliased",
        "defaultPalette": ["#2c3e50", "#e74c3c", "#3498db", "#2ecc71", "#f1c40f", "#ecf0f1"],
        "recommendedSizes": [16, 32, 48, 64],
    },
    StyleId.FLAT_CARTOON: {
        "name": "扁平卡通",
        "description": "简洁圆润的扁平设计，高饱和配色、清晰描边，适合休闲手游和儿童向游戏",
        "promptPrefix": "flat cartoon, 2d game asset, bold outlines, vibrant colors, simple shapes, casual game art",
        "negativePrompt": "realistic, 3d, photo, complex shading, noise, grain, dark moody",
        "defaultPalette": ["#e74c3c", "#f39c12", "#2ecc71", "#3498db", "#9b59b6", "#ffffff"],
        "recommendedSizes": [32, 64, 128, 256],
    },
    StyleId.FANTASY_PAINTERLY: {
        "name": "幻想手绘",
        "description": "暖色调手绘质感，柔光与渐变过渡，适用于奇幻 RPG 和中世纪风格游戏",
        "promptPrefix": "fantasy painterly, hand-painted, 2d game sprite, warm tones, soft lighting, rpg asset, medieval",
        "negativePrompt": "flat, vector, pixel art, cartoon, modern, sci-fi, cold colors",
        "defaultPalette": ["#8B4513", "#DAA520", "#556B2F", "#8B0000", "#4A0E4E", "#F5DEB3"],
        "recommendedSizes": [64, 128, 256],
    },
    StyleId.SCI_FI_UI: {
        "name": "科幻 UI",
        "description": "冷色调科技感，霓虹发光、半透明面板、几何线条，适合科幻/赛博朋克风格 UI 和 HUD",
        "promptPrefix": "sci-fi ui, cyberpunk, neon glow, tech interface, geometric, dark theme, futuristic hud, translucent",
        "negativePrompt": "organic, nature, medieval, fantasy, rustic, hand-drawn, cartoon, childish",
        "defaultPalette": ["#00ffff", "#ff00ff", "#00ff88", "#1a1a2e", "#0d7377", "#16213e"],
        "recommendedSizes": [16, 32, 64, 128],
    },
    StyleId.HAND_DRAWN: {
        "name": "手绘素描",
        "description": "铅笔/墨水手绘质感，轻微纹理与不规则线条，适合独立游戏和艺术风格作品",
        "promptPrefix": "hand-drawn sketch, ink drawing, 2d game sprite, pencil texture, indie game art, organic lines",
        "negativePrompt": "3d, photo, digital art, vector, perfect lines, symmetrical, mechanical, neon",
        "defaultPalette": ["#3a3a3a", "#7a7a7a", "#c4a882", "#8c6e5a", "#e8d5b7", "#4a6741"],
        "recommendedSizes": [32, 64, 128],
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
