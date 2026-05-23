"""
程序化 2D 游戏素材生成器。

设计原则：
  - pixel_art:  低分辨率绘制 → NEAREST 放大，保证逐像素清晰
  - flat_cartoon: 全分辨率绘制，圆角+阴影+明亮配色
  - 中文 prompt 关键词驱动颜色和形状
  - 动画帧有可见差异（浮动/偏移/变形）
"""
from __future__ import annotations
import math
from PIL import Image, ImageDraw
from app.generators.base import BaseGenerator
from app.models import AssetType, StyleId, AnimationType


# ================================================================
# 关键词解析
# ================================================================

class KeywordParser:
    """从中文 prompt 中提取颜色、形状、元素。"""

    COLOR_MAP = {
        "红": (220, 50, 50), "赤": (200, 40, 40), "火": (230, 80, 30),
        "蓝": (50, 100, 220), "水": (50, 100, 220), "冰": (120, 200, 240),
        "绿": (50, 180, 80), "草": (60, 160, 50), "森": (40, 130, 40),
        "黄": (240, 200, 40), "金": (240, 180, 30),
        "紫": (150, 50, 200), "毒": (140, 50, 180),
        "白": (240, 240, 245), "银": (190, 190, 200),
        "黑": (40, 40, 50), "暗": (35, 35, 45), "影": (50, 45, 60),
        "橙": (240, 130, 30), "粉": (240, 140, 180),
        "棕": (140, 100, 60), "土": (170, 130, 80),
        "灰": (140, 140, 150), "石": (120, 120, 130),
    }

    SHAPE_MAP = {
        AssetType.ENEMY: {
            "keywords": ["史莱姆", "slime"], "shape": "slime",
        },
        AssetType.ITEM: {
            "keywords": ["剑", "刀", "sword", "blade"], "shape": "sword",
            "_fallback_keywords": ["药水", "药", "potion"], "_fallback_shape": "potion",
            "__fallback_keywords": ["宝箱", "chest", "箱"], "__fallback_shape": "chest",
            "___fallback_keywords": ["盾", "shield"], "___fallback_shape": "shield",
        },
    }

    @classmethod
    def parse(cls, prompt: str, asset_type: AssetType) -> dict:
        """返回 {primary, secondary, dark, accent, shape, element}"""
        p = prompt.lower()

        # 颜色检测
        primary = (120, 120, 220)  # 默认蓝色
        for kw, rgb in cls.COLOR_MAP.items():
            if kw in prompt:
                primary = rgb
                break

        # 形状检测
        shape = cls._detect_shape(p, asset_type)

        # 辅助色
        secondary = cls._lighten(primary, 0.7)
        dark = cls._darken(primary, 0.5)
        accent = cls._complement(primary)

        return {
            "primary": primary,
            "secondary": secondary,
            "dark": dark,
            "accent": accent,
            "shape": shape,
            "element": cls._detect_element(p),
        }

    @classmethod
    def _detect_shape(cls, p: str, asset_type: AssetType) -> str:
        """检测形状关键词，默认按 assetType 回退"""
        # 通用形状检测
        if any(k in p for k in ("史莱姆", "slime", "球")):
            return "slime"
        if any(k in p for k in ("剑", "刀", "sword", "blade")):
            return "sword"
        if any(k in p for k in ("药水", "药", "potion", "瓶")):
            return "potion"
        if any(k in p for k in ("宝箱", "chest", "箱")):
            return "chest"
        if any(k in p for k in ("盾", "shield")):
            return "shield"
        if any(k in p for k in ("草", "grass")):
            return "grass"
        if any(k in p for k in ("石", "stone", "砖", "岩")):
            return "stone"
        if any(k in p for k in ("水", "water", "河", "海")):
            return "water"
        if any(k in p for k in ("火球", "火焰", "fire", "flame")):
            return "fireball"
        if any(k in p for k in ("按钮", "button")):
            return "button"
        if any(k in p for k in ("面板", "panel", "框")):
            return "panel"
        if any(k in p for k in ("图标", "icon", "技能")):
            return "icon"
        # 默认按类型
        defaults = {
            AssetType.CHARACTER: "humanoid",
            AssetType.ENEMY: "slime",
            AssetType.ITEM: "potion",
            AssetType.TILE: "grass",
            AssetType.UI: "button",
            AssetType.UI_ICON: "icon",
        }
        return defaults.get(asset_type, "humanoid")

    @classmethod
    def _detect_element(cls, p: str) -> str:
        if any(k in p for k in ("火", "fire", "flame")): return "fire"
        if any(k in p for k in ("冰", "水", "ice", "water")): return "water"
        if any(k in p for k in ("草", "森", "grass", "forest")): return "grass"
        if any(k in p for k in ("雷", "电", "lightning")): return "lightning"
        if any(k in p for k in ("暗", "影", "dark")): return "dark"
        if any(k in p for k in ("光", "圣", "light")): return "light"
        if any(k in p for k in ("地", "土", "earth")): return "earth"
        if any(k in p for k in ("毒", "poison")): return "poison"
        return "neutral"

    @staticmethod
    def _lighten(c: tuple, f: float) -> tuple:
        return tuple(min(255, int(c[i] + (255 - c[i]) * (1 - f))) for i in range(3))

    @staticmethod
    def _darken(c: tuple, f: float) -> tuple:
        return tuple(max(0, int(c[i] * f)) for i in range(3))

    @staticmethod
    def _complement(c: tuple) -> tuple:
        return tuple(255 - c[i] for i in range(3))


