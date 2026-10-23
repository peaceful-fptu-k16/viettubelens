// @vitest-environment jsdom

import { describe, expect, it } from "vitest";
import { isLiveCard } from "./card-visibility";

function cardWith(markup: string): { card: HTMLElement; anchor: HTMLElement } {
  const card = document.createElement("article");
  card.innerHTML = `<a id="thumbnail">Ảnh</a>${markup}`;
  return { card, anchor: card.querySelector<HTMLElement>("#thumbnail")! };
}

describe("isLiveCard", () => {
  it("recognizes current YouTube live overlay variants", () => {
    const overlay = cardWith(
      '<ytd-thumbnail-overlay-time-status-renderer overlay-style="LIVE" />',
    );
    const localized = cardWith(
      '<span class="badge-shape-wiz__text">TRỰC TIẾP</span>',
    );
    expect(isLiveCard(overlay.card, overlay.anchor)).toBe(true);
    expect(isLiveCard(localized.card, localized.anchor)).toBe(true);
  });

  it("does not classify a normal video whose title contains live", () => {
    const normal = cardWith("<h3>Live session đã ghi hình</h3>");
    expect(isLiveCard(normal.card, normal.anchor)).toBe(false);
  });
});
