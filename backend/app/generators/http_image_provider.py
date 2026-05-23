"""
通用 HTTP AI 图像生成 Provider — 不绑定任何特定厂商。

环境变量（不硬编码任何密钥）:
  IMAGE_PROVIDER_MODE     = mock | http              (默认 mock)
  IMAGE_PROVIDER_ENDPOINT = http://host:port/path     (必填)
  IMAGE_PROVIDER_API_KEY  = sk-... / ""               (可选)
  IMAGE_PROVIDER_BACKEND  = auto | sd_webui | comfyui | openai | generic
  IMAGE_PROVIDER_TIMEOUT  = 120                        (秒)

支持的 AI 后端（auto 自动检测）:
  - Stable Diffusion WebUI  (/sdapi/v1/txt2img)
  - ComfyUI                 (/prompt → 轮询 history)
  - OpenAI / SiliconFlow    (/v1/images/generations)
  - 通用 HTTP               (JSON POST → 解析响应)

  ★ 小尺寸素材自动处理：若请求 16~128px，自动升至 AI 模型支持的最小尺寸生成，
    然后 NEAREST/LANCZOS 缩放到目标尺寸。256px 以上直出。

响应格式自动识别:
  - {"images": ["base64..."]}          → base64 解码
  - {"images": [{"url": "https://"}]}  → HTTP 下载
  - {"data": [{"b64_json": "..."}]}   → OpenAI 风格
  - {"data": [{"url": "https://..."}]}→ OpenAI URL
  - {"filename": "/out/xxx.png"}       → 本地文件路径
"""
from __future__ import annotations
import os
import json
import base64
import io
import time
import logging
from pathlib import Path
from PIL import Image
import requests

from app.generators.base_provider import BaseImageProvider

logger = logging.getLogger(__name__)

# 各模型的最小支持尺寸（像素）。未列出的模型默认 256。
_MODEL_MIN_SIZES: dict[str, int] = {
    "Tongyi-MAI/Z-Image-Turbo": 256,
    "Tongyi-MAI/Z-Image": 256,
    "baidu/ERNIE-Image-Turbo": 256,
    "Kwai-Kolors/Kolors": 256,
    "Qwen/Qwen-Image": 256,
    "black-forest-labs/flux-schnell": 256,
    "black-forest-labs/flux-dev": 256,
}
# 可用尺寸（SD WebUI / ComfyUI 不限制，云端 API 通常只支持这些）
_VALID_SIZES = [256, 512, 768, 1024, 1280, 1536, 1792, 2048]


def _best_model_size(target: int) -> int:
    """找到 ≥ target 的最小可用尺寸。"""
    for s in _VALID_SIZES:
        if s >= target:
            return s
    return _VALID_SIZES[-1]


