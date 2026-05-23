from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ==================== 校验常量 ====================

ALLOWED_SIZES = frozenset({16, 32, 64, 128, 256})
VALID_ASSET_TYPES = frozenset({"character", "enemy", "item", "tile", "ui", "ui_icon"})
VALID_STYLE_IDS = frozenset({"pixel_art", "flat_cartoon"})


# ==================== Enums ====================

class AssetType(str, Enum):
    CHARACTER = "character"
    ENEMY = "enemy"
    ITEM = "item"
    TILE = "tile"
    UI = "ui"
    UI_ICON = "ui_icon"


class StyleId(str, Enum):
    PIXEL_ART = "pixel_art"
    FLAT_CARTOON = "flat_cartoon"


class ExportTarget(str, Enum):
    GENERIC = "generic"
    UNITY = "unity"
    GODOT = "godot"


class AnimationType(str, Enum):
    """Internal enum for procedural renderers — not exposed in the API."""
    IDLE = "idle"
    MOVE = "move"
    ATTACK = "attack"
    NONE = "none"


# ==================== Style ====================

class StyleInfo(BaseModel):
    id: StyleId
    name: str
    description: str
    promptPrefix: str = ""
    negativePrompt: str = ""
    defaultPalette: list[str] = Field(default_factory=list)
    recommendedSizes: list[int] = Field(default_factory=lambda: [16, 32, 48, 64, 128])


# ==================== Generate ====================

class GenerateRequest(BaseModel):
    prompt: str = Field(
        min_length=1,
        max_length=300,
        description="中文描述，如 '一只蓝色史莱姆'",
    )
    assetType: AssetType = Field(default=AssetType.ENEMY)
    styleId: StyleId = Field(default=StyleId.PIXEL_ART)
    width: int = Field(default=64, ge=16, le=256)
    height: int = Field(default=64, ge=16, le=256)
    transparent: bool = Field(default=True)
    seed: Optional[int] = Field(default=None)
    exportTarget: ExportTarget = Field(default=ExportTarget.GENERIC)

    @field_validator("width")
    @classmethod
    def width_must_be_allowed(cls, v: int) -> int:
        if v not in ALLOWED_SIZES:
            raise ValueError(f"width 必须是 {sorted(ALLOWED_SIZES)} 之一，收到 {v}")
        return v

    @field_validator("height")
    @classmethod
    def height_must_be_allowed(cls, v: int) -> int:
        if v not in ALLOWED_SIZES:
            raise ValueError(f"height 必须是 {sorted(ALLOWED_SIZES)} 之一，收到 {v}")
        return v


class AssetInfo(BaseModel):
    id: str
    url: str
    type: str = "frame"
    width: int
    height: int


class GenerateResponse(BaseModel):
    jobId: str
    status: str
    assets: list[AssetInfo] = Field(default_factory=list)
    spritesheetUrl: str = ""
    metadataUrl: str = ""
    cacheHit: bool = False


# ==================== Batch ====================

class BatchGenerateRequest(BaseModel):
    prompts: list[str]
    assetType: AssetType = Field(default=AssetType.ENEMY)
    styleId: StyleId = Field(default=StyleId.PIXEL_ART)
    width: int = Field(default=32)
    height: int = Field(default=32)
    transparent: bool = Field(default=True)
    exportTarget: ExportTarget = Field(default=ExportTarget.GENERIC)

    @field_validator("prompts")
    @classmethod
    def prompts_not_empty_and_limited(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("prompts 不能为空列表")
        for p in v:
            if not p or not p.strip():
                raise ValueError("每个 prompt 不能为空")
        return v


class BatchGenerateResponse(BaseModel):
    jobIds: list[str]
    message: str


# ==================== Job ====================

class JobStatus(BaseModel):
    jobId: str
    status: str
    prompt: str
    assetType: AssetType
    styleId: StyleId
    assets: list[AssetInfo] = Field(default_factory=list)
    spritesheetUrl: str = ""
    metadataUrl: str = ""
    createdAt: str = ""
    error: str = ""
    cacheHit: bool = False
