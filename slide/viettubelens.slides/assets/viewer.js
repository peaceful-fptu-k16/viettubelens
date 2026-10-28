const manifest = await fetch("manifest.json").then((response) => response.json());
const prettyTitles = ["VietTubeLens","Bối cảnh","Vấn đề người dùng","Giải pháp","Signal Prism","Trải nghiệm","Giao diện","Trạng thái","Kiến trúc","Luồng dữ liệu","Dữ liệu","Phân bố nhãn","Mô hình","Huấn luyện","Kết quả","Độ tin cậy","Lộ trình","Cảm ơn"];

const els = {
  app: document.querySelector("#app"),
  frames: [document.querySelector("#slide-frame-a"), document.querySelector("#slide-frame-b")],
  stage: document.querySelector("#stage"), stageRegion: document.querySelector("#stage-region"),
  current: document.querySelector("#current-number"), total: document.querySelector("#total-number"), chapter: document.querySelector("#chapter"), progress: document.querySelector("#progress-bar"),
  notesPanel: document.querySelector("#notes-panel"), notesTitle: document.querySelector("#notes-title"), notesContent: document.querySelector("#notes-content"), nextTitle: document.querySelector("#next-title"),
  overview: document.querySelector("#overview"), overviewGrid: document.querySelector("#overview-grid"), help: document.querySelector("#help"), laser: document.querySelector("#laser-dot"),
  timerValue: document.querySelector("#timer-value"), timerButton: document.querySelector("[data-action='timer']")
};

let index = Math.max(0, Math.min(manifest.playlist.length - 1, Number(location.hash.match(/\d+/)?.[0] || 1) - 1));
let activeSlot = 0;
let transitionToken = 0;
let notesOpen = new URLSearchParams(location.search).has("presenter");
let laserActive = false;
let reducedMotion = localStorage.getItem("vtl-reduced-motion") === "1" || matchMedia("(prefers-reduced-motion: reduce)").matches;
let startX = 0;
let timerStart = 0;
let timerInterval = 0;
let focusTimer = 0;
const channel = "BroadcastChannel" in window ? new BroadcastChannel("viettubelens-slides") : null;

els.total.textContent = String(manifest.playlist.length).padStart(2, "0");
if (notesOpen) els.app.classList.add("presenter");

function fitStage() {
  const scale = els.stage.clientWidth / 1920;
  els.frames.forEach((frame) => frame.style.transform = `scale(${scale})`);
}

async function loadNotes(i) {
  const html = await fetch(`slides/${manifest.playlist[i]}`).then((r) => r.text());
  const doc = new DOMParser().parseFromString(html, "text/html");
  els.notesContent.innerHTML = doc.querySelector("template[data-slide-notes]")?.innerHTML || "<p>Không có ghi chú cho slide này.</p>";
  els.notesTitle.textContent = prettyTitles[i];
  els.nextTitle.textContent = prettyTitles[Math.min(i + 1, prettyTitles.length - 1)];
}

function signalFrame(frame, type) {
  frame.contentWindow?.postMessage({ type, reducedMotion }, "*");
  frame.contentDocument?.documentElement.classList.toggle("reduce-motion", reducedMotion);
}

function applyMotionSetting() {
  els.app.classList.toggle("reduce-motion", reducedMotion);
  document.querySelector("[data-action='motion']")?.classList.toggle("active", reducedMotion);
  els.frames.forEach((frame) => signalFrame(frame, "vtl:motion"));
}

function syncMeta() {
  els.current.textContent = String(index + 1).padStart(2, "0");
  els.chapter.textContent = prettyTitles[index];
  els.progress.style.width = `${((index + 1) / manifest.playlist.length) * 100}%`;
  history.replaceState(null, "", `#/` + (index + 1));
  document.title = `${String(index + 1).padStart(2,"0")} · ${prettyTitles[index]} · VietTubeLens`;
  document.querySelectorAll(".thumb").forEach((el, thumbIndex) => el.classList.toggle("active", thumbIndex === index));
  loadNotes(index);
}

