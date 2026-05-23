# Game Asset Forge — 2D 游戏素材生成工具

文本输入 → 程序化/AI 生成 → 实时预览 → 导出为 Unity/Godot 可用格式。

## 快速启动

### 后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # 默认 mock 模式，无需 API Key
python run_backend.py
# 访问 http://localhost:8002/docs
```

### 前端

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

## 图像生成模式

项目支持多种生成后端，通过 `.env` 切换。**无 API Key 时自动使用 mock 回退，保证始终可用。**

### 1. mock（默认，零成本）

```env
IMAGE_PROVIDER_MODE=mock
```

程序化生成（Pillow），开箱即跑。适合演示、开发调试、离线使用。

---

### 2. http — 通用 AI 图像生成

将 `IMAGE_PROVIDER_MODE` 设为 `http` 后可接入任意兼容 HTTP API 的后端。

#### 支持的响应格式

Provider 自动识别以下格式，无需手动配置：
- `{"images": ["base64..."]}` — base64 PNG 数组
- `{"images": [{"url": "https://..."}]}` — 图片 URL
- `{"images": [{"filename": "/path/to/file.png"}]}` — 本地文件路径
- `{"data": [{"b64_json": "..."}]}` — OpenAI 兼容
- `{"image": "base64..."}` — 单图 base64

> 失败时**自动回退到 mock**，不会中断前端使用。

---

### 3. 后端接入指南

#### 3a. Stable Diffusion WebUI（A1111 / Forge）

SD WebUI 自带 HTTP API，端口通常为 7860。

```env
IMAGE_PROVIDER_MODE=http
IMAGE_PROVIDER_BACKEND=sd_webui
IMAGE_PROVIDER_ENDPOINT=http://localhost:7860/sdapi/v1/txt2img
IMAGE_PROVIDER_API_KEY=
```

启动 SD WebUI 时确保启用 API：
```bash
# 方法 1：启动参数加 --api
python launch.py --api

