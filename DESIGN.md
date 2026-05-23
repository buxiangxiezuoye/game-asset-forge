# 游戏素材生成工具 — 需求拆解与 MVP 设计方案

## 1. 2D 游戏素材常见类型

| 类型 | 英文 | 典型尺寸 | 说明 |
|------|------|---------|------|
| **角色** | Character | 32×32 ~ 128×128 | 玩家角色、NPC，通常需四方向帧或动画帧 |
| **敌人/怪物** | Enemy | 32×32 ~ 128×128 | 敌对单位，与角色类似但视觉风格更"反派" |
| **道具/物品** | Item / Prop | 16×16 ~ 64×64 | 武器、药水、宝箱、钥匙等可拾取物 |
| **地图瓦片** | Tile | 16×16 ~ 64×64 | 地形块（草地、水、沙、石），需无缝拼接 |
| **UI 图标** | UI Icon | 16×16 ~ 64×64 | 按钮、技能图标、血条、背包格 |
| **背景** | Background | 320×180 ~ 1920×1080 | 远中近景层，用于视差滚动 |
| **特效** | VFX | 32×32 ~ 128×128 | 爆炸、光效、魔法粒子，通常为帧序列 |

## 2. 不同素材在游戏开发中的使用方式

| 素材类型 | Unity 使用方式 | Godot 使用方式 | 通用格式 |
|---------|---------------|---------------|---------|
| 角色/敌人 | Sprite Renderer + Animator（Sprite Sheet 切片） | Sprite2D + AnimationPlayer（SpriteFrames） | PNG Sprite Sheet |
| 道具 | Sprite Renderer（单张或 Atlas） | Sprite2D | 单张 PNG / Atlas |
| 瓦片 Tile | Tilemap + Tile Palette（切片后刷地形） | TileMap + TileSet（autotile 支持） | Sprite Sheet PNG |
| UI 图标 | Canvas + Image | Control + TextureRect | 单张 PNG |
| 背景 | Sprite Renderer（按层排序） | ParallaxBackground + ParallaxLayer | 大尺寸 PNG |
| 特效 | ParticleSystem + Texture Sheet Animation | CPUParticles2D + Animation | 帧序列 PNG / Sprite Sheet |

**本项目 MVP 覆盖：角色、敌人（复用角色生成器+不同配色）、道具、Tile、UI 图标。**

## 3. MVP 功能范围

```
┌─────────────────────────────────────────────────────┐
│                    MVP 功能清单                      │
├─────────────────────────────────────────────────────┤
│ ✓ 文本→素材生成     │ 中文 prompt → procedural 生成  │
│ ✓ 4 类素材          │ 角色 / 敌人 / 道具 / 瓦片    │
│ ✓ 4 种风格预设      │ pixel_art / flat_cartoon /    │
│                      │ fantasy_painterly / sci_fi_ui │
│ ✓ 参数控制          │ 尺寸、主色、变体数量、种子     │
│ ✓ 批量生成          │ 一次提交多个 prompt           │
│ ✓ 实时预览          │ Web 端即时展示生成结果        │
│ ✓ 导出              │ 单张 PNG / Sprite Sheet / ZIP │
│ ✓ metadata.json     │ 含 pivot、frame、tag 信息     │
│ ✓ AI Provider 抽象  │ 默认 procedural，可切换 AI    │
└─────────────────────────────────────────────────────┘
```

## 4. 用户使用流程

```
[打开 Web 页面]
    │
    ▼
[选择素材类型] → 角色 / 敌人 / 道具 / 瓦片 / UI
    │
    ▼
[选择风格预设] → pixel_art / flat_cartoon / fantasy_painterly / sci_fi_ui
    │
    ▼
[输入中文描述] → "一只火焰史莱姆"
    │
    ▼
[调整参数] → 尺寸滑块 / 主色选择器 / 变体数量 / 随机种子
    │
    ▼
[点击 "生成素材"]
    │
    ▼
[预览区展示生成结果] → 可放大查看、对比变体
    │
    ▼
[选择导出] → 勾选素材 → 选择格式 → 下载 ZIP
```

## 5. 技术架构

```
浏览器 (React + TypeScript + Vite)
  │
  │ HTTP REST (JSON + Base64 Image)
  ▼
FastAPI Server (:8000)
  ├─ API 路由层 (/api/v1)
  │   ├─ POST /generate       单张生成
  │   ├─ POST /batch          批量生成
  │   ├─ GET  /styles         风格列表
  │   └─ POST /export         导出打包
  │
  ├─ 业务层
  │   ├─ PromptParser         关键词解析
  │   ├─ GeneratorFactory     根据类型+风格选择生成器
  │   └─ ExportService        PNG / Sprite Sheet / ZIP
  │
  └─ 生成器层 (Provider 模式)
      ├─ ProceduralGenerator  默认，Pillow 绘制
      └─ AIGenerator          (预留) SD / ComfyUI / OpenAI
```

## 6. 后端 API 列表

| 方法 | 路径 | 说明 | 请求体 |
|------|------|------|--------|
| `GET` | `/api/v1/styles` | 获取所有风格预设 | — |
| `POST` | `/api/v1/generate` | 单次生成素材 | `GenerateRequest` |
| `POST` | `/api/v1/batch` | 批量生成素材 | `BatchGenerateRequest` |
| `POST` | `/api/v1/export` | 导出素材包 | `ExportRequest` |
| `GET` | `/api/v1/health` | 健康检查 | — |