function update(nextIndex, { broadcast = true, initial = false } = {}) {
  const bounded = Math.max(0, Math.min(manifest.playlist.length - 1, nextIndex));
  const direction = bounded >= index ? "next" : "prev";
  index = bounded;
  syncMeta();
  if (broadcast) channel?.postMessage({ type: "navigate", index });
  preload(index + 1); preload(index - 1);

  const token = ++transitionToken;
  if (initial) {
    const frame = els.frames[activeSlot];
    frame.src = `slides/${manifest.playlist[index]}?v=11`;
    frame.onload = () => { if (token !== transitionToken) return; fitStage(); signalFrame(frame, "vtl:replay"); };
    return;
  }

  const outgoing = els.frames[activeSlot];
  const incomingSlot = activeSlot === 0 ? 1 : 0;
  const incoming = els.frames[incomingSlot];
  incoming.className = "slide-frame";
  incoming.src = `slides/${manifest.playlist[index]}?v=11`;
  incoming.onload = () => {
    if (token !== transitionToken) return;
    fitStage();
    els.stage.classList.remove("transition-next", "transition-prev");
    void els.stage.offsetWidth;
    els.stage.classList.add(`transition-${direction}`);
    outgoing.classList.remove("active"); outgoing.classList.add("outgoing");
    incoming.classList.add("incoming");
    signalFrame(incoming, "vtl:replay");
    window.setTimeout(() => {
      if (token !== transitionToken) return;
      outgoing.className = "slide-frame";
      incoming.className = "slide-frame active";
      els.stage.classList.remove("transition-next", "transition-prev");
      activeSlot = incomingSlot;
      signalFrame(incoming, "vtl:counts");
    }, reducedMotion ? 40 : 620);
  };
}

function preload(i) {
  if (i < 0 || i >= manifest.playlist.length) return;
  const href = `slides/${manifest.playlist[i]}`;
  if (document.head.querySelector(`link[href="${href}"]`)) return;
  const link = document.createElement("link"); link.rel = "prefetch"; link.href = href; link.as = "document"; document.head.append(link);
}

function navigate(delta) { update(index + delta); }
function replayMotion() { signalFrame(els.frames[activeSlot], "vtl:replay"); }
function toggleNotes(force) {
  notesOpen = force ?? !notesOpen;
  els.notesPanel.classList.toggle("open", notesOpen);
  els.notesPanel.setAttribute("aria-hidden", String(!notesOpen));
  document.querySelector("[data-action='notes']")?.classList.toggle("active", notesOpen);
  requestAnimationFrame(fitStage);
  window.setTimeout(fitStage, 320);
}
function toggleOverview() { els.overview.open ? els.overview.close() : els.overview.showModal(); }
function toggleLaser() {
  laserActive = !laserActive; els.stageRegion.classList.toggle("laser-active", laserActive);
  document.querySelector("[data-action='laser']")?.classList.toggle("active", laserActive);
}
function toggleMotion() {
  reducedMotion = !reducedMotion; localStorage.setItem("vtl-reduced-motion", reducedMotion ? "1" : "0"); applyMotionSetting(); replayMotion();
}
async function toggleFullscreen() { document.fullscreenElement ? await document.exitFullscreen() : await document.documentElement.requestFullscreen(); }
function openPresenter() { window.open(`${location.pathname}?presenter=1#/` + (index + 1), "viettubelens-presenter", "popup,width=1440,height=900"); }
function toggleTimer() {
  if (timerInterval) { clearInterval(timerInterval); timerInterval = 0; els.timerButton.textContent = "Tiếp tục"; return; }
  timerStart = timerStart ? Date.now() - Number(els.timerValue.dataset.elapsed || 0) : Date.now();
  timerInterval = window.setInterval(renderTimer, 500); els.timerButton.textContent = "Tạm dừng"; renderTimer();
}
function renderTimer() {
  const elapsed = Date.now() - timerStart; els.timerValue.dataset.elapsed = String(elapsed);
  const seconds = Math.floor(elapsed / 1000); els.timerValue.textContent = `${String(Math.floor(seconds/60)).padStart(2,"0")}:${String(seconds%60).padStart(2,"0")}`;
}
function showHelp(force) { const open = force ?? !els.help.classList.contains("open"); els.help.classList.toggle("open", open); els.help.setAttribute("aria-hidden", String(!open)); }
function wakeChrome() {
  els.app.classList.remove("focus-mode"); clearTimeout(focusTimer);
  if (document.fullscreenElement && !notesOpen) focusTimer = window.setTimeout(() => els.app.classList.add("focus-mode"), 2200);
}

