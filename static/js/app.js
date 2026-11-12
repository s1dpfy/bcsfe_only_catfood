import { startDl, stopDl, setDlLabel } from "./progress.js";
import "./http.js";

let pyodide = null;
let editorReady = false;
let pending = {};
let owned = {};

const FRUIT = ["보라 개다래나무의 씨앗", "빨강 개다래나무의 씨앗", "파랑 개다래나무의 씨앗", "초록 개다래나무의 씨앗", "노랑 개다래나무의 씨앗", "보라 개다래 열매", "빨강 개다래 열매", "파랑 개다래 열매", "초록 개다래 열매", "노랑 개다래 열매", "무지개 개다래 열매", "고대 개다래나무의 씨앗", "고대 개다래 열매", "무지개 개다래나무의 씨앗", "황금 개다래 열매", "악마 개다래나무의 씨앗", "악마 개다래 열매", "황금 개다래나무의 씨앗", "자수석", "홍수석", "청수석", "녹수석", "황수석", "자수석 결정", "홍수석 결정", "청수석 결정", "녹수석 결정", "황수석 결정", "무지개 수석"];
const EYES = ["캣츠아이【EX】", "캣츠아이【레어】", "캣츠아이【슈퍼 레어】", "캣츠아이【울트라 슈퍼 레어】", "캣츠아이【레전드】", "캣츠아이【다크】"];
const LIMITS = { catfood: 1000000, xp: 100000000, normal: 999, legend: 999, platinum: 999, catfruit: 998, np: 9999, catseyes: 999 };
const NAMES = { catfood: "통조림", xp: "XP", normal: "일반 티켓", legend: "레전드 티켓", platinum: "플래티넘 티켓", np: "NP", catfruit: "개다래", catseyes: "캣츠아이" };

function liftForKeyboard() {
  const vv = window.visualViewport;
  const kb = vv ? Math.max(0, window.innerHeight - vv.height - vv.offsetTop) : 0;
  document.documentElement.style.setProperty("--kb", kb + "px");
  const el = document.activeElement;
  if (kb && el && el.matches && el.matches("input,textarea")) el.scrollIntoView({ block: "center" });
}

function showSection(id) {
  document.querySelectorAll(".section").forEach((s) => s.classList.remove("active"));
  const el = document.getElementById(id);
  if (el) el.classList.add("active");
}

function logAction(msg) {
  document.getElementById("action-log").textContent = msg;
}

function goBack() {
  logAction("");
  showSection("section-intro");
  const btn = document.getElementById("btn-start");
  btn.disabled = false;
  btn.textContent = "에디터 이용시작";
}

function copyText(id) {
  navigator.clipboard.writeText(document.getElementById(id).innerText).then(() => logAction("복사했습니다"));
}

function fmt(n) {
  return Number(n || 0).toLocaleString("ko-KR");
}

function amountOf(type) {
  if (type === "catfruit" && pending.catfruitEach) return pending.catfruitEach;
  if (type === "catseyes" && pending.catseyesEach) return pending.catseyesEach;
  if (pending[type] != null) return pending[type];
  return owned[type];
}

function listNames(kind) {
  const names = kind === "catfruit" ? FRUIT : EYES;
  const raw = amountOf(kind);
  const cur = Array.isArray(raw) ? raw : [];
  return { names, cur, n: cur.length || names.length };
}

async function ensureEditor() {
  if (editorReady) return;
  startDl("런타임 받는 중");
  try {
    pyodide = await loadPyodide({ indexURL: "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/" });
    setDlLabel("에디터 받는 중");
    await pyodide.loadPackage(["micropip", "pyyaml", "requests"], {
      messageCallback: (msg) => {
        const name = String(msg).replace(/^(Loading|Loaded|Downloading)\s+/, "").split(/\s+/)[0];
        if (name) setDlLabel(name + " 받는 중");
      }
    });
    setDlLabel("에디터 설치 중");
    const source = await (await fetch("/editor.py")).text();
    await pyodide.runPythonAsync(source);
    editorReady = true;
  } finally {
    stopDl();
  }
}

