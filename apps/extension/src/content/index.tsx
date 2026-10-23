import React, { useEffect, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { DEFAULT_SETTINGS, getSettings } from "../shared/settings";
import type {
  AnalysisResult,
  ContentStatus,
  ExtensionSettings,
  WorkerRequest,
} from "../shared/types";
import { AnalysisBadge } from "./Badge";
import { isLiveCard } from "./card-visibility";
import styles from "./content.css?inline";

const VIDEO_LINK_SELECTOR = 'a[href*="/watch?v="]';
const CARD_SELECTOR = [
  "ytd-rich-item-renderer", "ytd-rich-grid-media", "ytd-video-renderer",
  "ytd-grid-video-renderer", "ytd-compact-video-renderer", "ytd-playlist-video-renderer",
  "yt-lockup-view-model", "yt-lockup-view-model-component", ".yt-lockup-view-model",
].join(",");
const THUMBNAIL_SELECTOR = [
  "a#thumbnail", "ytd-thumbnail", "yt-thumbnail-view-model",
  "yt-thumbnail-view-model-v2", ".yt-lockup-view-model__content-image",
].join(",");
const BATCH_SIZE = 6;
const VIEWPORT_MARGIN = 360;
const MAX_ANIMATED_BADGES = 6;

interface TrackedCard {
  uid: number;
  card: Element;
  anchor: HTMLElement;
  videoId: string;
  nearViewport: boolean;
}

interface PositionedBadge {
  uid: number;
  videoId: string;
  left: number;
  top: number;
  popoverOffset: number;
  popoverAbove: boolean;
  result: AnalysisResult;
}

function BadgeOverlay({ items, settings }: { items: PositionedBadge[]; settings: ExtensionSettings }) {
  const [openVideoId, setOpenVideoId] = useState<string | null>(null);
  useEffect(() => {
    if (openVideoId && !items.some((item) => item.videoId === openVideoId)) {
      setOpenVideoId(null);
    }
  }, [items, openVideoId]);
  return <div className={`vtl-overlay ${openVideoId ? "has-open-popover" : ""}`}>{items.map((item, index) => (
    <div
      className={`vtl-slot ${openVideoId === item.videoId ? "is-open" : ""}`}
      data-video-id={item.videoId}
      key={item.uid}
      style={{ transform: `translate3d(${item.left}px,${item.top}px,0)` }}
    >
      <AnalysisBadge
        result={item.result}
        showToxicity={settings.showToxicity}
        animations={settings.animations && index < MAX_ANIMATED_BADGES}
        index={index}
        open={openVideoId === item.videoId}
        onOpenChange={(open) => setOpenVideoId(open ? item.videoId : null)}
        popoverOffset={item.popoverOffset}
        popoverAbove={item.popoverAbove}
      />
    </div>
  ))}</div>;
}

const trackedCards = new Map<Element, TrackedCard>();
const trackedAnchors = new WeakMap<HTMLElement, TrackedCard>();
const results = new Map<string, AnalysisResult>();
const pending = new Set<string>();
let settings: ExtensionSettings = DEFAULT_SETTINGS;
let overlayHost: HTMLElement | null = null;
let overlayRoot: Root | null = null;
let nextUid = 1;
let refreshScheduled = false;
let pollTimer: number | undefined;
let pollAttempt = 0;
let priorityVideoIds: string[] = [];
let lastDetectedCount = 0;
let lastVisibleCount = 0;
let lastMountedCount = 0;
let lastReportedState = "";
let bootstrapError: string | undefined;
let contextInvalidated = false;

const nearObserver = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      const tracked = trackedAnchors.get(entry.target as HTMLElement);
      if (tracked) tracked.nearViewport = entry.isIntersecting;
    }
    scheduleRefresh();
  },
  { rootMargin: `${VIEWPORT_MARGIN}px 0px`, threshold: 0 },
);

function hasRuntimeContext(): boolean {
  if (contextInvalidated) return false;
  try { return Boolean(chrome.runtime?.id); } catch { return false; }
}

function stopInvalidatedContext(): void {
  if (contextInvalidated) return;
  contextInvalidated = true;
  destroyOverlay();
  nearObserver.disconnect();
  if (pollTimer !== undefined) window.clearTimeout(pollTimer);
}

function videoIdFromLink(link: HTMLAnchorElement): string | null {
  try { return new URL(link.href, location.origin).searchParams.get("v"); } catch { return null; }
}

function findCard(link: HTMLAnchorElement): Element {
  return link.closest(CARD_SELECTOR) ?? link.closest("#dismissible") ??
    link.closest<HTMLElement>('[class*="lockup"]') ?? link;
}

function findAnchor(card: Element, link: HTMLAnchorElement): HTMLElement {
  return card.querySelector<HTMLElement>(THUMBNAIL_SELECTOR) ??
    link.closest<HTMLElement>("ytd-thumbnail, yt-thumbnail-view-model") ?? link;
}

