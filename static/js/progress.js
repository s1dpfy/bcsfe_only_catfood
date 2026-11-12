const dl = { loaded: 0, total: 0, label: "받는 중", on: false };
const nativeFetch = window.fetch.bind(window);

export function paintDl() {
  const box = document.getElementById("dl-box");
  const bar = document.getElementById("dl-bar");
  const text = document.getElementById("dl-label");
  if (!dl.on) {
    box.classList.add("hidden");
    return;
  }
  box.classList.remove("hidden");
  const pct = dl.total > 0 ? Math.min(100, Math.round(dl.loaded / dl.total * 100)) : 0;
  bar.classList.toggle("unk", dl.total === 0);
  bar.style.width = dl.total ? pct + "%" : "";
  const mb = (n) => (n / 1048576).toFixed(1);
  text.textContent = dl.total
    ? `${dl.label} ${mb(dl.loaded)}MB / ${mb(dl.total)}MB · ${pct}%`
    : `${dl.label} ${mb(dl.loaded)}MB`;
  const start = document.getElementById("btn-start");
  if (start && start.disabled && document.getElementById("section-intro").classList.contains("active")) {
    start.textContent = dl.total ? `받는 중 ${pct}%` : "받는 중";
  }
  const loadBtn = document.getElementById("btn-load");
  if (loadBtn && loadBtn.disabled && document.getElementById("section-load").classList.contains("active")) {
    loadBtn.textContent = dl.total ? `불러오는 중 ${pct}%` : "불러오는 중";
  }
}

export function startDl(label) {
  dl.loaded = 0;
  dl.total = 0;
  dl.label = label;
  dl.on = true;
  paintDl();
}

export function stopDl() {
  dl.on = false;
  paintDl();
}

export function setDlLabel(label) {
  dl.label = label;
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
