import { AlertTriangle, ExternalLink, FlaskConical, MessageSquareText, ShieldCheck, Sparkles, Split, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import type { AnalysisResult } from "../shared/types";
import { LensLogo } from "./Logo";

interface BadgeProps {
  result: AnalysisResult;
  showToxicity: boolean;
  animations: boolean;
  index: number;
  popoverOffset?: number;
  popoverAbove?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

const sentimentLabel = { positive: "Tích cực", neutral: "Trung lập", negative: "Tiêu cực", mixed: "Trái chiều" };

function percent(value: number): string { return `${Math.round(value * 100)}%`; }

function timeLabel(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "Vừa cập nhật" : `Cập nhật ${date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}`;
}

function LoadingBadge({ status }: { status: AnalysisResult["status"] }) {
  const label = status === "queued" ? "Đang phân tích" : "Đang kết nối";
  return <div className="vtl-badge vtl-loading" role="status"><LensLogo size={22}/><span className="vtl-shimmer"/><span>{label}</span></div>;
}

function StateBadge({ result }: { result: AnalysisResult }) {
  const isError = result.status === "error" || result.status === "unavailable";
  return (
    <div className={`vtl-badge vtl-state ${isError ? "is-error" : "is-muted"}`} role="status" title={result.message ?? undefined}>
      {isError ? <AlertTriangle size={16}/> : <MessageSquareText size={16}/>}<span>{isError ? "Chưa thể phân tích" : "Chưa đủ dữ liệu"}</span>
    </div>
  );
}

function Distribution({ result }: { result: AnalysisResult }) {
  const values = result.sentiment_distribution;
  return (
    <div className="vtl-distribution-block">
      <div className="vtl-section-heading"><span>Phân bố phản ứng</span><span>{result.relevant_count}/{result.sample_size} phù hợp</span></div>
      <div className="vtl-distribution" aria-label="Phân bố cảm xúc">
        <span className="positive" style={{ width: percent(values.positive) }}/>
        <span className="neutral" style={{ width: percent(values.neutral) }}/>
        <span className="negative" style={{ width: percent(values.negative) }}/>
      </div>
      <div className="vtl-legend">
        <span><i className="positive"/>Tích cực {percent(values.positive)}</span>
        <span><i className="neutral"/>Trung lập {percent(values.neutral)}</span>
        <span><i className="negative"/>Tiêu cực {percent(values.negative)}</span>
      </div>
    </div>
  );
}

function OpinionInsight({ result }: { result: AnalysisResult }) {
  if (!result.opinion_pattern || result.opinion_pattern === "uncertain") return null;
  const content = {
    consensus: ["Đồng thuận rõ", "Phần lớn mẫu bình luận nghiêng về cùng một phản ứng."],
    balanced: ["Nhiều góc nhìn", "Mẫu bình luận chưa nghiêng hẳn về một phía."],
    polarized: ["Ý kiến phân cực", "Hai luồng tích cực và tiêu cực cùng hiện diện rõ."],
  }[result.opinion_pattern];
  if (!content) return null;
  return <div className={`vtl-opinion ${result.opinion_pattern}`}>
    <span><Split size={16}/></span>
    <div><strong>{content[0]}</strong><p>{content[1]}</p></div>
    {result.opinion_pattern === "polarized" && <em>{percent(result.polarization_score ?? 0)} phân cực</em>}
  </div>;
}

function DetailPopover({ result, onClose, showToxicity, id }: { result: AnalysisResult; onClose: () => void; showToxicity: boolean; id: string }) {
  const positive = Math.round(result.sentiment_distribution.positive * 100);
  return (
    <section id={id} className="vtl-popover" role="dialog" aria-label="Chi tiết phân tích VietTubeLens">
      <header className="vtl-popover-header">
        <div className="vtl-brand"><span className="vtl-logo-tile"><LensLogo size={25}/></span><span><strong>VietTubeLens</strong><small>{timeLabel(result.updated_at)} · {result.cache_hit ? "Từ bộ nhớ đệm" : "Phân tích mới"}</small></span></div>
        <button className="vtl-icon-button" onClick={onClose} aria-label="Đóng"><X size={17}/></button>
      </header>
      {result.source === "demo" && <div className="vtl-demo-note"><FlaskConical size={14}/><span>Dữ liệu mô phỏng để xem trước giao diện</span></div>}
      <div className="vtl-hero">
        <div className="vtl-score-ring" style={{ "--score": `${positive * 3.6}deg` } as React.CSSProperties}>
          <div><strong>{positive}</strong><small>/100</small></div>
        </div>
        <div className="vtl-hero-copy"><span className={`vtl-reaction ${result.overall_reaction}`}>{sentimentLabel[result.overall_reaction]}</span><h2>Phản ứng cộng đồng</h2><p>Kết quả tổng hợp từ các bình luận phù hợp, không phải điểm chất lượng video.</p></div>
      </div>
      <Distribution result={result}/>
      <OpinionInsight result={result}/>
      <div className="vtl-metrics">
        {showToxicity && <div><span className="vtl-metric-icon toxicity"><ShieldCheck size={16}/></span><span><small>Độc hại</small><strong>{percent(result.toxicity_rate)}</strong></span></div>}
        <div><span className="vtl-metric-icon confidence"><Sparkles size={16}/></span><span><small>Độ tin cậy</small><strong>{percent(result.confidence_score)} · {result.confidence_tier === "high" ? "Cao" : result.confidence_tier === "medium" ? "Vừa" : "Thấp"}</strong></span></div>
      </div>
      {result.abstained ? (
        <div className="vtl-abstain"><AlertTriangle size={18}/><div><strong>Chưa đưa ra kết luận</strong>{result.abstention_reasons.map((reason) => <p key={reason}>{reason}</p>)}</div></div>
      ) : result.evidence.length > 0 && (
        <div className="vtl-evidence-section">
          <div className="vtl-section-heading"><span>Bình luận đại diện</span><span>{result.evidence.length} bằng chứng</span></div>
          <div className="vtl-evidence-list">{result.evidence.slice(0, 3).map((item) => (
            <article className="vtl-evidence" key={item.comment_id}>
              <div><span className={`vtl-chip ${item.sentiment}`}>{sentimentLabel[item.sentiment]}</span>{item.url && <a href={item.url} target="_blank" rel="noreferrer" aria-label="Mở bình luận"><ExternalLink size={14}/></a>}</div>
              <p>“{item.text}”</p>
            </article>
          ))}</div>
        </div>
      )}
      {!result.abstained && result.minority_evidence && <div className="vtl-minority">
        <div className="vtl-section-heading"><span>Góc nhìn thiểu số</span><span>Đáng chú ý</span></div>
        <article className="vtl-evidence">
          <div><span className={`vtl-chip ${result.minority_evidence.sentiment}`}>{sentimentLabel[result.minority_evidence.sentiment]}</span>{result.minority_evidence.url && <a href={result.minority_evidence.url} target="_blank" rel="noreferrer" aria-label="Mở bình luận thiểu số"><ExternalLink size={14}/></a>}</div>
          <p>“{result.minority_evidence.text}”</p>
        </article>
      </div>}
      <footer className="vtl-footer"><button type="button">Dự đoán chưa đúng</button><span>AI có thể mắc lỗi</span></footer>
    </section>
  );
}

export function AnalysisBadge({ result, showToxicity, animations, index, popoverOffset = 0, popoverAbove = false, open: controlledOpen, onOpenChange }: BadgeProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const open = controlledOpen ?? internalOpen;
  const setOpen = (next: boolean | ((current: boolean) => boolean)) => {
    const value = typeof next === "function" ? next(open) : next;
    if (controlledOpen === undefined) setInternalOpen(value);
    onOpenChange?.(value);
  };
  const rootRef = useRef<HTMLDivElement>(null);
  const popoverId = useId();
  useEffect(() => {
    if (!open) return;
    const listener = (event: MouseEvent) => {
      const root = rootRef.current;
      if (root && !event.composedPath().includes(root)) setOpen(false);
    };
    document.addEventListener("pointerdown", listener, true);
    return () => document.removeEventListener("pointerdown", listener, true);
  }, [open]);

  if (result.status === "queued") return <LoadingBadge status={result.status}/>;
  if (result.status !== "ready") return <StateBadge result={result}/>;
  const positive = Math.round(result.sentiment_distribution.positive * 100);
  return (
    <div ref={rootRef} className={`vtl-root ${animations ? "with-motion" : "no-motion"} ${popoverAbove ? "popover-above" : ""}`} style={{ "--delay": `${index * 35}ms`, "--popover-offset": `${popoverOffset}px` } as React.CSSProperties}>
      <button className="vtl-badge vtl-ready" onClick={() => setOpen((value) => !value)} aria-expanded={open} aria-controls={popoverId}>
        <span className="vtl-compact-mark"><LensLogo size={23}/></span>
        <strong>{positive}<small>%</small></strong>
        <span className="vtl-primary-label">tích cực</span>
        <span className="vtl-expanded-metrics">
          {showToxicity && <span><i className="vtl-dot toxicity"/>{Math.round(result.toxicity_rate * 100)}% độc hại</span>}
          <span><i className={`vtl-dot confidence ${result.confidence_tier}`}/>{Math.round(result.confidence_score * 100)}% tin cậy</span>
        </span>
        <span className="vtl-confidence-ring" style={{ "--score": `${result.confidence_score * 360}deg` } as React.CSSProperties}/>
        <span className="vtl-sweep"/>
      </button>
      {open && <DetailPopover id={popoverId} result={result} onClose={() => setOpen(false)} showToxicity={showToxicity}/>}
    </div>
  );
}