async function startEditor() {
  const btn = document.getElementById("btn-start");
  btn.disabled = true;
  try {
    await ensureEditor();
    logAction("");
    showSection("section-load");
  } catch (err) {
    console.error(err);
    logAction("에디터를 준비하지 못했습니다. " + (err && err.message ? err.message : ""));
    btn.disabled = false;
    btn.textContent = "에디터 이용시작";
  }
}

async function callApi(source) {
  const raw = await pyodide.runPythonAsync(source);
  return JSON.parse(raw);
}

async function loadSave() {
  const tc = document.getElementById("transfer_code").value.trim();
  const cc = document.getElementById("confirmation_code").value.trim();
  if (!tc || !cc) return logAction("코드와 인증 번호를 입력하세요");
  const btn = document.getElementById("btn-load");
  btn.disabled = true;
  btn.textContent = "불러오는 중";
  startDl("세이브 받는 중");
  try {
    const data = await callApi(`api_download(${JSON.stringify(tc)}, ${JSON.stringify(cc)})`);
    if (!data.success) return logAction(data.error || "불러오기 실패");
    pending = {};
    owned = {
      catfood: data.catfood ?? 0,
      xp: data.xp ?? 0,
      normal: data.normal_tickets ?? 0,
      legend: data.legend_tickets ?? 0,
      platinum: data.platinum_tickets ?? 0,
      np: data.np ?? 0,
      catfruit: Array.isArray(data.catfruit) ? data.catfruit : [],
      catseyes: Array.isArray(data.catseyes) ? data.catseyes : [],
    };
    showSection("section-modify");
    logAction("세이브를 불러왔습니다");
  } catch (err) {
    console.error(err);
    logAction(err && err.message ? err.message : "불러오기 실패");
  } finally {
    stopDl();
    btn.disabled = false;
    btn.textContent = "불러오기";
  }
}

function closeModal() {
  document.getElementById("modal-resource").classList.add("hidden");
}

function openResource(type) {
  const title = document.getElementById("resource-title");
  const body = document.getElementById("resource-body");
  title.textContent = NAMES[type] || type;
  if (type === "catfruit" || type === "catseyes") {
    const pack = listNames(type);
    const max = LIMITS[type] || 0;
    const rows = [];
    for (let i = 0; i < pack.n; i++) {
      const label = pack.names[i];
      if (!label) continue;
      const have = Array.isArray(owned[type]) ? Number(owned[type][i] || 0) : 0;
      const val = pack.cur[i] ?? "";
      if (type === "catfruit" && i === 18) rows.push(`<p class="hint stone">수석</p>`);
      rows.push(`<label class="line"><span>${label}<small>현재 ${fmt(have)}</small></span><input class="input each" data-i="${i}" type="number" min="0" max="${max}" value="${val}"></label>`);
    }
    body.innerHTML = `
      <p class="hint">최대 ${max.toLocaleString("ko-KR")}. 일괄은 모든 칸을 같은 수로 채웁니다.</p>
      <input id="bulk-val" class="input" type="number" min="0" max="${max}" placeholder="일괄 수량">
      <button class="btn spaced" type="button" id="btn-bulk">모든 종류에 같은 수량</button>
      <div class="stack">${rows.join("")}</div>
      <button class="btn primary spaced" type="button" id="btn-save-each">이 수량으로 저장</button>`;
    body.querySelector("#btn-bulk").addEventListener("click", fillBulk);
    body.querySelector("#btn-save-each").addEventListener("click", () => saveEach(type));
  } else {
    const max = LIMITS[type];
    const have = owned[type];
    const now = amountOf(type);
    body.innerHTML = `<p class="hint">현재 ${have == null ? "-" : fmt(have)}개 · 최대 ${Number(max || 0).toLocaleString("ko-KR")}</p>
      <input id="res-val" class="input" type="number" placeholder="바꿀 수량" value="${now == null ? "" : now}">
      <button class="btn primary spaced" type="button" id="btn-save-one">저장</button>`;
    body.querySelector("#btn-save-one").addEventListener("click", () => savePending(type));
  }
  document.getElementById("modal-resource").classList.remove("hidden");
}

