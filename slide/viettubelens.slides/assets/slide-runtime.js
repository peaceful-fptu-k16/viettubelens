const root = document.documentElement;
const container = document.querySelector(".slide-container");
let running = [];
let countToken = 0;

const reduced = () => new URLSearchParams(location.search).has("static") || root.classList.contains("reduce-motion") || matchMedia("(prefers-reduced-motion: reduce)").matches;
const slideNumber = Number(container?.dataset.screenLabel?.match(/^\d+/)?.[0] || 0);

function cancelAll() {
  running.forEach((animation) => animation.cancel()); running = [];
  countToken += 1;
  document.querySelectorAll(".runtime-prism-sweep,.runtime-signal-dot,.motion-title-accent").forEach((node) => node.remove());
}

function animate(node, keyframes, options) {
  const animation = node.animate(keyframes, { fill: "both", easing: "cubic-bezier(.2,.82,.2,1)", ...options });
  running.push(animation); return animation;
}

function numberParts(text) {
  const clean = text.trim();
  if (/^0,\d{3}$/.test(clean)) return { value:Number(clean.replace(",",".")), decimals:3, suffix:"", format:"decimal" };
  if (/^\d{1,2}\.\d{3}$/.test(clean)) return { value:Number(clean.replace(".","")), decimals:0, suffix:"", format:"thousand" };
  if (/^\d{1,3}$/.test(clean)) return { value:Number(clean), decimals:0, suffix:"", format:"integer" };
  return null;
}

function countUp(node, delay = 60, duration = 480) {
  const parsed = numberParts(node.textContent); if (!parsed) return;
  const original = node.textContent.trim(); const token = countToken;
  const start = performance.now() + delay;
  const step = (now) => {
    if (token !== countToken) return;
    const progress = Math.max(0, Math.min(1, (now - start) / duration));
    const eased = 1 - Math.pow(1 - progress, 3); const value = parsed.value * eased;
    if (parsed.format === "decimal") node.textContent = value.toFixed(parsed.decimals).replace(".", ",");
    else if (parsed.format === "thousand") node.textContent = Math.round(value).toLocaleString("vi-VN");
    else node.textContent = String(Math.round(value));
    if (progress < 1) requestAnimationFrame(step); else node.textContent = original;
  };
  requestAnimationFrame(step);
}

function playCounts() {
  countToken += 1;
  container?.querySelectorAll("[data-count]").forEach((node,index) => countUp(node,40 + index * 45,500));
}

function animateSvg(chart, delay) {
  chart.querySelectorAll("polyline,path:not([data-flow-path]):not([data-route])").forEach((path, i) => {
    const stroke = getComputedStyle(path).stroke; if (!stroke || stroke === "none") return;
    try {
      const length = path.getTotalLength();
      path.style.strokeDasharray = String(length); path.style.strokeDashoffset = String(length);
      const a = animate(path, [{strokeDashoffset:length},{strokeDashoffset:0}], {duration:680,delay:delay+i*45});
      a.onfinish = () => { path.style.strokeDasharray = ""; path.style.strokeDashoffset = ""; };
    } catch {}
  });
  chart.querySelectorAll("rect").forEach((bar, i) => {
    bar.style.transformBox = "fill-box"; bar.style.transformOrigin = "left center";
    animate(bar, [{opacity:0,transform:"scaleX(.04)"},{opacity:1,transform:"scaleX(1)"}], {duration:520,delay:delay+120+i*35});
  });
  chart.querySelectorAll("circle").forEach((circle, i) => {
    circle.style.transformBox = "fill-box"; circle.style.transformOrigin = "center";
    animate(circle, [{opacity:0,transform:"scale(.2)"},{opacity:1,transform:"scale(1)"}], {duration:380,delay:delay+360+i*55});
  });
}

