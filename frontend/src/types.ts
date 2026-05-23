export type AssetType = "character" | "enemy" | "item" | "tile" | "ui" | "ui_icon";
export type StyleId = "pixel_art" | "flat_cartoon";
export type ExportTarget = "unity" | "godot" | "generic";

export interface StyleInfo {
  id: StyleId;
  name: string;
  description: string;
  promptPrefix: string;
  negativePrompt: string;
  defaultPalette: string[];
  recommendedSizes: number[];
}

export interface GenerateRequest {
  prompt: string;
  assetType: AssetType;
  styleId: StyleId;
  width: number;
  height: number;
  transparent: boolean;
  seed?: number | null;
  exportTarget: ExportTarget;
}

export interface AssetInfo {
  id: string;
  url: string;
  type: "frame" | "spritesheet";
  width: number;
  height: number;
}

export interface FrameMeta {
  filename: string;
  x: number;
  y: number;
  w: number;
  h: number;
  duration: number;
}

export interface GenerateResponse {
  jobId: string;
  status: string;
  assets: AssetInfo[];
  spritesheetUrl: string;
  metadataUrl: string;
  cacheHit: boolean;
}

export interface JobStatus {
  jobId: string;
  status: string;
  prompt: string;
  assetType: AssetType;
  styleId: StyleId;
  assets: AssetInfo[];
  spritesheetUrl: string;
  metadataUrl: string;
  createdAt: string;
  error: string;
  cacheHit: boolean;
}

export interface BatchGenerateRequest {
  prompts: string[];
  assetType: AssetType;
  styleId: StyleId;
  width: number;
  height: number;
  transparent: boolean;
  exportTarget: ExportTarget;
}

export interface BatchGenerateResponse {
  jobIds: string[];
  message: string;
}

export const ASSET_TYPE_LABELS: Record<AssetType, string> = {
  character: "角色",
  enemy: "敌人",
  item: "道具",
  tile: "瓦片",
  ui: "UI",
  ui_icon: "图标",
};

export const STYLE_LABELS: Record<StyleId, string> = {
  pixel_art: "像素艺术",
  flat_cartoon: "扁平卡通",
};

export const EXPORT_LABELS: Record<ExportTarget, string> = {
  unity: "Unity",
  godot: "Godot",
  generic: "通用",
};
