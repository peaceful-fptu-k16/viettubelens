import type { AnalysisResult, BatchResponse } from "./types";

function normalizedBase(url: string): string {
  return url.trim().replace(/\/+$/, "");
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function batchAnalyze(baseUrl: string, videoIds: string[]): Promise<BatchResponse> {
  const response = await fetch(`${normalizedBase(baseUrl)}/api/v1/analysis/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_ids: videoIds, max_comments: 30, refresh: false }),
  });
  return parseResponse<BatchResponse>(response);
}

export async function getAnalysis(baseUrl: string, videoId: string): Promise<AnalysisResult> {
  const response = await fetch(`${normalizedBase(baseUrl)}/api/v1/analysis/${encodeURIComponent(videoId)}`);
  return parseResponse<AnalysisResult>(response);
}

export async function getAnalysisBatch(baseUrl: string, videoIds: string[]): Promise<BatchResponse> {
  const response = await fetch(`${normalizedBase(baseUrl)}/api/v1/analysis/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_ids: videoIds }),
  });
  return parseResponse<BatchResponse>(response);
}

export async function healthCheck(baseUrl: string): Promise<{ status: string; model_version: string; demo_mode: boolean }> {
  const response = await fetch(`${normalizedBase(baseUrl)}/health`, { signal: AbortSignal.timeout(5000) });
  return parseResponse(response);
}

export async function clearBackendCache(baseUrl: string): Promise<void> {
  const response = await fetch(`${normalizedBase(baseUrl)}/api/v1/cache`, { method: "DELETE" });
  await parseResponse(response);
}
