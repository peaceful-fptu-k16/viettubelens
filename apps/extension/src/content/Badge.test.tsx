// Component behaviour is covered by Playwright against YouTube DOM fixtures.
// This smoke test keeps the test suite aware of the public module.
import { describe, expect, it } from "vitest";
import { AnalysisBadge } from "./Badge";

describe("AnalysisBadge", () => {
  it("exports the badge component", () => expect(AnalysisBadge).toBeTypeOf("function"));
});
