import { describe, expect, it, vi } from "vitest";
import { batchAnalyze } from "./api";

describe("batchAnalyze", () => {
  it("normalizes the base URL and sends the bounded request", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    await batchAnalyze("http://127.0.0.1:8000/", ["abc123xyz00"]);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/analysis/batch",
      expect.objectContaining({ method: "POST" }),
    );
    fetchMock.mockRestore();
  });
});
