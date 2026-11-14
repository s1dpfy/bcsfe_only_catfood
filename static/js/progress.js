const dl = { loaded: 0, total: 0, label: "받는 중", on: false, phasePct: 0 };
const nativeFetch = window.fetch.bind(window);

function pctNow() {
  const bytePct = dl.total > 0 ? Math.min(100, Math.round(dl.loaded / dl.total * 100)) : 0;
  return Math.max(bytePct, dl.phasePct || 0);
}

function paintOne(boxId, barId, labelId) {
  const box = document.getElementById(boxId);
  const bar = document.getElementById(barId);
  const text = document.getElementById(labelId);
  if (!box || !bar || !text) return;
  if (!dl.on && boxId !== "boot-dl") {
    box.classList.add("hidden");
    return;
  }
  box.classList.remove("hidden");
  const pct = pctNow();
  const hasBytes = dl.total > 0;
  bar.classList.toggle("unk", !hasBytes && pct < 2);
  bar.style.width = (hasBytes || pct > 0) ? Math.max(pct, hasBytes ? Math.min(100, Math.round(dl.loaded / dl.total * 100)) : pct) + "%" : "";
  const mb = (n) => (n / 1048576).toFixed(1);
  text.textContent = hasBytes
    ? `${dl.label} ${mb(dl.loaded)}MB / ${mb(dl.total)}MB · ${pct}%`
    : `${dl.label} ${mb(dl.loaded)}MB · ${pct}%`;
}

function paintPct() {
  const el = document.getElementById("boot-pct");
  if (!el) return;
  el.textContent = pctNow() + "%";
}

export function paintDl() {
  paintOne("dl-box", "dl-bar", "dl-label");
  paintOne("boot-dl", "boot-bar", "boot-label");
  paintPct();
  const loadBtn = document.getElementById("btn-load");
  if (loadBtn && loadBtn.disabled && document.getElementById("section-load").classList.contains("active")) {
    loadBtn.textContent = dl.on ? `불러오는 중 ${pctNow()}%` : "불러오는 중";
  }
}

export function startDl(label) {
  dl.loaded = 0;
  dl.total = 0;
  dl.phasePct = 0;
  dl.label = label;
  dl.on = true;
  paintDl();
}

export function stopDl() {
  dl.on = false;
  dl.phasePct = 100;
  paintDl();
}

export function setDlLabel(label) {
  dl.label = label;
  paintDl();
}

export function setPhaseProgress(pct, label) {
  dl.phasePct = Math.max(0, Math.min(100, Number(pct) || 0));
  if (label) dl.label = label;
  dl.on = true;
  paintDl();
}

function fileLabel(input) {
  try {
    const raw = typeof input === "string" ? input : (input && input.url) || "";
    const path = new URL(raw, location.href).pathname.split("/").filter(Boolean).pop() || "";
    if (path.includes("pyodide.asm.wasm")) return "런타임";
    if (path.includes("python_stdlib")) return "파이썬";
    if (raw.includes("/api/relay")) return "세이브";
    const wheel = path.replace(/\.whl$/, "").replace(/\.tar\.gz$/, "");
    if (wheel && wheel !== path) return wheel.split("-")[0];
  } catch (err) {}
  return "";
}

function trackResponse(res, input) {
  if (!dl.on || !res || !res.body) return res;
  const len = Number(res.headers.get("content-length") || 0);
  if (len) dl.total += len;
  const named = fileLabel(input);
  if (named) dl.label = named + " 받는 중";
  const reader = res.body.getReader();
  const stream = new ReadableStream({
    async pull(controller) {
      try {
        const { done, value } = await reader.read();
        if (done) {
          controller.close();
          return;
        }
        dl.loaded += value.byteLength;
        if (dl.total && dl.loaded > dl.total) dl.total = dl.loaded;
        paintDl();
        controller.enqueue(value);
      } catch (err) {
        controller.error(err);
      }
    }
  });
  return new Response(stream, { status: res.status, statusText: res.statusText, headers: new Headers(res.headers) });
}

window.fetch = async function (input, init) {
  const res = await nativeFetch(input, init);
  return trackResponse(res, input);
};
