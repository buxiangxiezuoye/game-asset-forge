# Game Asset Forge — 2D 游戏素材生成工具

文本输入 → 程序化生成 → 实时预览 → 导出为 Unity/Godot 可用格式。

## 快速启动

### 后端

```bash
cd backend
pip install -r requirements.txt
python run_backend.py
# 访问 http://localhost:8000/docs
```

### 前端

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

## 技术栈

- 前端：React + TypeScript + Vite
- 后端：Python FastAPI
- 图像：Pillow（程序化生成）
- AI 扩展：Provider 抽象层（预留 SD/ComfyUI/OpenAI 接入）

## 项目结构

```
game-asset-forge/
├── frontend/          # React + TypeScript + Vite
├── backend/           # Python FastAPI
└── README.md
```
