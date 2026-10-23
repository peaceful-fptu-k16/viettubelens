import { createRoot } from "react-dom/client";
import { AnalysisBadge } from "../content/Badge";
import badgeStyles from "../content/content.css?inline";
import type { AnalysisResult } from "../shared/types";
import "./showcase.css";

const sample: AnalysisResult = {
  video_id: "showcase01",
  status: "ready",
  sample_size: 30,
  relevant_count: 26,
  sentiment_distribution: { positive: 0.48, neutral: 0.13, negative: 0.39 },
  toxicity_rate: 0.04,
  overall_reaction: "mixed",
  confidence_score: 0.86,
  confidence_tier: "high",
  abstained: false,
  abstention_reasons: [],
  evidence: [
    { comment_id: "1", text: "Thông tin ngắn gọn, dễ hiểu và đúng trọng tâm.", sentiment: "positive", score: 0.94 },
    { comment_id: "2", text: "Phần hình ảnh trực quan nên mình theo dõi rất dễ.", sentiment: "positive", score: 0.88 },
    { comment_id: "3", text: "Nội dung ổn nhưng tiêu đề hơi phóng đại.", sentiment: "negative", score: 0.8 },
  ],
  opinion_pattern: "polarized",
  polarization_score: 0.68,
  minority_evidence: {
    comment_id: "minority-1",
    text: "Lập luận chính vẫn thiếu nguồn để mình có thể đồng ý hoàn toàn.",
    sentiment: "negative",
    score: 0.84,
  },
  cache_hit: true,
  model_version: "signal-prism-heuristic-v1",
  updated_at: new Date().toISOString(),
  source: "demo",
};

const stage = document.getElementById("badge-stage") ?? (() => {
  const host = document.createElement("div");
  host.id = "badge-stage";
  document.getElementById("showcase")?.append(host);
  return host;
})();
const shadow = stage.attachShadow({ mode: "open" });
const style = document.createElement("style");
style.textContent = badgeStyles;
const mount = document.createElement("div");
mount.className = "vtl-mount";
shadow.append(style, mount);
createRoot(mount).render(<AnalysisBadge result={sample} showToxicity animations index={0}/>);
