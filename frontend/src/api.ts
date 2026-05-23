import type {
  GenerateRequest, GenerateResponse,
  BatchGenerateRequest, BatchGenerateResponse,
  JobStatus, StyleInfo,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8002";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`[${res.status}] ${url} — ${body}`);
  }
  if (res.headers.get("content-type")?.includes("application/json")) {
    return res.json();
  }
  return undefined as T;
}

export async function healthCheck(): Promise<{ status: string }> {
  return request("/health");
}

export async function listStyles(): Promise<StyleInfo[]> {
  return request("/api/styles");
}

export async function generateAsset(req: GenerateRequest): Promise<GenerateResponse> {
  return request("/api/generate", { method: "POST", body: JSON.stringify(req) });
}

export async function batchGenerate(req: BatchGenerateRequest): Promise<BatchGenerateResponse> {
  return request("/api/batch", { method: "POST", body: JSON.stringify(req) });
}

export async function getJob(jobId: string): Promise<JobStatus> {
  return request(`/api/jobs/${jobId}`);
}

export function assetUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export function downloadUrl(jobId: string): string {
  return `${API_BASE_URL}/api/download/${jobId}`;
}