function fillBulk() {
  const value = document.getElementById("bulk-val").value;
  if (value === "") return logAction("일괄 수량을 입력하세요");
  document.querySelectorAll(".each").forEach((el) => { el.value = value; });
  logAction("모든 칸을 " + value + "으로 채웠습니다");
}

function saveEach(type) {
  const vals = [...document.querySelectorAll(".each")].map((el) => Number(el.value || 0));
  const max = LIMITS[type] || 0;
  if (vals.some((n) => n > max)) return logAction("최대 " + max + "까지입니다");
  if (type === "catfruit") pending.catfruitEach = vals;
  else pending.catseyesEach = vals;
  closeModal();
  logAction((type === "catfruit" ? "개다래" : "캣츠아이") + " 수량을 저장했습니다. 업로드하면 반영됩니다");
}

function savePending(key) {
  const value = document.getElementById("res-val").value;
  if (value === "") return logAction("수량을 입력하세요");
  const n = Number(value);
  const max = LIMITS[key];
  if (max != null && n > max) return logAction("최대 " + max.toLocaleString("ko-KR") + "까지입니다");
  pending[key] = n;
  closeModal();
  logAction("저장했습니다. 업로드하면 반영됩니다");
}

async function modifySave() {
  const payload = {};
  if (pending.catfood != null) payload.catfood = pending.catfood;
  if (pending.xp != null) payload.xp = pending.xp;
  if (pending.normal != null) payload.normal = pending.normal;
  if (pending.legend != null) payload.legend = pending.legend;
  if (pending.platinum != null) payload.platinum = pending.platinum;
  if (pending.np != null) payload.np = pending.np;
  if (pending.catfruitEach) payload.catfruitEach = pending.catfruitEach;
  if (pending.catseyesEach) payload.catseyesEach = pending.catseyesEach;
  const btn = document.getElementById("btn-upload");
  const label = btn.querySelector("span");
  btn.disabled = true;
  label.textContent = "업로드 중";
  try {
    const data = await callApi(`api_upload(${JSON.stringify(JSON.stringify(payload))})`);
    if (!data.success) {
      logAction(data.error || "업로드 실패");
      return;
    }
    showSection("section-result");
    document.getElementById("new_transfer_code").textContent = data.transfer_code;
    document.getElementById("new_confirmation_code").textContent = data.confirmation_code;
    logAction("");
  } catch (err) {
    console.error(err);
    logAction(err && err.message ? err.message : "업로드 실패");
  } finally {
    btn.disabled = false;
    label.textContent = "변경사항 업로드";
  }
}

if (window.visualViewport) {
  visualViewport.addEventListener("resize", liftForKeyboard);
  visualViewport.addEventListener("scroll", liftForKeyboard);
}
document.addEventListener("focusin", (e) => {
  if (e.target.matches && e.target.matches("input,textarea")) setTimeout(liftForKeyboard, 80);
});
document.getElementById("btn-start").addEventListener("click", startEditor);
document.getElementById("btn-load").addEventListener("click", loadSave);
document.getElementById("btn-upload").addEventListener("click", modifySave);
document.getElementById("btn-reload").addEventListener("click", () => location.reload());
document.querySelectorAll("[data-back]").forEach((el) => el.addEventListener("click", goBack));
document.querySelectorAll("[data-copy]").forEach((el) => el.addEventListener("click", () => copyText(el.dataset.copy)));
document.getElementById("resource-grid").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-resource]");
  if (btn) openResource(btn.dataset.resource);
});
document.getElementById("modal-resource").addEventListener("click", (e) => {
  if (e.target.id === "modal-resource") closeModal();
});
document.querySelector("[data-close]").addEventListener("click", closeModal);
