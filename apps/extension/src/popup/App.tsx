import { Activity, Check, Database, Eye, EyeOff, FlaskConical, Gauge, Info, LoaderCircle, Play, RefreshCcw, Server, Settings2, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { getSettings, saveSettings } from "../shared/settings";
import type { ContentStatus, ExtensionSettings, WorkerRequest } from "../shared/types";

function BrandMark({ size = 30 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M24.5 22.4A11.2 11.2 0 1 1 26.6 19l.9 6.2-5-2.9" stroke="url(#p)" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round"/><path d="m10.5 14.5 4.1 3.7 7-7" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round"/><defs><linearGradient id="p" x1="5" y1="5" x2="27" y2="27"><stop stopColor="#7C5CFC"/><stop offset=".52" stopColor="#22D3EE"/><stop offset="1" stopColor="#A3E635"/></linearGradient></defs></svg>;
}

async function send<T>(message: WorkerRequest): Promise<T> {
  if (typeof chrome === "undefined" || !chrome.runtime?.sendMessage) {
    throw new Error("Preview web · mở extension để kết nối backend");
  }
  const response = await chrome.runtime.sendMessage(message);
  if (!response?.ok) throw new Error(response?.error ?? "Không thể kết nối");
  return response.data as T;
}

function Toggle({ checked, onChange, label, description, icon }: { checked: boolean; onChange: (value: boolean) => void; label: string; description: string; icon: React.ReactNode }) {
  return <label className="setting-row"><span className="setting-icon">{icon}</span><span className="setting-copy"><strong>{label}</strong><small>{description}</small></span><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)}/><span className="switch"><span/></span></label>;
}

export function App() {
  const [settings, setSettings] = useState<ExtensionSettings | null>(null);
  const [tab, setTab] = useState<"home" | "settings" | "about">("home");
  const [health, setHealth] = useState<{ status: string; model_version: string; demo_mode: boolean } | null>(null);
  const [contentStatus, setContentStatus] = useState<ContentStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const check = async () => {
    setChecking(true); setError(null);
    try { setHealth(await send({ type: "HEALTH_CHECK" })); } catch (cause) { setHealth(null); setError(cause instanceof Error ? cause.message : "Không thể kết nối backend"); }
    try { setContentStatus(await send({ type: "GET_CONTENT_STATUS" })); } catch { setContentStatus(null); }
    finally { setChecking(false); }
  };
  useEffect(() => { void getSettings().then(setSettings); void check(); }, []);
  const update = async (value: Partial<ExtensionSettings>) => { const next = await saveSettings(value); setSettings(next); };
  const notify = (message: string) => { setToast(message); window.setTimeout(() => setToast(null), 1800); };
  const configureBackend = async () => {
    if (!settings) return;
    try {
      const url = new URL(settings.backendUrl);
      if (url.protocol === "https:" && typeof chrome !== "undefined" && chrome.permissions?.request) {
        const granted = await chrome.permissions.request({ origins: [`${url.origin}/*`] });
        if (!granted) { setError("Cần quyền truy cập backend đã chọn"); return; }
      }
      await saveSettings({ backendUrl: settings.backendUrl });
      await check();
    } catch { setError("Địa chỉ backend không hợp lệ"); }
  };

  if (!settings) return <div className="boot"><LoaderCircle className="spin"/><span>Đang khởi động Lens…</span></div>;
  return (
    <main className="app-shell">
      <div className="ambient ambient-one"/><div className="ambient ambient-two"/>
      <header className="topbar"><div className="brand"><span className="brand-tile"><BrandMark/></span><span><strong>VietTubeLens</strong><small>Community intelligence</small></span></div><span className={`status-dot ${health ? "online" : "offline"}`} title={health ? "Backend online" : "Backend offline"}/></header>
      <nav className="tabs" aria-label="Điều hướng"><button className={tab === "home" ? "active" : ""} onClick={() => setTab("home")}><Activity size={15}/>Tổng quan</button><button className={tab === "settings" ? "active" : ""} onClick={() => setTab("settings")}><Settings2 size={15}/>Cài đặt</button><button className={tab === "about" ? "active" : ""} onClick={() => setTab("about")}><Info size={15}/>Giới thiệu</button></nav>

      {tab === "home" && <section className="view">
        <div className="hero-card"><div className="eyebrow"><Sparkles size={13}/> SIGNAL PRISM</div><h1>Hiểu cộng đồng<br/><span>trước khi xem.</span></h1><p>Phản ứng, độ độc hại và bằng chứng — ngay trên từng video card.</p><div className="hero-orbit"><BrandMark size={42}/><i/><i/><i/></div></div>
        <div className={`connection-card ${health ? "connected" : "disconnected"}`}>
          <div className="connection-icon">{checking ? <LoaderCircle className="spin"/> : health ? <Server/> : <Server/>}</div>
          <div><small>BACKEND</small><strong>{checking ? "Đang kiểm tra…" : health ? "Sẵn sàng phân tích" : "Chưa kết nối"}</strong><span>{health ? `${health.model_version}${health.demo_mode ? " · Demo" : " · YouTube"}` : error ?? settings.backendUrl}</span></div>
          <button onClick={() => void check()} aria-label="Kiểm tra lại"><RefreshCcw size={15}/></button>
        </div>
        <div className={`page-status ${contentStatus?.active ? "active" : "inactive"}`}>
          <span className="page-status-icon"><Eye size={15}/></span>
          <span><small>TRANG YOUTUBE</small><strong>{contentStatus?.active ? `${contentStatus.badgesMounted} badge đang hiển thị` : "Content script chưa hoạt động"}</strong><em>{contentStatus?.active ? `${contentStatus.detectedCards} liên kết · ${contentStatus.visibleCards} video trong vùng nhìn` : "Reload extension, sau đó làm mới YouTube"}</em></span>
        </div>
        {health?.demo_mode && <div className="demo-banner"><FlaskConical size={16}/><span><strong>Chế độ demo</strong>Dữ liệu mô phỏng được dùng khi chưa có YouTube API key.</span></div>}
        <div className="quick-grid"><div><span className="quick-icon violet"><Eye size={18}/></span><small>Badge</small><strong>{settings.enabled ? "Đang bật" : "Đã tắt"}</strong></div><div><span className="quick-icon cyan"><Gauge size={18}/></span><small>Tối đa</small><strong>{settings.maxCards} video</strong></div><div><span className="quick-icon lime"><ShieldCheck size={18}/></span><small>Toxicity</small><strong>{settings.showToxicity ? "Hiển thị" : "Đã ẩn"}</strong></div></div>
        <button className="primary-action" onClick={async () => { if (typeof chrome !== "undefined" && chrome.tabs?.query) { const [active] = await chrome.tabs.query({ active: true, currentWindow: true }); if (active?.id) { await chrome.tabs.reload(active.id); window.close(); } } }}><Play size={16} fill="currentColor"/>Làm mới trang YouTube</button>
      </section>}

      {tab === "settings" && <section className="view settings-view">
        <div className="section-title"><span>Cài đặt hiển thị</span><small>Thay đổi được áp dụng ngay</small></div>
        <div className="settings-card">
          <Toggle checked={settings.enabled} onChange={(enabled) => void update({ enabled })} label="Hiển thị Lens Badge" description="Phân tích video trong vùng nhìn thấy" icon={settings.enabled ? <Eye size={17}/> : <EyeOff size={17}/>}/>
          <Toggle checked={settings.showToxicity} onChange={(showToxicity) => void update({ showToxicity })} label="Chỉ số độc hại" description="Hiện tỷ lệ bình luận có dấu hiệu độc hại" icon={<ShieldCheck size={17}/>}/>
          <Toggle checked={settings.animations} onChange={(animations) => void update({ animations })} label="Hiệu ứng chuyển động" description="Prism sweep và chuyển cảnh mềm" icon={<Sparkles size={17}/>}/>
        </div>
        <div className="section-title compact"><span>Số video theo vùng nhìn</span><strong>{settings.maxCards}</strong></div>
        <input className="range" type="range" min="3" max="12" value={settings.maxCards} onChange={(event) => void update({ maxCards: Number(event.target.value) })}/>
        <label className="field-label">Địa chỉ backend<input value={settings.backendUrl} spellCheck={false} onChange={(event) => setSettings({ ...settings, backendUrl: event.target.value })}/></label>
        <div className="button-row"><button className="secondary-action" onClick={() => void configureBackend()}><RefreshCcw size={15}/>Lưu & kiểm tra</button><button className="secondary-action" onClick={async () => { try { await send({ type: "CLEAR_CACHE" }); notify("Đã xóa cache backend"); } catch { notify("Không thể xóa cache"); } }}><Database size={15}/>Xóa cache</button></div>
      </section>}

      {tab === "about" && <section className="view about-view"><div className="about-mark"><BrandMark size={58}/></div><h2>VietTubeLens</h2><p className="version">Signal Prism · v0.2.1</p><p>VietTubeLens tổng hợp phản ứng từ một mẫu bình luận công khai. Kết quả không đại diện cho toàn bộ người xem và không phải đánh giá chất lượng khách quan của video.</p><div className="principles"><div><Check size={15}/><span><strong>Có bằng chứng</strong>Hiển thị bình luận đại diện</span></div><div><Check size={15}/><span><strong>Biết từ chối</strong>Không kết luận khi dữ liệu yếu</span></div><div><Check size={15}/><span><strong>Tôn trọng lựa chọn</strong>Không tự động ẩn video</span></div></div></section>}
      {toast && <div className="toast"><Check size={14}/>{toast}</div>}
    </main>
  );
}
