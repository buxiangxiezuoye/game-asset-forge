from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


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
    FANTASY_PAINTERLY = "fantasy_painterly"
    SCI_FI_UI = "sci_fi_ui"
    HAND_DRAWN = "hand_drawn"


class AnimationType(str, Enum):
    IDLE = "idle"
    MOVE = "move"
    ATTACK = "attack"
    NONE = "none"


class ExportTarget(str, Enum):
    GENERIC = "generic"
    UNITY = "unity"
    GODOT = "godot"


class AssetFrameType(str, Enum):
    FRAME = "frame"
    SPRITESHEET = "spritesheet"


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
    prompt: str = Field(description="中文描述，如 '一只蓝色史莱姆'")
    assetType: AssetType = Field(default=AssetType.ENEMY)
    styleId: StyleId = Field(default=StyleId.PIXEL_ART)
    width: int = Field(default=32, ge=16, le=256)
    height: int = Field(default=32, ge=16, le=256)
    frameCount: int = Field(default=1, ge=1, le=16, description="动画帧数")
    animation: AnimationType = Field(default=AnimationType.IDLE)
    transparent: bool = Field(default=True)
    seed: Optional[int] = Field(default=None)
    exportTarget: ExportTarget = Field(default=ExportTarget.GENERIC)


class AssetInfo(BaseModel):
    id: str
    url: str
    type: AssetFrameType = AssetFrameType.FRAME
    width: int
    height: int


class GenerateResponse(BaseModel):
    jobId: str
    status: str  # "completed" | "failed"
    assets: list[AssetInfo] = Field(default_factory=list)
    spritesheetUrl: str = ""
    metadataUrl: str = ""


# ==================== Batch ====================

class BatchGenerateRequest(BaseModel):
    prompts: list[str]
    assetType: AssetType = Field(default=AssetType.ENEMY)
    styleId: StyleId = Field(default=StyleId.PIXEL_ART)
    width: int = Field(default=32)
    height: int = Field(default=32)
    frameCount: int = Field(default=1)
    animation: AnimationType = Field(default=AnimationType.IDLE)
    transparent: bool = Field(default=True)
    exportTarget: ExportTarget = Field(default=ExportTarget.GENERIC)


class BatchGenerateResponse(BaseModel):
    jobIds: list[str]
    message: str


# ==================== Job ====================

class JobStatus(BaseModel):
    jobId: str
    status: str  # "completed" | "failed" | "processing"
    prompt: str
    assetType: AssetType
    styleId: StyleId
    assets: list[AssetInfo] = Field(default_factory=list)
    spritesheetUrl: str = ""
    metadataUrl: str = ""
    createdAt: str = ""
    error: str = ""
