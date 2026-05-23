import { useEffect, useState } from "react";
import { healthCheck, generateAsset, assetUrl, downloadUrl } from "./api";
import type {
  GenerateResponse, AssetType, StyleId,
  AnimationType, ExportTarget, FrameMeta,
} from "./types";
import {
  ASSET_TYPE_LABELS, STYLE_LABELS, ANIM_LABELS, EXPORT_LABELS,
} from "./types";

const SIZES = [16, 32, 64, 128];
const FRAME_COUNTS = [1, 2, 4, 8];

export default function App() {
  // ——— 状态 ———
  const [status, setStatus] = useState("检查中...");
  const [online, setOnline] = useState(false);

  const [prompt, setPrompt] = useState("一只蓝色史莱姆");
  const [assetType, setAssetType] = useState<AssetType>("enemy");
  const [style, setStyle] = useState<StyleId>("pixel_art");
  const [width, setWidth] = useState(64);
  const [height, setHeight] = useState(64);
  const [frames, setFrames] = useState(4);
  const [anim, setAnim] = useState<AnimationType>("idle");
  const [target, setTarget] = useState<ExportTarget>("generic");
  const [seed, setSeed] = useState<number | null>(42);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [metadata, setMetadata] = useState<any>(null);
  const [history, setHistory] = useState<GenerateResponse[]>([]);

  // ——— 初始化 ———
  useEffect(() => {
    healthCheck()
      .then((d) => { setStatus("已连接"); setOnline(true); })
      .catch(() => { setStatus("未连接"); setOnline(false); });
  }, []);

  // ——— 生成 ———
  const doGenerate = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await generateAsset({
        prompt, assetType, styleId: style, width, height,
        frameCount: frames, animation: anim, transparent: true,
        seed, exportTarget: target,
      });
      setResult(res);
      setHistory((prev) => [res, ...prev.slice(0, 19)]);

      // 拉取 metadata
      try {
        const mr = await fetch(assetUrl(res.metadataUrl));
        if (mr.ok) setMetadata(await mr.json());
      } catch { /* ignore */ }
    } catch (e) {
      setError((e as Error).message);
    }
    setLoading(false);
  };

  // ——— 下载 ZIP ———
  const doDownload = () => {
    if (!result) return;
    window.open(downloadUrl(result.jobId), "_blank");
  };

  // ——— 渲染 ———
  const spritesheetSrc = result ? assetUrl(result.spritesheetUrl) : null;

  return (
    <div className="app">
      {/* ========== 顶部标题栏 ========== */}
      <header className="topbar">
        <div className="topbar-left">
          <h1 className="logo">GameAssetForge</h1>
          <span className="subtitle">Text-to-2D Game Asset Generator</span>
        </div>
        <div className="topbar-right">
          <span className={`dot ${online ? "on" : "off"}`} />
          <span className="status-text">{status}</span>
        </div>
      </header>

      {/* ========== 主体两栏布局 ========== */}
      <div className="main-layout">
        {/* ===== 左侧表单 ===== */}
        <aside className="form-panel">
          <h2 className="panel-title">生成参数</h2>

          <label className="field">描述 Prompt</label>
          <input className="input" value={prompt}
            onChange={(e) => setPrompt(e.target.value)} placeholder="输入中文描述..." />

          <label className="field">素材类型 AssetType</label>
          <select className="select" value={assetType}
            onChange={(e) => setAssetType(e.target.value as AssetType)}>
            {Object.entries(ASSET_TYPE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v} ({k})</option>
            ))}
          </select>

          <label className="field">风格 Style</label>
          <div className="chips">
            {(Object.entries(STYLE_LABELS) as [StyleId, string][]).map(([k, v]) => (
              <button key={k} className={`chip ${style === k ? "active" : ""}`}
                onClick={() => setStyle(k)}>{v}</button>
            ))}
          </div>

          <label className="field">尺寸 Size</label>
          <div className="row">
            <div className="half">
              <span className="mini-label">宽</span>
              <select className="select" value={width}
                onChange={(e) => setWidth(Number(e.target.value))}>
                {SIZES.map((v) => (<option key={v} value={v}>{v}px</option>))}
              </select>
            </div>
            <div className="half">
              <span className="mini-label">高</span>
              <select className="select" value={height}
                onChange={(e) => setHeight(Number(e.target.value))}>
                {SIZES.map((v) => (<option key={v} value={v}>{v}px</option>))}
              </select>
            </div>
          </div>

          <label className="field">帧数 FrameCount</label>
          <div className="chips">
            {FRAME_COUNTS.map((v) => (
              <button key={v} className={`chip ${frames === v ? "active" : ""}`}
                onClick={() => setFrames(v)}>{v}</button>
            ))}
          </div>

          <label className="field">动画 Animation</label>
          <div className="chips">
            {(Object.entries(ANIM_LABELS) as [AnimationType, string][]).map(([k, v]) => (
              <button key={k} className={`chip ${anim === k ? "active" : ""}`}
                onClick={() => setAnim(k)}>{v}</button>
            ))}
          </div>

          <label className="field">导出目标 ExportTarget</label>
          <select className="select" value={target}
            onChange={(e) => setTarget(e.target.value as ExportTarget)}>
            {Object.entries(EXPORT_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>

          <label className="field">种子 Seed</label>
          <input className="input" type="number"
            value={seed ?? ""}
            onChange={(e) => setSeed(e.target.value ? Number(e.target.value) : null)}
            placeholder="留空则随机" />

          <button className="btn-primary" onClick={doGenerate} disabled={loading}>
            {loading ? "生成中..." : "生成素材 Generate"}
          </button>

          {error && <div className="error-msg">{error}</div>}
        </aside>

        {/* ===== 右侧预览 ===== */}
        <main className="preview-panel">
          <h2 className="panel-title">预览 Preview</h2>

          {loading && <div className="loading-spinner">生成中...</div>}

          {result && !loading && (
            <div className="result-area">
              {/* 元信息 */}
              <div className="meta-bar">
                <span className="tag">Job: {result.jobId}</span>
                <span className="tag">帧: {result.assets.length}</span>
                <span className="tag">{width}×{height}</span>
              </div>

              {/* Sprite Sheet */}
              {spritesheetSrc && (
                <section className="section">
                  <h3>Sprite Sheet</h3>
                  <div className="sheet-box">
                    <img src={spritesheetSrc} alt="spritesheet"
                      className={style === "pixel_art" ? "pixel" : "smooth"} />
                  </div>
                </section>
              )}

              {/* 逐帧 */}
              <section className="section">
                <h3>逐帧预览 Frames</h3>
                <div className="frames-row">
                  {result.assets.map((a) => (
                    <div key={a.id} className="frame-item">
                      <img src={assetUrl(a.url)} alt={a.id}
                        className={style === "pixel_art" ? "pixel" : "smooth"} />
                      <span className="frame-label">{a.id.split("_").pop()}</span>
                    </div>
                  ))}
                </div>
              </section>

              {/* Metadata 摘要 */}
              {metadata && (
                <section className="section">
                  <h3>Metadata</h3>
                  <div className="meta-grid">
                    <div><span>jobId</span><code>{metadata.jobId}</code></div>
                    <div><span>frameWidth</span><code>{metadata.frameWidth}px</code></div>
                    <div><span>frameHeight</span><code>{metadata.frameHeight}px</code></div>
                    <div><span>frameCount</span><code>{metadata.frameCount}</code></div>
                    <div><span>animation</span><code>{metadata.animation}</code></div>
                    <div><span>spritesheet</span><code>{metadata.spritesheet}</code></div>
                    <div><span>compatibleWith</span>
                      <code>{(metadata.compatibleWith || []).join(", ")}</code>
                    </div>
                    {metadata.frames && (
                      <div className="meta-full">
                        <span>frames</span>
                        <div>
                          {(metadata.frames as FrameMeta[]).map((f, i) => (
                            <code key={i}>{f.filename}: x={f.x} y={f.y} w={f.w}h={f.h} {f.duration}ms</code>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </section>
              )}

              {/* 下载按钮 */}
              <button className="btn-download" onClick={doDownload}>
                下载 ZIP 包 Download
              </button>
            </div>
          )}

          {!result && !loading && (
            <div className="empty-state">
              <p>输入参数，点击「生成素材」开始</p>
              <p className="hint">默认示例：一只蓝色史莱姆 · 像素风 · idle 动画 · 4帧</p>
            </div>
          )}
        </main>
      </div>

      {/* ===== 底部历史 ===== */}
      {history.length > 0 && (
        <footer className="history-bar">
          <h3>历史记录</h3>
          <div className="history-scroll">
            {history.map((h) => (
              <div key={h.jobId} className="hist-thumb"
                onClick={() => {
                  setResult(h);
                  fetch(assetUrl(h.metadataUrl))
                    .then((r) => r.ok ? r.json() : null)
                    .then((m) => m && setMetadata(m))
                    .catch(() => {});
                }}>
                <img src={assetUrl(h.spritesheetUrl)} alt={h.jobId}
                  className={style === "pixel_art" ? "pixel" : "smooth"} />
                <span>{h.jobId.slice(0, 6)}</span>
              </div>
            ))}
          </div>
        </footer>
      )}
    </div>
  );
}
