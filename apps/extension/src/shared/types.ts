export type AnalysisStatus = "ready" | "queued" | "insufficient_data" | "unavailable" | "error";
export type Sentiment = "positive" | "neutral" | "negative";
export type ConfidenceTier = "high" | "medium" | "low";

export interface SentimentDistribution {
  positive: number;
  neutral: number;
  negative: number;
}

export interface Evidence {
  comment_id: string;
  text: string;
  sentiment: Sentiment;
  score: number;
  url?: string | null;
}

export interface AnalysisResult {
  video_id: string;
  status: AnalysisStatus;
  sample_size: number;
  relevant_count: number;
  sentiment_distribution: SentimentDistribution;
  toxicity_rate: number;
  overall_reaction: Sentiment | "mixed";
  confidence_score: number;
  confidence_tier: ConfidenceTier;
  abstained: boolean;
  abstention_reasons: string[];
  evidence: Evidence[];
  opinion_pattern?: "consensus" | "balanced" | "polarized" | "uncertain";
  polarization_score?: number;
  minority_evidence?: Evidence | null;
  cache_hit: boolean;
  model_version: string;
  updated_at: string;
  source: "youtube" | "demo";
  message?: string | null;
}

export interface BatchResponse { items: AnalysisResult[]; }

export interface ExtensionSettings {
  enabled: boolean;
  showToxicity: boolean;
  animations: boolean;
  maxCards: number;
  backendUrl: string;
}

export interface ContentStatus {
  active: boolean;
  detectedCards: number;
  visibleCards: number;
  badgesMounted: number;
  updatedAt: number;
  error?: string;
}

export type WorkerRequest =
  | { type: "BATCH_ANALYZE"; videoIds: string[] }
  | { type: "GET_ANALYSIS"; videoId: string }
  | { type: "GET_ANALYSIS_BATCH"; videoIds: string[] }
  | { type: "HEALTH_CHECK" }
  | { type: "CLEAR_CACHE" }
  | { type: "REPORT_CONTENT_STATUS"; status: ContentStatus }
  | { type: "GET_CONTENT_STATUS" };