class HttpImageProvider(BaseImageProvider):
    """泛用 HTTP AI 图像生成 Provider — 自动适配多种后端 + 智能缩放。"""

    def __init__(self):
        self.endpoint: str = os.getenv("IMAGE_PROVIDER_ENDPOINT", "").strip()
        self.api_key: str = os.getenv("IMAGE_PROVIDER_API_KEY", "").strip()
        self.model: str = os.getenv("IMAGE_PROVIDER_MODEL", "").strip()
        self.timeout: int = int(os.getenv("IMAGE_PROVIDER_TIMEOUT", "120"))
        explicit = os.getenv("IMAGE_PROVIDER_BACKEND", "auto").strip().lower()
        self.backend: str = explicit if explicit != "auto" else self._detect_backend()

        # 回退模型链：优先用主模型，失败后依次尝试回退模型
        fallback_raw = os.getenv("IMAGE_PROVIDER_FALLBACK_MODELS", "").strip()
        self._model_chain: list[str] = []
        if self.model:
            self._model_chain.append(self.model)
        if fallback_raw:
            self._model_chain += [m.strip() for m in fallback_raw.split(",") if m.strip() and m.strip() != self.model]

        if not self.endpoint:
            raise RuntimeError("IMAGE_PROVIDER_ENDPOINT 未设置，无法初始化 HTTP Provider")
        endpoint_display = self.endpoint
        if self.api_key:
            endpoint_display += " (with API key)"
        logger.info("HttpImageProvider 初始化: backend=%s endpoint=%s models=%s",
                     self.backend, endpoint_display, self._model_chain)

    # ==================================================================
    # generate — 统一入口
    # ==================================================================

    def generate(
        self,
        *,
        prompt: str,
        negative_prompt: str = "",
        width: int = 64,
        height: int = 64,
        seed: int = 0,
    ) -> Image.Image:
        logger.info("HTTP Provider [%s] → prompt=%.80s...  %dx%d  seed=%d",
                     self.backend, prompt, width, height, seed)

        last_error: Exception | None = None
        models_to_try = self._model_chain if self._model_chain else [self.model or ""]

        for model_id in models_to_try:
            self.model = model_id
            try:
                return self._generate_once(prompt, negative_prompt, width, height, seed)
            except Exception as exc:
                logger.warning("模型 %s 调用失败: %s，尝试下一个...", model_id, exc)
                last_error = exc

        raise RuntimeError(
            f"所有模型均调用失败 (共 {len(models_to_try)} 个): {last_error}"
        )

    def _generate_once(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        seed: int,
    ) -> Image.Image:
        # 确定生成尺寸：小素材放大到模型支持的最小尺寸
        gen_w, gen_h = self._generation_size(width, height)
        needs_resize = (gen_w != width or gen_h != height)
        if needs_resize:
            logger.info("  → 升档生成 %dx%d (目标 %dx%d)", gen_w, gen_h, width, height)

        payload = self._build_payload(prompt, negative_prompt, gen_w, gen_h, seed)
        headers = self._build_headers()
        data = self._post(payload, headers)
        image = self._extract_image(data)

        if image.mode != "RGBA":
            image = image.convert("RGBA")

        # 缩放到目标尺寸
        if needs_resize:
            # 像素风用 NEAREST，其他用 LANCZOS
            method = Image.NEAREST if width <= 64 else Image.LANCZOS
            image = image.resize((width, height), method)
            logger.info("  → 缩放完成 %dx%d (%s)", width, height,
                       "NEAREST" if method == Image.NEAREST else "LANCZOS")

        return image

    def _generation_size(self, target_w: int, target_h: int) -> tuple[int, int]:
        """根据后端类型和目标尺寸确定生成尺寸。"""
        # SD WebUI / ComfyUI：本地模型，直接按目标生成
        if self.backend in ("sd_webui", "comfyui"):
            return target_w, target_h

        # 云端 API：找到模型支持的最小尺寸
        min_size = _MODEL_MIN_SIZES.get(self.model, 256)
        w = _best_model_size(max(target_w, min_size))
        h = _best_model_size(max(target_h, min_size))
        return w, h

    # ==================================================================
    # 后端检测
    # ==================================================================

    @staticmethod
    def _detect_backend() -> str:
        ep = os.getenv("IMAGE_PROVIDER_ENDPOINT", "").lower()
        if not ep:
            return "generic"
        if "/sdapi/" in ep or ":7860" in ep or "txt2img" in ep:
            return "sd_webui"
        if "/prompt" in ep or "comfy" in ep or ":8188" in ep:
            return "comfyui"
        if "/v1/images/generations" in ep or "openai" in ep or "siliconflow" in ep:
            return "openai"
        return "generic"

    # ==================================================================
    # 构建请求
    # ==================================================================

    def _build_payload(
        self, prompt: str, negative: str, width: int, height: int, seed: int
    ) -> dict:
        if self.backend == "sd_webui":
            return {
                "prompt": prompt,
                "negative_prompt": negative or "",
                "width": width,
                "height": height,
                "seed": seed,
                "steps": int(os.getenv("IMAGE_PROVIDER_STEPS", "20")),
                "cfg_scale": float(os.getenv("IMAGE_PROVIDER_CFG", "7.0")),
                "sampler_name": os.getenv("IMAGE_PROVIDER_SAMPLER", "Euler a"),
            }

        if self.backend == "comfyui":
            return {
                "prompt": self._build_comfy_workflow(prompt, negative, width, height, seed),
                "client_id": f"gameassetforge_{int(time.time())}",
            }

        # openai / generic: 都用 OpenAI 兼容格式
        p: dict = {
            "model": self.model or "dall-e-3",
            "prompt": prompt,
            "size": f"{width}x{height}",
            "n": 1,
            "response_format": "b64_json",
        }
        if seed:
            p["seed"] = seed
        return p

    def _build_headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    # ==================================================================
    # ComfyUI workflow
    # ==================================================================

    @staticmethod
    def _build_comfy_workflow(
        prompt: str, negative: str, width: int, height: int, seed: int
    ) -> dict:
        """构建最小 txt2img ComfyUI workflow。"""
        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": int(os.getenv("IMAGE_PROVIDER_STEPS", "20")),
                    "cfg": float(os.getenv("IMAGE_PROVIDER_CFG", "7.0")),
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": os.getenv("IMAGE_PROVIDER_MODEL", "sd_xl_base_1.0.safetensors")},
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": width, "height": height, "batch_size": 1},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["4", 1]},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": negative, "clip": ["4", 1]},
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "gameassetforge", "images": ["8", 0]},
            },
        }

    # ==================================================================
    # HTTP 发送
    # ==================================================================

    def _post(self, payload: dict, headers: dict) -> dict:
        """发送 POST + 获取最终图像数据。ComfyUI 需要两阶段（提交 + 轮询）。"""
        try:
            resp = requests.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"HTTP [{self.backend}] 请求失败: {exc}")

        # 检查 API 业务错误
        if isinstance(data, dict) and data.get("code") and data.get("code") != 0:
            raise RuntimeError(f"[{self.backend}] API 错误 code={data['code']}: {data.get('message', 'unknown')}")

        if self.backend == "comfyui":
            data = self._comfy_poll(data, headers)

        return data

    def _comfy_poll(self, submit_data: dict, headers: dict) -> dict:
        """ComfyUI: 提交 /prompt → 轮询 /history/{prompt_id} → 拿到图片数据。"""
        prompt_id = submit_data.get("prompt_id")
        if not prompt_id:
            raise RuntimeError("ComfyUI prompt 提交未返回 prompt_id")

        base = self.endpoint.rstrip("/")
        if base.endswith("/prompt"):
            base = base[: -len("/prompt")]

        history_url = f"{base}/history/{prompt_id}"
        started = time.time()
        while time.time() - started < self.timeout:
            try:
                r = requests.get(history_url, headers=headers, timeout=30)
                r.raise_for_status()
                hist = r.json()
            except requests.RequestException:
                time.sleep(1)
                continue

            entry = hist.get(prompt_id)
            if entry and entry.get("outputs"):
                return self._comfy_extract_images(entry["outputs"])
            time.sleep(1)

        raise RuntimeError(f"ComfyUI 超时: {self.timeout}s 内未完成生成")

    @staticmethod
    def _comfy_extract_images(outputs: dict) -> dict:
        """从 ComfyUI outputs 中提取 {images: [...]} 格式。"""
        images = []
        for node_id, node_output in outputs.items():
            imgs = node_output.get("images", [])
            for img_info in imgs:
                filename = img_info.get("filename", "")
                subfolder = img_info.get("subfolder", "")
                folder_type = img_info.get("type", "output")

                comfy_root = os.getenv("COMFYUI_OUTPUT_DIR", "")
                if comfy_root and filename:
                    full = Path(comfy_root) / folder_type / subfolder / filename
                    if full.exists():
                        images.append({"filename": str(full)})
                        continue

                if filename:
                    full = Path(".") / ".." / folder_type / subfolder / filename
                    if full.exists():
                        images.append({"filename": str(full.resolve())})
                        continue

                if filename:
                    logger.warning(
                        "ComfyUI 生成了 %s，但无法定位。设置 COMFYUI_OUTPUT_DIR 环境变量。",
                        filename,
                    )
        return {"images": images} if images else {"images": []}

    # ==================================================================
    # 图像提取
    # ==================================================================

    def _extract_image(self, data: dict) -> Image.Image:
        """从响应中提取图像 — 支持多种格式。"""
        image = self._try_parse(data)
        if image is None:
            raise RuntimeError(
                f"[{self.backend}] 无法解析响应。keys={list(data.keys())} 数据前 200 字符: {json.dumps(data, ensure_ascii=False)[:200]}"
            )
        return image

    def _try_parse(self, data: dict) -> Image.Image | None:
        """逐格式尝试解析。"""

        # --- Format A: {"images": [...]} ---
        if "images" in data and isinstance(data["images"], list) and data["images"]:
            first = data["images"][0]
            if isinstance(first, dict):
                if "url" in first:
                    return self._download(first["url"])
                if "filename" in first:
                    return self._load_file(first["filename"])
            if isinstance(first, str):
                img = self._decode_b64(first)
                if img:
                    return img
                return self._load_file(first)

        # --- Format B: {"data": [{"b64_json": "..."}]} / {"data": [{"url": "..."}]}  ---
        if "data" in data and isinstance(data["data"], list) and data["data"] is not None and len(data["data"]) > 0:
            item = data["data"][0]
            if isinstance(item, dict):
                if "b64_json" in item:
                    return self._decode_b64(item["b64_json"])
                if "url" in item:
                    return self._download(item["url"])

        # --- Format C: {"url": "https://..."}  ---
        if "url" in data and isinstance(data["url"], str):
            return self._download(data["url"])

        # --- Format D: {"image": "base64..."}  ---
        if "image" in data and isinstance(data["image"], str):
            return self._decode_b64(data["image"])

        # --- Format E: {"filename": "/path/to/file.png"}  ---
        if "filename" in data and isinstance(data["filename"], str):
            return self._load_file(data["filename"])

        # --- Format F: 响应本身就是 base64 字符串 ---
        if isinstance(data, str) and len(data) > 100:
            return self._decode_b64(data)

        return None

    # ==================================================================
    # 底层 IO
    # ==================================================================

    @staticmethod
    def _decode_b64(b64_str: str) -> Image.Image | None:
        """base64 → PIL Image。去除 data:image/png;base64, 前缀。"""
        try:
            s = b64_str
            if s.startswith("data:"):
                s = s.split(",", 1)[1]
            raw = base64.b64decode(s)
            return Image.open(io.BytesIO(raw))
        except Exception as exc:
            logger.warning("base64 解码失败: %s", exc)
            return None

    @staticmethod
    def _download(url: str) -> Image.Image | None:
        """从 URL 下载图像。"""
        try:
            if url.startswith("file://") or url.startswith("/") or (
                len(url) > 1 and url[1] == ":"
            ):
                return HttpImageProvider._load_file(url)
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            return Image.open(io.BytesIO(r.content))
        except Exception as exc:
            logger.warning("图像下载失败 %s: %s", url[:120], exc)
            return None

    @staticmethod
    def _load_file(path: str) -> Image.Image | None:
        """从本地文件系统加载图像。"""
        try:
            p = Path(path)
            if path.startswith("file://"):
                p = Path(path[7:])
            if not p.exists():
                logger.warning("文件不存在: %s", p)
                return None
            return Image.open(p)
        except Exception as exc:
            logger.warning("本地文件加载失败 %s: %s", path, exc)
            return None
