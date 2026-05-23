from __future__ import annotations
import os
import hashlib
import json
import uuid
import io
import random
import logging
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image
from app.config import OUTPUTS_DIR, settings
from app.models import (
    GenerateRequest, GenerateResponse, AssetInfo,
    BatchGenerateRequest, BatchGenerateResponse,
    JobStatus,
)
from app.generators.base_provider import BaseImageProvider
from app.services.spritesheet_service import SpriteSheetService

logger = logging.getLogger(__name__)


class AssetService:
    """Job-based 素材生成服务。每次生成对应一个 jobId，文件落地到 storage/outputs/{jobId}/"""

    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._cache: dict[str, str] = {}  # hash → jobId

    # ==================== 缓存工具 ====================

    @staticmethod
    def _build_cache_key(req: GenerateRequest) -> str:
        """为请求构建确定性缓存键。"""
        raw = "|".join([
            req.prompt.strip(),
            req.assetType.value,
            req.styleId.value,
            str(req.width),
            str(req.height),
            str(req.seed),
        ])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _resolve_seed(req: GenerateRequest) -> int:
        return req.seed if req.seed is not None else random.randint(0, 2**31 - 1)

    # ==================== 生成 ====================

    def generate(self, req: GenerateRequest) -> GenerateResponse:
        # —— 缓存检查 ——
        cache_key = self._build_cache_key(req)
        cached_job_id = self._cache.get(cache_key)
        if cached_job_id and cached_job_id in self._jobs:
            job = self._jobs[cached_job_id]
            logger.info("Cache HIT → %s", cached_job_id)
            return GenerateResponse(
                jobId=cached_job_id,
                status=job["status"],
                assets=job["assets"],
                spritesheetUrl=f"/outputs/{cached_job_id}/spritesheet.png",
                metadataUrl=f"/outputs/{cached_job_id}/metadata.json",
                cacheHit=True,
            )

        job_id = uuid.uuid4().hex[:12]
        job_dir = OUTPUTS_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # 保存请求快照
        req_path = job_dir / "request.json"
        req_path.write_text(req.model_dump_json(indent=2), encoding="utf-8")

        seed = self._resolve_seed(req)
        mode = os.getenv("IMAGE_PROVIDER_MODE", "mock").strip().lower()

        if mode == "mock":
            from app.generators.mock_generator import MockGenerator
            mock_gen = MockGenerator(req)
            img, meta = mock_gen.generate_single()

        elif mode == "http":
            from app.services.style_service import StyleService
            style_data = StyleService.get_style(req.styleId)
            ai_provider = self._create_ai_provider()
            img, meta = self._generate_one_ai(ai_provider, seed, style_data, req)

        else:
            raise RuntimeError(
                f"不支持的 IMAGE_PROVIDER_MODE: '{mode}'。"
                f"请设置为 'http'（调用 AI 图像 API）或 'mock'（程序化生成开发模式）。"
            )

        # 质量控制：确保 RGBA + 居中
        img = self._ensure_rgba(img)
        img = self._center_crop(img, req.width, req.height)

        frame_id = f"{job_id}_f0"
        fname = "frame_0.png"
        frame_path = job_dir / fname
        img.save(frame_path, format="PNG")

        meta_path = job_dir / "frame_0_meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        assets: list[AssetInfo] = []
        pil_images: list[Image.Image] = []

        assets.append(AssetInfo(
            id=frame_id,
            url=f"/outputs/{job_id}/{fname}",
            type="frame",
            width=req.width,
            height=req.height,
        ))
        pil_images.append(img)

        # Sprite Sheet — 横向排列（带间距）
        spritesheet_bytes, sheet_meta = SpriteSheetService.build_from_pil(
            pil_images, req.width, req.height
        )
        sheet_path = job_dir / "spritesheet.png"
        sheet_path.write_bytes(spritesheet_bytes)
        json_path = job_dir / "spritesheet.json"
        json_path.write_text(json.dumps(sheet_meta, ensure_ascii=False, indent=2), encoding="utf-8")

        # metadata.json
        metadata = {
            "jobId": job_id,
            "prompt": req.prompt,
            "assetType": req.assetType.value,
            "styleId": req.styleId.value,
            "frameWidth": req.width,
            "frameHeight": req.height,
            "spritesheet": "spritesheet.png",
            "frames": sheet_meta.get("frames", []),
            "exportTarget": req.exportTarget.value,
            "seed": seed,
            "cacheHit": False,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "compatibleWith": ["Unity", "Godot", "Aseprite"],
        }
        meta_json_path = job_dir / "metadata.json"
        meta_json_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        # 存储 job 记录
        self._jobs[job_id] = {
            "status": "completed",
            "req": req,
            "assets": assets,
            "seed": seed,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }

        # 写入缓存
        self._cache[cache_key] = job_id

        return GenerateResponse(
            jobId=job_id,
            status="completed",
            assets=assets,
            spritesheetUrl=f"/outputs/{job_id}/spritesheet.png",
            metadataUrl=f"/outputs/{job_id}/metadata.json",
            cacheHit=False,
        )

    # ==================== 批量生成 ====================

    def batch_generate(self, req: BatchGenerateRequest) -> BatchGenerateResponse:
        max_batch = settings.max_batch_size
        if len(req.prompts) > max_batch:
            return BatchGenerateResponse(
                jobIds=[],
                message=f"批量生成最多同时 {max_batch} 个 prompt，收到 {len(req.prompts)} 个",
            )
        job_ids: list[str] = []
        for prompt in req.prompts:
            greq = GenerateRequest(
                prompt=prompt,
                assetType=req.assetType,
                styleId=req.styleId,
                width=req.width,
                height=req.height,
                transparent=req.transparent,
                exportTarget=req.exportTarget,
            )
            resp = self.generate(greq)
            job_ids.append(resp.jobId)
        return BatchGenerateResponse(jobIds=job_ids, message=f"已创建 {len(job_ids)} 个生成任务")

    # ==================== 查询 ====================

    def get_job(self, job_id: str) -> JobStatus | None:
        job = self._jobs.get(job_id)
        if not job:
            return None

        req = job["req"]
        # 检查是否为缓存命中（通过 metadata 文件）
        cache_hit = False
        meta_path = OUTPUTS_DIR / job_id / "metadata.json"
        if meta_path.exists():
            try:
                m = json.loads(meta_path.read_text(encoding="utf-8"))
                cache_hit = m.get("cacheHit", False)
            except Exception:
                pass

        return JobStatus(
            jobId=job_id,
            status=job["status"],
            prompt=req.prompt,
            assetType=req.assetType,
            styleId=req.styleId,
            assets=job["assets"],
            spritesheetUrl=f"/outputs/{job_id}/spritesheet.png",
            metadataUrl=f"/outputs/{job_id}/metadata.json",
            createdAt=job.get("createdAt", ""),
            cacheHit=cache_hit,
        )

    # ==================== AI Provider 集成 ====================

    @staticmethod
    def _create_ai_provider() -> BaseImageProvider:
        mode = os.getenv("IMAGE_PROVIDER_MODE", "mock").strip().lower()
        if mode != "http":
            raise RuntimeError(
                f"IMAGE_PROVIDER_MODE 当前为 '{mode}'，不是 'http'，无法调用 AI 图像服务。"
            )
        try:
            from app.generators.http_image_provider import HttpImageProvider
            return HttpImageProvider()
        except RuntimeError as e:
            raise RuntimeError(f"AI 图像服务配置错误: {e}") from e

    @staticmethod
    def _generate_one_ai(
        provider: BaseImageProvider,
        seed: int,
        style_data: dict,
        req: GenerateRequest,
    ) -> tuple[Image.Image, dict]:
        """用 AI provider 生成单张图像并返回 metadata。"""
        prompt = f"{style_data.get('promptPrefix', '')}, {req.prompt}".strip(", ")
        negative = style_data.get("negativePrompt", "")

        img = provider.generate(
            prompt=prompt,
            negative_prompt=negative,
            width=req.width,
            height=req.height,
            seed=seed,
        )

        meta = {
            "seed": seed,
            "width": req.width,
            "height": req.height,
            "style": req.styleId.value,
            "asset_type": req.assetType.value,
            "prompt": req.prompt,
            "enhanced_prompt": prompt,
            "generator": "ai_http",
            "pivot": [req.width // 2, req.height // 2],
        }
        return img, meta

    # ==================== 质量控制 ====================

    @staticmethod
    def _ensure_rgba(img: Image.Image) -> Image.Image:
        """确保图像为 RGBA 模式，保留透明背景。"""
        if img.mode == "RGBA":
            return img
        if img.mode in ("RGB", "P", "L"):
            img = img.convert("RGBA")
        return img

    @staticmethod
    def _center_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
        """如果图像尺寸不匹配目标，居中裁剪到目标尺寸。"""
        iw, ih = img.size
        if (iw, ih) == (target_w, target_h):
            return img
        # 计算裁剪区域
        left = max(0, (iw - target_w) // 2)
        top = max(0, (ih - target_h) // 2)
        right = left + target_w
        bottom = top + target_h
        # 裁剪
        cropped = img.crop((left, top, right, bottom))
        # 如果裁剪后小于目标，贴到目标大小的透明画布上
        if cropped.size != (target_w, target_h):
            canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
            paste_x = max(0, (target_w - cropped.width) // 2)
            paste_y = max(0, (target_h - cropped.height) // 2)
            canvas.paste(cropped, (paste_x, paste_y))
            return canvas
        return cropped

    # ==================== ZIP 下载 ====================

    def build_zip(self, job_id: str) -> bytes | None:
        import zipfile
        job_dir = OUTPUTS_DIR / job_id
        if not job_dir.exists():
            return None

        buf = io.BytesIO()
        folder = f"asset_package_{job_id}"

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # --- 1. frames/ 目录 ---
            for fpath in sorted(job_dir.iterdir()):
                if fpath.name.startswith("frame_") and fpath.suffix == ".png":
                    zf.write(fpath, arcname=f"{folder}/frames/{fpath.name}")

            # --- 2. spritesheet.png ---
            sheet_path = job_dir / "spritesheet.png"
            if sheet_path.exists():
                zf.write(sheet_path, arcname=f"{folder}/spritesheet.png")

            # --- 3. metadata.json ---
            meta_path = job_dir / "metadata.json"
            if meta_path.exists():
                zf.write(meta_path, arcname=f"{folder}/metadata.json")

            # --- 4. prompt_history.json ---
            job = self._jobs.get(job_id, {})
            req = job.get("req")
            prompt_history = self._build_prompt_history(job_id, req, job)
            zf.writestr(f"{folder}/prompt_history.json",
                       json.dumps(prompt_history, ensure_ascii=False, indent=2).encode("utf-8"))

            # --- 5-7. 引擎导入指南 ---
            width = req.width if req else 32
            height = req.height if req else 32
            zf.writestr(f"{folder}/unity_import_guide.md", self._build_unity_guide(width, height).encode("utf-8"))
            zf.writestr(f"{folder}/godot_import_guide.md", self._build_godot_guide(width, height).encode("utf-8"))
            zf.writestr(f"{folder}/aseprite_import_guide.md", self._build_aseprite_guide(width, height).encode("utf-8"))

        return buf.getvalue()

    # ---------- 辅助文档生成 ----------

    def _build_prompt_history(self, job_id: str, req, job: dict) -> dict:
        """构建 prompt_history.json"""
        from app.services.style_service import StyleService
        style_data = StyleService.get_style(req.styleId) if req else {}
        return {
            "jobId": job_id,
            "originalPrompt": req.prompt if req else "",
            "enhancedPrompt": f"{style_data.get('promptPrefix', '')}, {req.prompt if req else ''}".strip(", "),
            "stylePreset": {
                "id": req.styleId.value if req else "",
                "name": style_data.get("name", ""),
                "promptPrefix": style_data.get("promptPrefix", ""),
                "negativePrompt": style_data.get("negativePrompt", ""),
            },
            "seed": job.get("seed"),
            "generationParameters": {
                "assetType": req.assetType.value if req else "",
                "width": req.width if req else 0,
                "height": req.height if req else 0,
                "exportTarget": req.exportTarget.value if req else "",
                "transparent": req.transparent if req else True,
            },
        }

    @staticmethod
    def _build_unity_guide(frame_w: int, frame_h: int) -> str:
        pad = settings.spritesheet_padding
        return f"""# Unity 导入指南

## 1. 导入 Sprite Sheet

1. 将 `spritesheet.png` 拖入 Unity 的 `Assets` 窗口。
2. 在 Inspector 中设置：
   - **Texture Type** = `Sprite (2D and UI)`
   - **Sprite Mode** = `Multiple`
   - **Pixels Per Unit** = `{frame_w}`
   - **Filter Mode** = `Point (no filter)` （像素风素材）
   - **Compression** = `None`
3. 点击 **Apply**。
4. 点击 **Sprite Editor** 打开切片工具。

## 2. 切片设置

1. 在 Sprite Editor 中，左上角选择 **Slice**。
2. 设置：
   - **Type** = `Grid By Cell Size`
   - **Pixel Size** = `{frame_w} x {frame_h}`
   - **Offset** = `{pad}` (帧间间距)
3. 点击 **Slice** → 右上角 **Apply**。
4. 现在 Project 窗口展开 spritesheet 即可看到每帧独立 Sprite。

## 3. 创建动画

1. 在 Hierarchy 中创建一个 `Sprite Renderer` 对象。
2. 打开 **Animation** 窗口（Window → Animation → Animation）。
3. 选中对象，点击 **Create** 创建 `.anim` 文件。
4. 将 spritesheet 展开的帧按顺序拖入 Animation 时间轴。
5. 调整帧速（Sample Rate 一般为 8~12）使动画流畅。
6. 可使用 **Animator Controller** 管理 idle / walk / attack 等状态切换。

## 4. Tilemap 使用

1. 如果是 tile 素材，在 Inspector 中设置 **Sprite Mode** = `Single`。
2. 在 Hierarchy 中创建 **2D Object → Tilemap → Rectangular**。
3. 打开 **Tile Palette** 窗口，将素材拖入创建 Tile。
4. 使用画笔工具在 Scene 中绘制地形。
"""

    @staticmethod
    def _build_godot_guide(frame_w: int, frame_h: int) -> str:
        pad = settings.spritesheet_padding
        return f"""# Godot 导入指南

## 1. 导入 PNG 素材

1. 将项目 ZIP 解压，复制 `frames/` 和 `spritesheet.png` 到 Godot 项目目录。
2. Godot 会自动导入 PNG，在 FileSystem 面板可见。
3. 选中图片，在 **Import** 选项卡设置：
   - **Preset** = `2D Texture`
   - **Filter** = `false` （像素风素材，关闭过滤可保持清晰边缘）

## 2. 使用 Sprite2D（单帧）

```gdscript
# 在场景中创建 Sprite2D 节点
var sprite = Sprite2D.new()
sprite.texture = load("res://frames/frame_0.png")
add_child(sprite)
```

## 3. 使用 AnimatedSprite2D（多帧动画）

1. 创建 **AnimatedSprite2D** 节点。
2. 在 Inspector 中创建 **SpriteFrames** 资源。
3. 在底部 Animation 面板中：
   - 点击「添加动画」创建 `idle` / `walk` / `attack` 等动画
   - 将各帧 PNG 拖入对应动画轨道
   - 设置帧速 FPS = 8~12
4. 设置 **Animation** 属性为默认播放的动画名（如 `idle`）。
5. 在脚本中切换动画：
```gdscript
$AnimatedSprite2D.play("walk")
```

## 4. TileSet 使用（瓦片素材）

1. 创建 **TileMap** 节点。
2. 在 Inspector 中创建 **TileSet** 资源。
3. 点击 **TileSet** → **Add Source** → 选择单个 tile 图片。
4. 在 TileSet 底部面板中设置碰撞形状（可选）。
5. 选择 TileMap 节点，在 2D 视图中使用画笔绘制地形。
6. 可将多个 tile 添加到同一个 TileSet 中，通过 Atlas 管理。

## 5. Sprite Sheet 切片

Spritesheet 帧间有 {pad}px 透明间距。在 Godot 中可按固定尺寸切片：
- Tile Width: `{frame_w}`
- Tile Height: `{frame_h}`
- Offset X: `{pad}`
"""

    @staticmethod
    def _build_aseprite_guide(frame_w: int, frame_h: int) -> str:
        pad = settings.spritesheet_padding
        return f"""# Aseprite 导入指南

## 1. 打开 Sprite Sheet

1. 打开 Aseprite。
2. **File → Open** 选择 `spritesheet.png`。
3. 弹出导入对话框时，设置 `Sprite Sheet` 模式。

## 2. 根据 Metadata 切帧

打开 `metadata.json` 查看帧信息：

- `frameWidth`: {frame_w}px
- `frameHeight`: {frame_h}px
- `padding`: {pad}px （帧间间距）
- `frames[]`: 每帧的 x, y, w, h 坐标

在 Aseprite 中手动切帧：

1. **File → Import Sprite Sheet...**
2. 设置：
   - **X**: {pad}, **Y**: {pad}
   - **Width**: {frame_w}, **Height**: {frame_h}
   - 勾选 **Import all frames**
3. 点击 **OK**，Aseprite 会自动按网格排列每帧到独立 cel。

## 3. 验证动画

1. 按 **Enter** 播放动画预览。
2. 在 Timeline 面板调整每帧持续时间 `duration`（参考 metadata.json）。
3. 使用 **File → Export** 导出优化后的 spritesheet 或 GIF。

## 4. 提示

- 可在 Aseprite 中进一步编辑像素、添加细节。
- 素材生成为透明背景 RGBA PNG，Aseprite 完美支持。
- Frame 标签可用于组织 idle / walk / attack 动画组。
"""