function drawPath(path, delay, duration = 520) {
  try {
    const length = path.getTotalLength();
    path.style.strokeDasharray = String(length);
    path.style.strokeDashoffset = String(length);
    const animation = animate(path,[{strokeDashoffset:length},{strokeDashoffset:0}],{duration,delay,easing:"cubic-bezier(.25,.8,.25,1)"});
    animation.onfinish = () => {
      if (path.classList.contains("route-flow")) {
        path.style.strokeDasharray = "14 12";
        path.style.strokeDashoffset = "0";
        animate(path,[{strokeDashoffset:0},{strokeDashoffset:-52}],{duration:900,delay:40,easing:"linear"});
      } else {
        path.style.strokeDasharray = "";
        path.style.strokeDashoffset = "";
      }
    };
  } catch {}
}

function playStoryFlow() {
  const paths = [...container.querySelectorAll("[data-flow-path]")];
  if (!paths.length) return;
  const start = slideNumber === 4 ? 560 : 500;
  paths.forEach((path,index) => drawPath(path,start + index * 390,500));
  container.querySelectorAll(".flow-paths circle").forEach((node,index) => animate(node,[{opacity:0,transform:"scale(.2)",transformOrigin:"center"},{opacity:1,transform:"scale(1)",transformOrigin:"center"}],{duration:260,delay:start + index * 390 + 330}));
  container.querySelectorAll("[data-reveal-step]").forEach((node) => {
    const step = Math.max(1,Number(node.dataset.revealStep || 1));
    animate(node,[{opacity:0,transform:"translateX(24px) scale(.985)"},{opacity:1,transform:"translateX(0) scale(1)"}],{duration:480,delay:start + (step - 1) * 390 + 360});
  });
}

function playArchitectureRoutes() {
  const request = [...container.querySelectorAll('[data-route="request"]')];
  const response = [...container.querySelectorAll('[data-route="response"]')];
  request.forEach((path,index) => drawPath(path,520 + index * 150,440));
  response.forEach((path,index) => drawPath(path,1500 + index * 220,600));
  container.querySelectorAll("[data-route-label]").forEach((node,index) => animate(node,[{opacity:0,transform:"translateY(8px)"},{opacity:1,transform:"translateY(0)"}],{duration:380,delay:index?1640:620}));
}

function createAccent(title) {
  if (!title || [1,18].includes(slideNumber)) return;
  const rect = title.getBoundingClientRect();
  const accent = document.createElement("div"); accent.className = "motion-title-accent";
  accent.style.left = `${Math.round(rect.left)}px`; accent.style.top = `${Math.round(rect.bottom + 12)}px`; accent.style.width = `${Math.min(170, rect.width * .28)}px`;
  container.append(accent);
  animate(accent, [{opacity:0,transform:"scaleX(0)"},{opacity:1,transform:"scaleX(1)"}], {duration:520,delay:170});
}

