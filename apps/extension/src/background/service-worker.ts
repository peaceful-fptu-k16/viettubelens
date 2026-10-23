import { batchAnalyze, clearBackendCache, getAnalysis, getAnalysisBatch, healthCheck } from "../shared/api";
import { DEFAULT_SETTINGS, getSettings } from "../shared/settings";
import type { AnalysisResult, BatchResponse, WorkerRequest } from "../shared/types";

const SESSION_CACHE_TTL = 15 * 60 * 1000;
const sessionKey = (videoId: string) => `vtl:analysis:${videoId}`;

interface SessionEntry {
  cachedAt: number;
  result: AnalysisResult;
}

async function sessionResults(videoIds: string[]): Promise<Map<string, AnalysisResult>> {
  const keys = videoIds.map(sessionKey);
  const stored = await chrome.storage.session.get(keys);
  const now = Date.now();
  const found = new Map<string, AnalysisResult>();
  for (const videoId of videoIds) {
    const entry = stored[sessionKey(videoId)] as SessionEntry | undefined;
    if (entry && now - entry.cachedAt < SESSION_CACHE_TTL) {
      found.set(videoId, { ...entry.result, cache_hit: true });
    }
  }
  return found;
}

async function storeSessionResults(items: AnalysisResult[]): Promise<void> {
  const terminal = items.filter((item) => item.status !== "queued");
  if (!terminal.length) return;
  const cachedAt = Date.now();
  await chrome.storage.session.set(Object.fromEntries(
    terminal.map((result) => [sessionKey(result.video_id), { cachedAt, result } satisfies SessionEntry]),
  ));
}

async function withSessionCache(
  videoIds: string[],
  fetchMissing: (missing: string[]) => Promise<BatchResponse>,
): Promise<BatchResponse> {
  const cached = await sessionResults(videoIds);
  const missing = videoIds.filter((videoId) => !cached.has(videoId));
  if (missing.length) {
    const response = await fetchMissing(missing);
    await storeSessionResults(response.items);
    for (const item of response.items) cached.set(item.video_id, item);
  }
  return { items: videoIds.flatMap((videoId) => {
    const item = cached.get(videoId);
    return item ? [item] : [];
  }) };
}

chrome.runtime.onInstalled.addListener(async () => {
  const current = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  await chrome.storage.sync.set({ ...DEFAULT_SETTINGS, ...current });
});

chrome.runtime.onMessage.addListener((message: WorkerRequest, _sender, sendResponse) => {
  void (async () => {
    try {
      const settings = await getSettings();
      switch (message.type) {
        case "BATCH_ANALYZE":
          sendResponse({
            ok: true,
            data: await withSessionCache(
              message.videoIds,
              (missing) => batchAnalyze(settings.backendUrl, missing),
            ),
          });
          break;
        case "GET_ANALYSIS": {
          const response = await withSessionCache(
            [message.videoId],
            async ([videoId]) => ({ items: [await getAnalysis(settings.backendUrl, videoId)] }),
          );
          sendResponse({ ok: true, data: response.items[0] });
          break;
        }
        case "GET_ANALYSIS_BATCH":
          sendResponse({
            ok: true,
            data: await withSessionCache(
              message.videoIds,
              (missing) => getAnalysisBatch(settings.backendUrl, missing),
            ),
          });
          break;
        case "HEALTH_CHECK":
          sendResponse({ ok: true, data: await healthCheck(settings.backendUrl) });
          break;
        case "CLEAR_CACHE":
          await clearBackendCache(settings.backendUrl);
          await chrome.storage.session.clear();
          sendResponse({ ok: true });
          break;
        case "REPORT_CONTENT_STATUS":
          await chrome.storage.local.set({ vtlContentStatus: message.status });
          sendResponse({ ok: true });
          break;
        case "GET_CONTENT_STATUS": {
          const stored = await chrome.storage.local.get("vtlContentStatus");
          const status = stored.vtlContentStatus;
          const active = Boolean(status && Date.now() - status.updatedAt < 15_000);
          sendResponse({
            ok: true,
            data: status ? { ...status, active } : { active: false, updatedAt: 0 },
          });
          break;
        }
      }
    } catch (error) {
      sendResponse({ ok: false, error: error instanceof Error ? error.message : "Lỗi không xác định" });
    }
  })();
  return true;
});
