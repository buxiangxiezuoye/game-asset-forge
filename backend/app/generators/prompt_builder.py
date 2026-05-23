from __future__ import annotations
from app.models import AssetType, StyleId, GenerateRequest, AnimationType, ExportTarget


class PromptBuilder:
    """根据用户输入构建生成参数。解析中文关键词，提取 asset_type、style 等。"""

    KEYWORD_MAP = {
        AssetType.CHARACTER: [
            "角色", "人物", "战士", "法师", "弓箭手", "骑士", "盗贼", "牧师",
            "村民", "商人", "英雄", "主角", "NPC", "玩家", "character", "player",
        ],
        AssetType.ENEMY: [
            "敌人", "怪物", "史莱姆", "骷髅", "僵尸", "幽灵", "龙", "boss",
            "小怪", "恶魔", "鬼", "enemy", "monster", "slime", "dragon",
        ],
        AssetType.ITEM: [
            "道具", "物品", "剑", "刀", "盾", "药水", "戒指", "宝石",
            "卷轴", "食物", "苹果", "宝箱", "钥匙", "弓", "箭", "sword", "potion", "item",
        ],
        AssetType.TILE: [
            "瓦片", "地形", "草地", "土地", "水", "沙", "石头", "墙壁",
            "地板", "砖", "tile", "grass", "water", "stone", "ground", "floor",
        ],
        AssetType.UI: [
            "UI", "按钮", "面板", "图标", "血条", "技能", "背包", "界面",
            "菜单", "边框", "button", "panel", "icon", "ui",
        ],
    }

    @classmethod
    def infer_asset_type(cls, prompt: str) -> AssetType:
        p = prompt.lower()
        for atype, keywords in cls.KEYWORD_MAP.items():
            for kw in keywords:
                if kw.lower() in p:
                    return atype
        return AssetType.CHARACTER

    @classmethod
    def build_request(
        cls,
        prompt: str,
        asset_type: AssetType | None = None,
        style_id: StyleId = StyleId.FLAT_CARTOON,
        width: int = 32,
        height: int = 32,
        frame_count: int = 1,
        animation: AnimationType = AnimationType.IDLE,
        transparent: bool = True,
        seed: int | None = None,
        export_target: ExportTarget = ExportTarget.GENERIC,
    ) -> GenerateRequest:
        if asset_type is None:
            asset_type = cls.infer_asset_type(prompt)

        return GenerateRequest(
            prompt=prompt,
            assetType=asset_type,
            styleId=style_id,
            width=width,
            height=height,
            frameCount=frame_count,
            animation=animation,
            transparent=transparent,
            seed=seed,
            exportTarget=export_target,
        )