# 方法 2：使用 Forge/ReForge（默认启用 API）
```

验证 API 可用：
```bash
curl http://localhost:7860/sdapi/v1/sd-models
```

#### 3b. ComfyUI

ComfyUI 默认启用 API，端口 8188。需要设置输出目录以便 Provider 读取生成结果。

```env
IMAGE_PROVIDER_MODE=http
IMAGE_PROVIDER_BACKEND=comfyui
IMAGE_PROVIDER_ENDPOINT=http://localhost:8188/prompt
COMFYUI_OUTPUT_DIR=D:/ComfyUI_windows_portable/ComfyUI/output
IMAGE_PROVIDER_STEPS=20
IMAGE_PROVIDER_CFG=7.0
```

> ComfyUI 生成流程：POST `/prompt` 提交 workflow → 轮询 `/history/{prompt_id}` → 从 `COMFYUI_OUTPUT_DIR` 读取图片。Provider 自动处理整个流程。

#### 3c. 云端 API（SiliconFlow / Novita / OpenAI）

```env
IMAGE_PROVIDER_MODE=http
IMAGE_PROVIDER_BACKEND=generic
IMAGE_PROVIDER_ENDPOINT=https://api.siliconflow.cn/v1/images/generations
IMAGE_PROVIDER_API_KEY=sk-your-api-key
IMAGE_PROVIDER_MODEL=stabilityai/stable-diffusion-3-5-large
```

> 只需替换 `ENDPOINT`、`API_KEY`、`MODEL` 即可接入任何兼容 OpenAI 格式的图像生成 API。

#### 3d. 自定义 HTTP 后端

任何接收 JSON POST 并返回图像的 HTTP 服务均可接入：

```env
IMAGE_PROVIDER_MODE=http
IMAGE_PROVIDER_BACKEND=generic
IMAGE_PROVIDER_ENDPOINT=https://your-custom-api.com/generate
IMAGE_PROVIDER_API_KEY=your-key
```

默认 POST payload 格式：
```json
{
  "prompt": "pixel art, 16-bit...", "negative_prompt": "blurry, smooth...",
  "width": 64, "height": 64, "seed": 42
}
```

若需要不同的请求格式，可直接修改 `backend/app/generators/http_image_provider.py` 中的 `_build_payload()` 方法（约 20 行代码）。

---

### 4. 环境变量完整参考

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `IMAGE_PROVIDER_MODE` | `mock` | `mock` 或 `http` |
| `IMAGE_PROVIDER_BACKEND` | `auto` | `auto` / `sd_webui` / `comfyui` / `openai` / `generic` |
| `IMAGE_PROVIDER_ENDPOINT` | — | HTTP 端点 URL |
| `IMAGE_PROVIDER_API_KEY` | — | Bearer Token（可选） |
| `IMAGE_PROVIDER_MODEL` | — | 模型名（SD WebUI 不需要） |
| `IMAGE_PROVIDER_TIMEOUT` | `120` | 请求超时秒数 |
| `IMAGE_PROVIDER_STEPS` | `20` | SD/ComfyUI 采样步数 |
| `IMAGE_PROVIDER_CFG` | `7.0` | SD/ComfyUI CFG Scale |
| `IMAGE_PROVIDER_SAMPLER` | `Euler a` | SD/ComfyUI 采样器 |
| `COMFYUI_OUTPUT_DIR` | — | ComfyUI 输出目录路径 |

## 技术栈

- 前端：React + TypeScript + Vite
- 后端：Python FastAPI
- 图像：Pillow（程序化生成）
- AI 扩展：可插拔 Provider 抽象层（BaseImageProvider → HttpImageProvider）

## 项目结构

```
game-asset-forge/
├── frontend/               # React + TypeScript + Vite
│   └── src/
│       ├── api.ts          # API 客户端
│       ├── App.tsx         # 主界面
│       └── styles.css      # 暗色主题
├── backend/                # Python FastAPI
│   └── app/
│       ├── generators/     # 生成器层
│       │   ├── base.py               # 程序化生成基类
│       │   ├── mock_generator.py     # 程序化渲染器
│       │   ├── base_provider.py      # AI Provider 抽象
│       │   └── http_image_provider.py # HTTP AI Provider
│       ├── services/       # 业务逻辑
│       │   ├── asset_service.py      # 任务生成
│       │   ├── style_service.py      # 风格预设
│       │   └── spritesheet_service.py # Sprite Sheet 拼接
│       └── main.py         # FastAPI 入口
└── README.md
```

## 参数校验

所有输入在后端严格校验，防止无效请求：

| 参数 | 允许值 |
|------|--------|
| `width` / `height` | 16, 32, 64, 128, 256 |
| `frameCount` | 1, 2, 4, 8 |
| `prompt` | 1-300 字符，不能为空 |
| `batchSize` | 最多 10 个 prompt |

## 缓存机制

以 `(prompt, assetType, styleId, width, height, frameCount, seed)` 为键做 SHA-256 哈希。相同参数生成过则直接返回已有结果，metadata 中标记 `cacheHit: true`。前端显示「缓存命中」标识。

- 大幅减少重复生成耗时（第二次生成同类参数几乎即时）
- 节省 AI API 调用成本

## 低成本策略

| 策略 | 说明 |
|------|------|
| 小图优先 | 默认 64×64，够用再放大。尺寸翻倍 = 像素数 ×4 |
| 缓存复用 | 相同参数命中缓存，零计算成本 |
| 批量导出 | batch 接口一次提交多个 prompt，减少往返 |
| 本地模型可选 | `IMAGE_PROVIDER_MODE` 支持指向本地 SD/ComfyUI，无 API 费用 |
| 默认 mock | 不配置任何 API Key 也能跑，纯本地程序化生成 |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/styles` | 风格列表 |
| POST | `/api/generate` | 单次生成 |
| POST | `/api/batch` | 批量生成（最多 10 prompts） |
| GET | `/api/jobs/{jobId}` | 任务状态 |
| GET | `/api/download/{jobId}` | 下载 ZIP |