manifest.playlist.forEach((file, i) => {
  const button = document.createElement("button"); button.type = "button"; button.className = "thumb"; button.dataset.index = String(i);
  button.innerHTML = `<img src="assets/thumbs/${file.replace(".html", ".png")}" alt="Xem trước slide ${i + 1}: ${prettyTitles[i]}" loading="lazy"><span class="thumb-copy"><b>${String(i + 1).padStart(2,"0")}</b><span>${prettyTitles[i]}</span></span>`;
  button.addEventListener("click", () => { update(i); els.overview.close(); }); els.overviewGrid.append(button);
});

document.addEventListener("click", (event) => {
  const action = event.target.closest("[data-action]")?.dataset.action;
  ({prev:()=>navigate(-1),next:()=>navigate(1),overview:toggleOverview,"close-overview":()=>els.overview.close(),notes:()=>toggleNotes(),laser:toggleLaser,motion:toggleMotion,replay:replayMotion,presenter:openPresenter,fullscreen:toggleFullscreen,timer:toggleTimer,"close-help":()=>showHelp(false)})[action]?.();
});
document.addEventListener("keydown", (event) => {
  if (event.target.matches("input,textarea,select")) return;
  const key = event.key.toLowerCase();
  if (["arrowright","pagedown"," "].includes(key)) { event.preventDefault(); navigate(1); }
  else if (["arrowleft","pageup","backspace"].includes(key)) { event.preventDefault(); navigate(-1); }
  else if (key === "home") update(0); else if (key === "end") update(manifest.playlist.length - 1);
  else if (key === "o") toggleOverview(); else if (key === "n") toggleNotes(); else if (key === "f") toggleFullscreen();
  else if (key === "l") toggleLaser(); else if (key === "m") toggleMotion(); else if (key === "r") replayMotion(); else if (key === "p") openPresenter();
  else if (key === "?") showHelp(); else if (key === "escape") { if (els.overview.open) els.overview.close(); else showHelp(false); }
});
window.addEventListener("resize", fitStage);
new ResizeObserver(fitStage).observe(els.stage);
window.addEventListener("hashchange", () => { const requested = Number(location.hash.match(/\d+/)?.[0]); if (requested && requested - 1 !== index) update(requested - 1); });
els.stageRegion.addEventListener("pointerdown", (event) => { startX = event.clientX; });
els.stageRegion.addEventListener("pointerup", (event) => { const delta = event.clientX - startX; if (Math.abs(delta) > 72) navigate(delta < 0 ? 1 : -1); });
els.stageRegion.addEventListener("pointermove", (event) => { if (!laserActive) return; const r = els.stageRegion.getBoundingClientRect(); els.laser.style.left = `${event.clientX-r.left}px`; els.laser.style.top = `${event.clientY-r.top}px`; });
document.addEventListener("fullscreenchange", wakeChrome); document.addEventListener("mousemove", wakeChrome);
channel?.addEventListener("message", (event) => { if (event.data?.type === "navigate" && event.data.index !== index) update(event.data.index, { broadcast:false }); });

toggleNotes(notesOpen); applyMotionSetting(); update(index, {broadcast:false, initial:true}); fitStage();
if (!sessionStorage.getItem("vtl-help-seen") && !notesOpen) { window.setTimeout(() => showHelp(true), 650); sessionStorage.setItem("vtl-help-seen", "1"); }