### 数据模型

```python
# GenerateRequest
{
  "prompt": "火焰史莱姆",
  "asset_type": "character",        # character | enemy | item | tile | ui
  "style": "pixel_art",             # pixel_art | flat_cartoon | fantasy_painterly | sci_fi_ui
  "size": 64,                       # 16-256
  "primary_color": "#e74c3c",       # HEX
  "variants": 3,                    # 1-10
  "seed": null                      # null=随机
}

# AssetResult
{
  "id": "abc123",
  "prompt": "火焰史莱姆",
  "asset_type": "character",
  "style": "pixel_art",
  "size": 64,
  "primary_color": "#e74c3c",
  "seed": 42,
  "image_base64": "iVBORw0KGgo...",
  "metadata": {
    "tags": ["火焰", "史莱姆"],
    "pivot": [32, 32],
    "frame": {"x": 0, "y": 0, "w": 64, "h": 64}
  }
}
```

## 7. 前端页面结构

```
┌──────────────────────────────────────────────────┐
│  🎮 游戏素材生成工具            Game Asset Forge │
├────────────┬─────────────────┬──────────────────┤
│  生成面板   │    预览区        │   导出面板        │
│            │                 │                  │
│ 素材类型 ◉ │  ┌───────────┐  │ 已选素材列表     │
│ 角色 敌人  │  │           │  │ ☑ 火焰史莱姆    │
│ 道具 瓦片  │  │  生成结果  │  │ ☑ 冰霜剑        │
│            │  │  实时预览  │  │ ☐ 草地瓦片      │
│ 风格选择   │  │           │  │                  │
│ ○像素 ○卡通│  │  网格/放大 │  │ 导出格式        │
│ ○幻想 ○科幻│  │  对比变体  │  │ ○ PNG          │
│            │  │           │  │ ○ Sprite Sheet  │
│ 描述输入   │  └───────────┘  │ ○ ZIP           │
│ [________] │                 │                  │
│            │                 │ [下载导出包]     │
│ 参数调整   │                 │                  │
│ 尺寸 [==]  │                 │                  │
│ 主色 [■]   │                 │                  │
│ 变体 [3]   │                 │                  │
│            │                 │                  │
│ [生成素材] │                 │                  │
└────────────┴─────────────────┴──────────────────┘
```

## 8. 导出文件结构

```
asset_export_20240101_120000.zip
├── sprites/
│   ├── character_fire_slime_001.png      # 单张精灵
│   ├── character_fire_slime_002.png
│   ├── item_ice_sword_001.png
│   └── tile_grass_001.png
├── spritesheets/
│   ├── character_fire_slime.png          # Sprite Sheet 整图
│   ├── character_fire_slime.json         # Frame 数据
│   └── tile_grass.png
├── metadata.json                          # 全局元数据
└── README.txt                             # 使用说明（含 Unity/Godot 导入指引）
```

### metadata.json 结构
```json
{
  "version": "1.0",
  "generated_at": "2024-01-01T12:00:00",
  "assets": [
    {
      "id": "abc123",
      "file": "sprites/character_fire_slime_001.png",
      "prompt": "火焰史莱姆",
      "type": "character",
      "style": "pixel_art",
      "size": 64,
      "pivot": [32, 32],
      "tags": ["火焰", "史莱姆"],
      "seed": 42
    }
  ]
}
```

## 9. 比赛评分点与项目对应

| 评分维度 | 本项目实现 |
|---------|-----------|
| 素材覆盖度 | 覆盖角色、敌人、道具、瓦片、UI 五类 |
| 生成效率 | procedural 毫秒级生成，AI 回退不阻塞 |
| 素材质量 | 4 种风格模板保证视觉一致性 |
| 风格一致性 | 同一风格共享色板、线宽、阴影、反锯齿规则 |
| 工具集成 | 导出 PNG + Sprite Sheet + metadata.json，Unity Tilemap/Godot TileSet 可直接导入 |
| 用户体验 | Web UI，中文界面，所见即所得 |
| 创新性 | Provider 抽象设计，procedural 与 AI 双模式可切换 |
| 可运行性 | 一键启动前后端，零外部依赖（默认 procedural 模式） |

## 10. 分阶段实施计划

### 第一阶段（本次）：项目脚手架 + 需求文档 ✓
- 创建前后端目录结构
- 编写 DESIGN.md
- 配置 package.json / requirements.txt / vite.config / tsconfig

### 第二阶段：后端生成器核心
- 完善 4 种风格模板 (pixel_art, flat_cartoon, fantasy_painterly, sci_fi_ui)
- 实现 5 类生成器 (character, enemy, item, tile, ui)
- PromptParser 关键词解析
- API 路由 (generate, batch, styles)

### 第三阶段：前端界面
- 生成面板组件
- 预览画布组件
- 风格选择器
- 导出面板
- API 对接

### 第四阶段：导出系统
- PNG 单张导出
- Sprite Sheet 拼接 + frame 数据
- ZIP 打包 + metadata.json

### 第五阶段：联调与演示打磨
- 前后端联调
- 错误处理
- UI 美化
- README + 演示说明
