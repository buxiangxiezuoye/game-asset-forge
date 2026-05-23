from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from app.config import OUTPUTS_DIR
from app.models import (
    GenerateRequest, GenerateResponse,
    BatchGenerateRequest, BatchGenerateResponse,
    JobStatus, StyleInfo,
)
from app.services.asset_service import AssetService
from app.services.style_service import StyleService

app = FastAPI(title="Game Asset Forge", version="0.1.0")

# CORS — 允许前端开发端口
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件 — 暴露生成的素材
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")

asset_service = AssetService()


# ==================== 1. Health ====================

@app.get("/health")
async def health():
    return {"status": "ok"}


# ==================== 2. Styles ====================

@app.get("/api/styles", response_model=list[StyleInfo])
async def list_styles():
    return StyleService.list_styles()


# ==================== 3. Generate ====================

@app.post("/api/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    try:
        return asset_service.generate(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 4. Batch Generate ====================

@app.post("/api/batch", response_model=BatchGenerateResponse)
async def batch_generate(req: BatchGenerateRequest):
    return asset_service.batch_generate(req)


# ==================== 5. Job Status ====================

@app.get("/api/jobs/{jobId}", response_model=JobStatus)
async def get_job(jobId: str):
    job = asset_service.get_job(jobId)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {jobId} not found")
    return job


# ==================== 6. Download ZIP ====================

@app.get("/api/download/{jobId}")
async def download_job(jobId: str):
    zip_bytes = asset_service.build_zip(jobId)
    if zip_bytes is None:
        raise HTTPException(status_code=404, detail=f"Job {jobId} not found")
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{jobId}.zip"'},
    )