# ================================================================
# 像素艺术渲染器
# ================================================================

class PixelArtRenderer:
    """
    像素艺术渲染：
      - 在低分辨率画布上绘制（target_size // pixel_scale）
      - 使用 NEAREST 放大，保证锯齿清晰
      - 限制调色板到 6-8 色
    """

    PIXEL_SCALE = 4  # 目标尺寸 64 → 像素画布 16×16

    def __init__(self, w: int, h: int, info: dict, seed: int):
        self.target_w = w
        self.target_h = h
        self.pw = max(8, w // self.PIXEL_SCALE)  # pixel canvas width
        self.ph = max(8, h // self.PIXEL_SCALE)
        self.info = info
        self.seed = seed

    def render(self, frame: int, total_frames: int, anim: AnimationType) -> Image.Image:
        """在低分辨率画布上绘制，然后 NEAREST 放大到目标尺寸。"""
        canvas = Image.new("RGBA", (self.pw, self.ph), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        shape = self.info["shape"]
        pc = self.info["primary"]
        sc = self.info["secondary"]
        dk = self.info["dark"]
        ac = self.info["accent"]

        # 动画偏移量
        bounce = self._bounce(frame, total_frames, anim)
        shift_x = self._shift_x(frame, total_frames, anim)

        method = getattr(self, f"px_{shape}", self.px_slime)
        method(draw, self.pw, self.ph, pc, sc, dk, ac, bounce, shift_x, frame, total_frames, anim)

        # NEAREST 放大
        return canvas.resize((self.target_w, self.target_h), Image.NEAREST)

    # ---- 动画计算 ----

    def _bounce(self, fi: int, total: int, anim: AnimationType) -> int:
        if anim == AnimationType.IDLE:
            return 1 if (fi % 2 == 0) else -1
        if anim == AnimationType.MOVE:
            return 1 if (fi % 2 == 0) else -1
        if anim == AnimationType.ATTACK:
            return -fi
        if anim == AnimationType.NONE:
            return 0
        return 0

    def _shift_x(self, fi: int, total: int, anim: AnimationType) -> int:
        if anim == AnimationType.MOVE:
            return 1 if (fi % 2 == 0) else -1
        return 0

    # ---- 形状绘制 (像素坐标) ----

    def px_slime(self, d, pw, ph, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """半圆形史莱姆，2 像素眼"""
        cx, cy = pw // 2 + sx, ph // 2 + bounce
        r = pw // 3
        # attack 帧 1: 身体变宽
        stretch = 1 if (anim == AnimationType.ATTACK and fi % 2 == 1) else 0
        body_top = max(1, cy - r)
        body_bot = min(ph - 1, cy + r + stretch)
        body_left = max(0, cx - r - stretch)
        body_right = min(pw - 1, cx + r + stretch)

        # 身体 — 桶形
        d.ellipse([body_left, body_top, body_right, body_bot], fill=pc)
        # 描边（手动用深色像素）
        self._pixel_outline_ellipse(d, body_left, body_top, body_right, body_bot, dk)

        # 高光
        hl_x, hl_y = cx - r // 2, body_top + 1
        d.ellipse([hl_x, hl_y, hl_x + r // 2, hl_y + r // 2], fill=sc)

        # 眼（白底+黑瞳），第 2 帧眨眼
        eye_r = max(1, pw // 12)
        blinking = (fi % 4 == 2 and anim == AnimationType.IDLE)
        for ex in [cx - pw // 6, cx + pw // 6]:
            eye_y = body_top + r // 2
            if blinking:
                # 眨眼：画一条线代替眼珠
                d.line([(ex - eye_r, eye_y), (ex + eye_r, eye_y)], fill=(0, 0, 0))
            elif anim == AnimationType.NONE:
                d.ellipse([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r], fill=(255, 255, 255))
                d.point((ex, eye_y), fill=(0, 0, 0))
            else:
                d.ellipse([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r], fill=(255, 255, 255))
                d.point((ex, eye_y), fill=(0, 0, 0))

    def px_humanoid(self, d, pw, ph, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """像素小人：头+身体+四肢"""
        cx = pw // 2 + sx
        head_y = max(2, ph // 5 + bounce)
        head_r = max(2, pw // 6)

        # 头
        d.ellipse([cx - head_r, head_y - head_r, cx + head_r, head_y + head_r], fill=pc)
        self._pixel_outline_ellipse(d, cx - head_r, head_y - head_r, cx + head_r, head_y + head_r, dk)

        # 身体
        body_y = head_y + head_r + 1
        body_h = max(3, ph // 3)
        body_w = max(2, pw // 5)
        d.rectangle([cx - body_w, body_y, cx + body_w, body_y + body_h], fill=sc)
        d.rectangle([cx - body_w, body_y, cx + body_w, body_y + body_h], outline=dk)

        # 腿
        leg_w = max(1, pw // 10)
        leg_top = body_y + body_h
        leg_shift = 1 if (anim == AnimationType.MOVE and fi % 2 == 0) else 0
        d.rectangle([cx - body_w + leg_shift, leg_top, cx - body_w + leg_w + leg_shift, ph - 1], fill=dk)
        d.rectangle([cx + body_w - leg_w - leg_shift, leg_top, cx + body_w - leg_shift, ph - 1], fill=dk)

        # 眼
        eye_r = max(1, head_r // 3)
        for ex in [cx - head_r // 2, cx + head_r // 2]:
            d.point((ex, head_y), fill=(0, 0, 0))

    def px_sword(self, d, pw, ph, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """像素剑：垂直刃+护手+握柄"""
        cx = pw // 2 + sx
        blade_top = max(1, ph // 8 + bounce)
        blade_bot = ph * 2 // 3 + bounce
        blade_w = max(1, pw // 10)

        # 剑刃
        d.rectangle([cx - blade_w, blade_top, cx + blade_w, blade_bot], fill=sc)
        d.rectangle([cx - blade_w, blade_top, cx + blade_w, blade_bot], outline=dk)
        # 中线
        d.line([(cx, blade_top + 1), (cx, blade_bot - 1)], fill=(255, 255, 255))

        # 护手
        guard_w = max(2, pw // 4)
        d.rectangle([cx - guard_w, blade_bot, cx + guard_w, blade_bot + 1], fill=dk)

        # 握柄
        grip_h = max(2, ph // 4)
        d.rectangle([cx - blade_w, blade_bot + 2, cx + blade_w, blade_bot + 2 + grip_h], fill=pc)
        d.rectangle([cx - blade_w, blade_bot + 2, cx + blade_w, blade_bot + 2 + grip_h], outline=dk)

        # 攻击光效
        if anim == AnimationType.ATTACK and fi % 2 == 0:
            glow_x = blade_top
            for gl_y in range(blade_top, blade_bot, 3):
                if 0 <= glow_x < pw and 0 <= gl_y < ph:
                    d.point((glow_x - 1, gl_y), fill=(255, 255, 200))
                    d.point((glow_x + blade_w + 2, gl_y), fill=(255, 255, 200))

    def px_potion(self, d, pw, ph, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """像素药水瓶"""
        cx = pw // 2 + sx
        r = max(3, pw // 4)
        bottle_top = max(1, ph // 3 + bounce)
        bottle_bot = min(ph - 1, bottle_top + r)

        # 瓶身
        d.rounded_rectangle([cx - r // 2, bottle_top, cx + r // 2, bottle_bot], radius=1, fill=pc)
        d.rounded_rectangle([cx - r // 2, bottle_top, cx + r // 2, bottle_bot], radius=1, outline=dk)

        # 瓶颈
        neck_h = r // 3
        neck_w = r // 4
        d.rectangle([cx - neck_w, bottle_top - neck_h, cx + neck_w, bottle_top], fill=sc, outline=dk)

        # 瓶塞
        d.rectangle([cx - neck_w - 1, bottle_top - neck_h - 1, cx + neck_w + 1, bottle_top - neck_h], fill=dk)

        # 高光
        d.point((cx - r // 4, bottle_top + 1), fill=(255, 255, 255))

    def px_chest(self, d, pw, ph, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """像素宝箱"""
        cx = pw // 2 + sx
        box_w, box_h = pw // 3, ph // 4
        box_y = ph // 2 + bounce

        # 箱体
        d.rectangle([cx - box_w, box_y, cx + box_w, box_y + box_h], fill=sc, outline=dk)
        # 箱盖
        lid_h = max(2, ph // 8)
        d.rectangle([cx - box_w - 1, box_y - lid_h, cx + box_w + 1, box_y], fill=pc, outline=dk)
        # 锁
        d.rectangle([cx - 1, box_y, cx + 1, box_y + lid_h], fill=ac)
        # 金属边框
        d.line([(cx - box_w, box_y + box_h // 2), (cx + box_w, box_y + box_h // 2)], fill=dk)

    def px_grass(self, d, pw, ph, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """像素草地瓦片"""
        d.rectangle([0, 0, pw - 1, ph - 1], fill=pc)
        # 草叶 - 随机但固定种子
        import random
        rng = random.Random(self.seed + fi)
        for _ in range(5):
            x = rng.randint(1, pw - 2)
            y = rng.randint(1, ph - 2)
            h = rng.randint(2, ph // 3)
            for dy in range(h):
                if y - dy >= 0:
                    d.point((x, y - dy), fill=sc)
                    if rng.random() > 0.5 and x + 1 < pw and y - dy >= 0:
                        d.point((x + 1, y - dy), fill=sc)

    def px_stone(self, d, pw, ph, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """像素石块瓦片"""
        d.rectangle([0, 0, pw - 1, ph - 1], fill=pc)
        import random
        rng = random.Random(self.seed + fi)
        # 石块砌合图案
        for row in range(0, ph, max(2, ph // 4)):
            offset = rng.randint(0, pw // 4) if row > 0 else 0
            for col in range(-pw // 4, pw, pw // 3):
                x1 = col + offset
                d.rectangle([x1, row, min(x1 + pw // 3, pw - 1), min(row + ph // 4, ph - 1)],
                           outline=dk)

    def px_water(self, d, pw, ph, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """像素水面瓦片"""
        d.rectangle([0, 0, pw - 1, ph - 1], fill=pc)
        import random
        rng = random.Random(self.seed)
        # 波纹
        for row in range(2, ph - 1, max(2, ph // 4)):
            offset = (fi * 2 + row) % 4 - 2
            for col in range(0, pw, 3):
                if 0 <= col + offset < pw:
                    d.point((col + offset, row), fill=sc)

    def px_fireball(self, d, pw, ph, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """像素火球"""
        cx = pw // 2 + sx
        cy = ph // 2 + bounce
        r = max(2, pw // 3)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=pc)
        # 内焰
        d.ellipse([cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2], fill=sc)
        # 核心
        d.ellipse([cx - r // 4, cy - r // 4, cx + r // 4, cy + r // 4], fill=ac)

    def px_button(self, d, pw, ph, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """像素按钮"""
        d.rounded_rectangle([1, 1, pw - 2, ph - 2], radius=1, fill=pc, outline=dk)
        # 高光
        hl_y = 2
        d.rectangle([pw // 4, hl_y, pw * 3 // 4, hl_y + 1], fill=sc)

    def px_panel(self, d, pw, ph, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """像素面板"""
        d.rectangle([0, 0, pw - 1, ph - 1], fill=pc, outline=dk)
        # 标题栏
        title_h = max(2, ph // 5)
        d.rectangle([0, 0, pw - 1, title_h], fill=dk)

    def px_icon(self, d, pw, ph, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """像素图标（圆形+十字）"""
        cx, cy = pw // 2, ph // 2 + bounce
        r = max(2, pw // 3)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=pc, outline=dk)
        d.line([(cx - r // 2, cy), (cx + r // 2, cy)], fill=(255, 255, 255))
        d.line([(cx, cy - r // 2), (cx, cy + r // 2)], fill=(255, 255, 255))

    # ---- 工具 ----

    def _pixel_outline_ellipse(self, d, x1, y1, x2, y2, color):
        """像素化椭圆描边：在椭圆四周画点模拟描边"""
        # 简化：用 draw ellipse outline 然后手动修正
        try:
            d.ellipse([x1, y1, x2, y2], outline=color)
        except Exception:
            pass


# ================================================================
# 扁平卡通渲染器
# ================================================================

class FlatCartoonRenderer:
    """
    扁平卡通风渲染：
      - 全分辨率绘制
      - 圆角、柔和阴影、明亮配色
      - 描边+高光
    """

    def __init__(self, w: int, h: int, info: dict, seed: int):
        self.w = w
        self.h = h
        self.info = info
        self.seed = seed

    def render(self, frame: int, total_frames: int, anim: AnimationType) -> Image.Image:
        canvas = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        shape = self.info["shape"]
        pc = self.info["primary"]
        sc = self.info["secondary"]
        dk = self.info["dark"]
        ac = self.info["accent"]

        bounce = self._bounce(frame, total_frames, anim)
        shift_x = self._shift_x(frame, total_frames, anim)

        method = getattr(self, f"fc_{shape}", self.fc_slime)
        method(draw, self.w, self.h, pc, sc, dk, ac, bounce, shift_x, frame, total_frames, anim)

        return canvas

    def _bounce(self, fi, total, anim):
        if anim == AnimationType.IDLE: return int(2 * (1 if fi % 2 == 0 else -1))
        if anim == AnimationType.MOVE: return int(3 * (1 if fi % 2 == 0 else -1))
        if anim == AnimationType.ATTACK:
            return [0, -3, 2][fi % 3] if total >= 3 else int(-2 * (1 if fi % 2 == 0 else -1))
        if anim == AnimationType.NONE: return 0
        return 0

    def _shift_x(self, fi, total, anim):
        if anim == AnimationType.MOVE: return int(2 * (1 if fi % 2 == 0 else -1))
        if anim == AnimationType.ATTACK: return int(2 * (1 if fi % 2 == 0 else -1))
        return 0

    def _shadow(self, d, bbox, offset=(2, 2)):
        x1, y1, x2, y2 = bbox
        sx1, sy1 = x1 + offset[0], y1 + offset[1]
        sx2, sy2 = x2 + offset[0], y2 + offset[1]
        d.ellipse([sx1, sy1, sx2, sy2], fill=(0, 0, 0, 60))

    # ---- 形状 ----

    def fc_slime(self, d, w, h, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """圆润史莱姆"""
        cx, cy = w // 2 + sx, h // 2 + bounce
        r = w // 3
        # attack 帧 1: 身体压扁拉伸
        stretch_x = 4 if (anim == AnimationType.ATTACK and fi % 2 == 1) else 0
        stretch_y = -2 if (anim == AnimationType.ATTACK and fi % 2 == 1) else 0
        body = [cx - r - stretch_x, cy - r // 2 + stretch_y,
                cx + r + stretch_x, cy + r * 3 // 2 - stretch_y]
        if self._bounce(fi, total, anim) != 0:
            self._shadow(d, body)
        d.ellipse(body, fill=pc, outline=dk, width=max(2, w // 20))
        # attack: 身体拉伸
        if anim == AnimationType.ATTACK and fi % 2 == 1:
            body = [cx - r - 2, cy - r // 2, cx + r + 2, cy + r * 3 // 2]
        # 高光
        d.ellipse([cx - r // 2, cy - r // 4, cx - r // 5, cy + r // 3], fill=(255, 255, 255, 100))
        # 眼，第 2 帧眨眼
        eye_r = max(2, w // 12)
        blinking = (fi % 4 == 2 and anim == AnimationType.IDLE)
        for ex in [cx - r // 2, cx + r // 2]:
            eye_y = cy - r // 3
            if blinking:
                d.line([(ex - eye_r, eye_y), (ex + eye_r, eye_y)], fill=dk, width=2)
            elif anim == AnimationType.NONE:
                d.ellipse([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r], fill=(255, 255, 255), outline=dk, width=1)
                p_r = max(1, eye_r // 2)
                d.ellipse([ex - p_r, eye_y - p_r, ex + p_r, eye_y + p_r], fill=dk)
            else:
                d.ellipse([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r], fill=(255, 255, 255), outline=dk, width=1)
                p_r = max(1, eye_r // 2)
                d.ellipse([ex - p_r, eye_y - p_r, ex + p_r, eye_y + p_r], fill=dk)

    def fc_humanoid(self, d, w, h, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """卡通小人"""
        cx, cy = w // 2 + sx, h // 2
        head_r = w // 6
        head_y = h // 5 + bounce

        # 身体（带阴影）
        body = [cx - head_r, head_y + head_r, cx + head_r, h * 3 // 5]
        d.rounded_rectangle(body, radius=head_r // 2, fill=sc, outline=dk, width=2)

        # 头
        d.ellipse([cx - head_r, head_y - head_r, cx + head_r, head_y + head_r],
                  fill=pc, outline=dk, width=2)

        # 眼
        eye_r = max(1, head_r // 3)
        for ex in [cx - head_r // 2, cx + head_r // 2]:
            d.ellipse([ex - eye_r, head_y - eye_r, ex + eye_r, head_y + eye_r],
                      fill=(255, 255, 255), outline=dk, width=1)
            d.point((ex, head_y), fill=dk)

        # 四肢
        limb_w = max(1, w // 16)
        arm_swing = 0
        if anim == AnimationType.MOVE:
            arm_swing = 3 if fi % 2 == 0 else -3
        d.line([(cx - head_r, head_y + head_r + 2), (cx - head_r * 2, h // 2 + arm_swing)],
               fill=pc, width=limb_w)
        d.line([(cx + head_r, head_y + head_r + 2), (cx + head_r * 2, h // 2 - arm_swing)],
               fill=pc, width=limb_w)

        leg_swing = -arm_swing
        d.line([(cx - head_r // 2, h * 3 // 5), (cx - head_r // 2 + leg_swing, h - 3)],
               fill=dk, width=limb_w)
        d.line([(cx + head_r // 2, h * 3 // 5), (cx + head_r // 2 - leg_swing, h - 3)],
               fill=dk, width=limb_w)

    def fc_sword(self, d, w, h, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """卡通剑"""
        cx, cy = w // 2 + sx, h // 2
        blade_t, blade_b = h // 10 + bounce, h * 3 // 5 + bounce
        blade_w = w // 14

        d.polygon([(cx - blade_w, blade_t), (cx + blade_w, blade_t),
                   (cx + blade_w // 2, blade_b), (cx - blade_w // 2, blade_b)],
                  fill=sc, outline=dk, width=2)
        # 中线
        d.line([(cx, blade_t + 2), (cx, blade_b - 2)], fill=(255, 255, 255, 120), width=1)

        # 护手
        guard_w = w // 4
        d.rounded_rectangle([cx - guard_w, blade_b, cx + guard_w, blade_b + w // 14],
                            radius=1, fill=dk)

        # 握柄
        grip_b = blade_b + h // 3
        d.rounded_rectangle([cx - w // 18, blade_b + w // 14, cx + w // 18, grip_b],
                            radius=1, fill=pc, outline=dk, width=1)

        # 剑柄宝石
        d.ellipse([cx - w // 12, grip_b, cx + w // 12, grip_b + w // 8], fill=ac, outline=dk, width=1)

        # 攻击闪光
        if anim == AnimationType.ATTACK and fi % 2 == 0:
            for i in range(3):
                gx = cx - blade_w - i * 3
                gy = blade_t + i * 6
                d.ellipse([gx - 1, gy - 1, gx + 1, gy + 1], fill=(255, 255, 200, 180))

    def fc_potion(self, d, w, h, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """卡通药水瓶"""
        cx = w // 2 + sx
        cy = h // 2 + bounce
        r = w // 3

        # 瓶身
        d.rounded_rectangle([cx - r, cy - r // 2, cx + r, cy + r],
                            radius=r // 3, fill=pc, outline=dk, width=2)
        # 瓶颈
        neck_h = r // 2
        d.rectangle([cx - r // 3, cy - r // 2 - neck_h, cx + r // 3, cy - r // 2],
                    fill=sc, outline=dk, width=1)
        # 瓶塞
        d.rounded_rectangle([cx - r // 3 - 1, cy - r // 2 - neck_h - r // 5,
                             cx + r // 3 + 1, cy - r // 2 - neck_h],
                            radius=1, fill=dk)
        # 高光
        d.ellipse([cx - r // 2, cy - r // 4, cx - r // 5, cy + r // 3],
                  fill=(255, 255, 255, 100))
        # 气泡
        import random
        rng = random.Random(self.seed + fi)
        for _ in range(2):
            bx = cx + rng.randint(-r // 2, r // 2)
            by = cy - r // 2 + rng.randint(0, r)
            br = rng.randint(1, r // 5)
            d.ellipse([bx, by, bx + br, by + br], fill=(255, 255, 255, 120))

    def fc_chest(self, d, w, h, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """卡通宝箱"""
        cx, cy = w // 2 + sx, h // 2 + bounce
        box_w, box_h = w // 3, h // 4

        # 箱体
        d.rounded_rectangle([cx - box_w, cy, cx + box_w, cy + box_h],
                            radius=w // 16, fill=sc, outline=dk, width=2)
        # 箱盖
        lid_h = h // 7
        d.rounded_rectangle([cx - box_w - 2, cy - lid_h, cx + box_w + 2, cy],
                            radius=w // 12, fill=pc, outline=dk, width=2)
        # 锁
        d.ellipse([cx - w // 14, cy - lid_h // 2, cx + w // 14, cy + lid_h // 2],
                  fill=ac, outline=dk, width=1)
        # 金属条
        d.line([(cx - box_w, cy + box_h // 2), (cx + box_w, cy + box_h // 2)], fill=dk, width=1)

    def fc_grass(self, d, w, h, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """卡通草地瓦片"""
        d.rectangle([0, 0, w, h], fill=pc)
        import random
        rng = random.Random(self.seed + fi)
        for _ in range(8):
            x = rng.randint(2, w - 2)
            bot = rng.randint(h // 3, h - 2)
            top = bot - rng.randint(3, h // 3)
            d.line([(x, bot), (x + rng.randint(-1, 1), top)], fill=sc, width=2)

    def fc_stone(self, d, w, h, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """卡通石块瓦片"""
        d.rectangle([0, 0, w, h], fill=pc)
        import random
        rng = random.Random(self.seed + fi)
        for row in range(0, h, h // 3):
            for col in range(0, w, w // 3):
                x1, y1 = col + 1, row + 1
                x2, y2 = col + w // 3 - 1, row + h // 3 - 1
                d.rounded_rectangle([x1, y1, x2, y2], radius=w // 16,
                                    fill=sc if (row + col) % 2 == 0 else pc,
                                    outline=dk, width=1)

    def fc_water(self, d, w, h, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """卡通水面瓦片"""
        d.rectangle([0, 0, w, h], fill=pc)
        for i in range(4):
            yy = h // 6 + i * h // 5
            offset = (fi * 3 + i * 5) % 8 - 4
            d.arc([w // 5, yy - h // 10 + offset, w * 4 // 5, yy + h // 10 + offset],
                  start=10, end=170, fill=sc, width=2)

    def fc_fireball(self, d, w, h, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """卡通火球"""
        cx, cy = w // 2 + sx, h // 2 + bounce
        r = w // 3
        # 外焰
        d.ellipse([cx - r, cy - r * 3 // 2, cx + r, cy + r * 3 // 2], fill=pc, outline=dk, width=2)
        # 内焰
        d.ellipse([cx - r // 2, cy - r, cx + r // 2, cy + r], fill=sc)
        # 核心
        d.ellipse([cx - r // 4, cy - r // 2, cx + r // 4, cy + r], fill=ac)

    def fc_button(self, d, w, h, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """卡通按钮"""
        d.rounded_rectangle([2, 2 + bounce, w - 2, h - 2 + bounce],
                            radius=w // 6, fill=pc, outline=dk, width=2)
        d.rounded_rectangle([w // 4, 4 + bounce, w * 3 // 4, h // 3 + bounce],
                            radius=w // 10, fill=(255, 255, 255, 100))

    def fc_panel(self, d, w, h, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """卡通面板"""
        d.rounded_rectangle([1, 1, w - 1, h - 1], radius=w // 12,
                            fill=(*pc, 220) if len(pc) == 3 else pc,
                            outline=dk, width=2)
        # 标题栏
        d.rectangle([w // 8, h // 7, w * 7 // 8, h // 4], fill=dk)

    def fc_icon(self, d, w, h, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """卡通图标"""
        cx, cy = w // 2, h // 2 + bounce
        r = w // 3
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=pc, outline=dk, width=2)
        d.line([(cx - r // 2, cy), (cx + r // 2, cy)], fill=(255, 255, 255), width=2)
        d.line([(cx, cy - r // 2), (cx, cy + r // 2)], fill=(255, 255, 255), width=2)

    def fc_shield(self, d, w, h, pc, sc, dk, ac, bounce, sx, fi, total, anim):
        """卡通盾牌"""
        cx, cy = w // 2 + sx, h // 2 + bounce
        r = w // 3
        pts = [(cx, h // 7), (cx + r, h // 4), (cx + r, cy),
               (cx, h * 5 // 6), (cx - r, cy), (cx - r, h // 4)]
        d.polygon(pts, fill=pc, outline=dk, width=2)
        cross_w = r // 3
        d.rectangle([cx - r // 3, cy - cross_w, cx + r // 3, cy + cross_w], fill=sc)
        d.rectangle([cx - cross_w, cy - r // 2, cx + cross_w, cy + r // 2], fill=sc)


# ================================================================
# MockGenerator — 主入口
# ================================================================

class MockGenerator(BaseGenerator):
    """
    统一的 Mock 生成器入口：
      - pixel_art → PixelArtRenderer
      - flat_cartoon → FlatCartoonRenderer
      - fantasy_painterly → FlatCartoonRenderer (暖色调变体)
      - sci_fi_ui → FlatCartoonRenderer (冷色调变体)
      - hand_drawn → FlatCartoonRenderer (加纹理)
    """

    def __init__(self, request):
        super().__init__(request)
        # 解析关键词
        self.parsed = KeywordParser.parse(request.prompt, request.assetType)
        # 选择渲染器
        self.renderer = self._pick_renderer()

    def _pick_renderer(self):
        w, h = self.req.width, self.req.height
        sid = self.req.styleId
        if sid == StyleId.PIXEL_ART:
            return PixelArtRenderer(w, h, self.parsed, self.seed)
        else:
            # flat_cartoon / fantasy_painterly / sci_fi_ui / hand_drawn
            return FlatCartoonRenderer(w, h, self.parsed, self.seed)

    def _draw(self, img: Image.Image, frame_index: int = 0) -> dict:
        """兼容 BaseGenerator 接口（单帧绘制到给定 img）。"""
        rendered = self.renderer.render(
            frame_index, self.req.frameCount, self.req.animation
        )
        img.paste(rendered, (0, 0))
        return {
            "tags": [self.parsed["shape"], self.parsed.get("element", "")],
            "generator": "mock",
            "frame": frame_index,
            "shape": self.parsed["shape"],
        }

    def generate_single(self, frame_index: int = 0) -> tuple[Image.Image, dict]:
        """生成单帧 — 直接调用渲染器。"""
        rendered = self.renderer.render(
            frame_index, self.req.frameCount, self.req.animation
        )
        meta = {
            "seed": self.seed,
            "width": self.req.width,
            "height": self.req.height,
            "style": self.req.styleId.value,
            "asset_type": self.req.assetType.value,
            "prompt": self.req.prompt,
            "animation": self.req.animation.value,
            "frame": frame_index,
            "shape": self.parsed["shape"],
            "element": self.parsed.get("element", ""),
            "pivot": [self.req.width // 2, self.req.height // 2],
        }
        return rendered, meta