function isVisible(rect: DOMRect): boolean {
  return rect.width >= 80 && rect.height >= 45 && rect.bottom >= 0 &&
    rect.top <= window.innerHeight && rect.right >= 0 && rect.left <= window.innerWidth;
}

function untrack(card: Element): void {
  const tracked = trackedCards.get(card);
  if (!tracked) return;
  nearObserver.unobserve(tracked.anchor);
  trackedCards.delete(card);
}

function trackLink(link: HTMLAnchorElement): void {
  const videoId = videoIdFromLink(link);
  if (!videoId) return;
  const card = findCard(link);
  const anchor = findAnchor(card, link);
  const existing = trackedCards.get(card);
  if (existing?.videoId === videoId && existing.anchor === anchor) return;
  if (existing) untrack(card);
  if (isLiveCard(card, anchor)) return;
  const tracked = { uid: nextUid++, card, anchor, videoId, nearViewport: false };
  trackedCards.set(card, tracked);
  trackedAnchors.set(anchor, tracked);
  nearObserver.observe(anchor);
}

function trackNode(node: Node): void {
  if (!(node instanceof Element)) return;
  if (node.matches(VIDEO_LINK_SELECTOR)) trackLink(node as HTMLAnchorElement);
  node.querySelectorAll<HTMLAnchorElement>(VIDEO_LINK_SELECTOR).forEach(trackLink);
}

function cleanupDisconnectedCards(): void {
  for (const [card] of trackedCards) if (!document.contains(card)) untrack(card);
  lastDetectedCount = trackedCards.size;
}

function placeholder(videoId: string): AnalysisResult {
  return {
    video_id: videoId, status: "queued", sample_size: 0, relevant_count: 0,
    sentiment_distribution: { positive: 0, neutral: 1, negative: 0 }, toxicity_rate: 0,
    overall_reaction: "neutral", confidence_score: 0, confidence_tier: "low",
    abstained: false, abstention_reasons: [], evidence: [], cache_hit: false,
    model_version: "pending", updated_at: new Date().toISOString(), source: "youtube",
  };
}

function errorResult(videoId: string, message: string): AnalysisResult {
  return { ...placeholder(videoId), status: "error", message };
}

function ensureOverlay(): void {
  if (overlayRoot || !settings.enabled) return;
  overlayHost = document.createElement("div");
  overlayHost.dataset.viettubelensRoot = "true";
  overlayHost.style.cssText = "position:fixed;inset:0;width:0;height:0;z-index:2147483000;pointer-events:none;overflow:visible";
  const shadow = overlayHost.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = styles;
  const mount = document.createElement("div");
  shadow.append(style, mount);
  document.documentElement.append(overlayHost);
  overlayRoot = createRoot(mount);
}

function destroyOverlay(): void {
  overlayRoot?.unmount();
  overlayHost?.remove();
  overlayRoot = null;
  overlayHost = null;
  lastMountedCount = 0;
}

async function send<T>(message: WorkerRequest): Promise<T> {
  if (!hasRuntimeContext()) {
    stopInvalidatedContext();
    throw new Error("Extension vừa được cập nhật · hãy làm mới YouTube");
  }
  let response: { ok?: boolean; error?: string; data?: unknown };
  try {
    response = await chrome.runtime.sendMessage(message);
  } catch (error) {
    if (!hasRuntimeContext() || String(error).includes("Extension context invalidated")) stopInvalidatedContext();
    throw error;
  }
  if (!response?.ok) throw new Error(response?.error ?? "Không thể kết nối backend");
  return response.data as T;
}

function reportStatus(force = false): void {
  if (!hasRuntimeContext()) { stopInvalidatedContext(); return; }
  const status: ContentStatus = {
    active: true, detectedCards: lastDetectedCount, visibleCards: lastVisibleCount,
    badgesMounted: lastMountedCount, updatedAt: Date.now(), error: bootstrapError,
  };
  const state = JSON.stringify({ ...status, updatedAt: 0 });
  if (!force && state === lastReportedState) return;
  lastReportedState = state;
  try {
    void chrome.runtime.sendMessage({ type: "REPORT_CONTENT_STATUS", status } satisfies WorkerRequest)
      .catch((error: unknown) => {
        if (String(error).includes("Extension context invalidated")) stopInvalidatedContext();
      });
  } catch { stopInvalidatedContext(); }
}

function schedulePoll(delay = 1200): void {
  if (!pending.size || pollTimer !== undefined || contextInvalidated) return;
  pollTimer = window.setTimeout(() => { pollTimer = undefined; void pollPending(); }, delay);
}

async function pollPending(): Promise<void> {
  const ids = Array.from(new Set([
    ...priorityVideoIds.filter((videoId) => pending.has(videoId)),
    ...pending,
  ])).slice(0, settings.maxCards);
  if (!ids.length) return;
  if (pollAttempt > 8) {
    for (const id of ids) {
      results.set(id, errorResult(id, "Phân tích mất nhiều thời gian hơn dự kiến"));
      pending.delete(id);
    }
    pollAttempt = 0;
    refreshOverlay();
    return;
  }
  try {
    const response = await send<{ items: AnalysisResult[] }>({ type: "GET_ANALYSIS_BATCH", videoIds: ids });
    let completed = 0;
    for (const item of response.items) {
      results.set(item.video_id, item);
      if (item.status !== "queued") { pending.delete(item.video_id); completed++; }
    }
    pollAttempt = completed > 0 ? 0 : pollAttempt + 1;
  } catch { pollAttempt++; }
  refreshOverlay();
  if (pending.size) schedulePoll(Math.min(1200 * 1.55 ** pollAttempt, 7000));
}