function play() {
  if (!container) return;
  cancelAll();
  container.querySelectorAll('[data-object="true"]').forEach((node) => {
    const style = node.getAttribute("style") || "";
    if (/background:\s*#fff(?:fff)?/i.test(style) && /border-radius/i.test(style)) node.classList.add("surface-card");
    if (/background:\s*#0b1020/i.test(style) && /border-radius/i.test(style)) node.classList.add("ink-panel");
  });
  const objects = [...container.querySelectorAll(":scope > [data-object='true']")];
  if (reduced()) { objects.forEach((node) => { node.style.opacity = ""; node.style.transform = ""; node.style.clipPath = ""; }); return; }

  const title = container.querySelector(".title") || objects.find((node) => {
    const size = Number.parseFloat(getComputedStyle(node).fontSize); return node.dataset.objectType === "textbox" && size >= 54 && node.getBoundingClientRect().top < 300;
  });
  const kicker = container.querySelector(".kicker");
  const processSlides = new Set([3,6,9,10,14,17]);

  objects.forEach((node, order) => {
    const type = node.dataset.objectType;
    const rect = node.getBoundingClientRect();
    const area = rect.width * rect.height;
    let delay = 120 + Math.min(order, 14) * 34;
    if (node.dataset.sequence) delay = 120 + Number(node.dataset.sequence) * 90;
    if (processSlides.has(slideNumber)) delay = 130 + Math.round((rect.left / 1920) * 320) + Math.round((rect.top / 1080) * 60);
    if (node === kicker) delay = 30;
    if (node === title) delay = 80;

    if (node.matches("[data-reveal-step],.flow-paths")) return;
    if (node === kicker) animate(node,[{opacity:0,letterSpacing:".28em"},{opacity:1,letterSpacing:getComputedStyle(node).letterSpacing}],{duration:440,delay});
    else if (node === title) animate(node,[{opacity:0,clipPath:"inset(100% 0 0 0)",transform:"translateY(22px)"},{opacity:1,clipPath:"inset(0)",transform:"translateY(0)"}],{duration:620,delay});
    else if (type === "chart") { animate(node,[{opacity:0,clipPath:"inset(0 100% 0 0)"},{opacity:1,clipPath:"inset(0)"}],{duration:720,delay}); animateSvg(node,delay+90); }
    else if (type === "table") animate(node,[{opacity:0,clipPath:"inset(0 0 100% 0)"},{opacity:1,clipPath:"inset(0)"}],{duration:620,delay});
    else if (type === "image") animate(node,[{opacity:0,transform:"scale(.965)"},{opacity:1,transform:"scale(1)"}],{duration:560,delay});
    else if (type === "shape" && area > 180000) animate(node,[{opacity:0},{opacity:1}],{duration:560,delay:Math.max(0,delay-100)});
    else if (type === "shape") animate(node,[{opacity:0,transform:"scale(.985)"},{opacity:1,transform:"scale(1)"}],{duration:440,delay});
    else animate(node,[{opacity:0,transform:"translateY(12px)"},{opacity:1,transform:"translateY(0)"}],{duration:470,delay});
  });

  container.querySelectorAll("li,table tr").forEach((node, i) => animate(node,[{opacity:0,transform:"translateX(-10px)"},{opacity:1,transform:"translateX(0)"}],{duration:340,delay:200+i*40}));
  container.querySelectorAll('[style*="display:grid"]').forEach((grid) => {
    const children = [...grid.children].filter((node) => node.tagName !== "STYLE" && node.tagName !== "SCRIPT");
    if (children.length < 3) return;
    children.forEach((node,index) => animate(node,[{opacity:0,transform:"translateY(14px) scale(.99)"},{opacity:1,transform:"translateY(0) scale(1)"}],{duration:360,delay:220+index*65}));
  });
  playCounts();

  playStoryFlow();
  if (slideNumber === 9) playArchitectureRoutes();

  createAccent(title);
  const sweep = document.createElement("div"); sweep.className = "runtime-prism-sweep"; document.body.append(sweep);
  animate(sweep,[{left:"-18%",opacity:0},{offset:.16,opacity:.8},{left:"108%",opacity:0}],{duration:980,delay:slideNumber===1?240:520,easing:"cubic-bezier(.2,.7,.2,1)"});

  if ([1,4,5,9,10,13,15,18].includes(slideNumber)) {
    const dot = document.createElement("div"); dot.className = "runtime-signal-dot"; dot.style.left = "10%"; dot.style.top = slideNumber===18?"24%":"72%"; document.body.append(dot);
    animate(dot,[{opacity:0,transform:"translateX(0) scale(.5)"},{offset:.2,opacity:1},{opacity:0,transform:"translateX(1450px) scale(1)"}],{duration:920,delay:680,easing:"cubic-bezier(.2,.7,.2,1)"});
  }
}

addEventListener("message", (event) => {
  if (event.data?.type === "vtl:motion") { root.classList.toggle("reduce-motion", !!event.data.reducedMotion); if (event.data.reducedMotion) cancelAll(); }
  if (event.data?.type === "vtl:replay") { root.classList.toggle("reduce-motion", !!event.data.reducedMotion); play(); }
  if (event.data?.type === "vtl:counts" && !reduced()) playCounts();
});

if (document.readyState === "loading") addEventListener("DOMContentLoaded", () => requestAnimationFrame(play)); else requestAnimationFrame(play);
