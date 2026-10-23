const LIVE_INDICATOR_SELECTOR = [
  'ytd-thumbnail-overlay-time-status-renderer[overlay-style="LIVE"]',
  '[badge-style-type="BADGE_STYLE_TYPE_LIVE_NOW"]',
  '[aria-label="LIVE"]',
  '[aria-label="Trực tiếp"]',
  '.yt-badge-shape--live',
].join(",");

const LIVE_TEXT_SELECTOR = [
  "ytd-thumbnail-overlay-time-status-renderer",
  "yt-thumbnail-overlay-badge-view-model",
  ".badge-shape-wiz__text",
].join(",");

export function isLiveCard(card: Element, anchor: HTMLElement): boolean {
  if (card.querySelector(LIVE_INDICATOR_SELECTOR) || anchor.querySelector(LIVE_INDICATOR_SELECTOR)) {
    return true;
  }
  return Array.from(card.querySelectorAll<HTMLElement>(LIVE_TEXT_SELECTOR)).some((indicator) => {
    const label = `${indicator.textContent ?? ""} ${indicator.getAttribute("aria-label") ?? ""}`
      .trim()
      .toLocaleUpperCase("vi-VN");
    return /(^|\s)LIVE(\s|$)/u.test(label) || label.includes("TRỰC TIẾP");
  });
}