async function requestMissing(ids: string[]): Promise<void> {
  const missing = ids.filter((id) => !results.has(id) && !pending.has(id));
  if (!missing.length) return;
  missing.forEach((id) => pending.add(id));
  refreshOverlay();
  for (let offset = 0; offset < missing.length; offset += BATCH_SIZE) {
    const batch = missing.slice(offset, offset + BATCH_SIZE);
    try {
      const response = await send<{ items: AnalysisResult[] }>({ type: "BATCH_ANALYZE", videoIds: batch });
      for (const item of response.items) {
        results.set(item.video_id, item);
        if (item.status !== "queued") pending.delete(item.video_id);
      }
    } catch (error) {
      for (const id of batch) {
        results.set(id, errorResult(id, error instanceof Error ? error.message : "Lỗi kết nối"));
        pending.delete(id);
      }
    }
    refreshOverlay();
  }
  if (pending.size) { pollAttempt = 0; schedulePoll(); }
}

function selectedCards(): Array<{ tracked: TrackedCard; rect: DOMRect; visible: boolean }> {
  cleanupDisconnectedCards();
  const measured = Array.from(trackedCards.values())
    .filter((tracked) => tracked.nearViewport && !isLiveCard(tracked.card, tracked.anchor))
    .map((tracked) => {
      const rect = tracked.anchor.getBoundingClientRect();
      return { tracked, rect, visible: isVisible(rect) };
    })
    .filter(({ rect }) => rect.width >= 80 && rect.height >= 45)
    .sort((left, right) => left.visible !== right.visible
      ? (left.visible ? -1 : 1)
      : Math.abs(left.rect.top) - Math.abs(right.rect.top));
  const unique: typeof measured = [];
  const videoIds = new Set<string>();
  for (const item of measured) {
    if (videoIds.has(item.tracked.videoId)) continue;
    videoIds.add(item.tracked.videoId);
    unique.push(item);
    if (unique.length >= settings.maxCards) break;
  }
  lastVisibleCount = measured.filter(({ visible }) => visible).length;
  return unique;
}

function refreshOverlay(): void {
  if (!hasRuntimeContext()) { stopInvalidatedContext(); return; }
  if (!settings.enabled) { destroyOverlay(); reportStatus(); return; }
  const selected = selectedCards();
  priorityVideoIds = selected.map(({ tracked }) => tracked.videoId);
  const visible = selected.filter((item) => item.visible);
  ensureOverlay();
  if (overlayHost) overlayHost.dataset.theme = document.documentElement.hasAttribute("dark") ? "dark" : "light";
  const positioned = visible.map(({ tracked, rect }) => ({
    uid: tracked.uid, videoId: tracked.videoId,
    left: Math.round(rect.left + 10), top: Math.round(rect.top + 10),
    popoverOffset: Math.min(0, window.innerWidth - (rect.left + 10 + 360 + 12)),
    popoverAbove: rect.top > window.innerHeight * 0.45,
    result: results.get(tracked.videoId) ?? placeholder(tracked.videoId),
  }));
  lastMountedCount = positioned.length;
  overlayRoot?.render(<BadgeOverlay items={positioned} settings={settings} />);
  reportStatus();
  void requestMissing(selected.map(({ tracked }) => tracked.videoId));
}

function scheduleRefresh(): void {
  if (!hasRuntimeContext()) { stopInvalidatedContext(); return; }
  if (refreshScheduled) return;
  refreshScheduled = true;
  requestAnimationFrame(() => { refreshScheduled = false; refreshOverlay(); });
}

async function bootstrap(): Promise<void> {
  try { settings = await getSettings(); }
  catch (error) {
    settings = DEFAULT_SETTINGS;
    bootstrapError = error instanceof Error ? error.message : "Không đọc được cài đặt";
  }
  trackNode(document.documentElement);
  scheduleRefresh();
  new MutationObserver((records) => {
    for (const record of records) {
      if (record.type === "attributes") trackNode(record.target);
      record.addedNodes.forEach(trackNode);
    }
    scheduleRefresh();
  }).observe(document.documentElement, {
    childList: true, subtree: true, attributes: true, attributeFilter: ["href"],
  });
  addEventListener("scroll", scheduleRefresh, { passive: true, capture: true });
  addEventListener("resize", scheduleRefresh, { passive: true });
  chrome.storage.onChanged.addListener(async () => {
    settings = await getSettings().catch(() => DEFAULT_SETTINGS);
    scheduleRefresh();
  });
  window.setInterval(() => reportStatus(true), 5_000);
}

void bootstrap();
