import { startDl, stopDl, setDlLabel, setPhaseProgress } from "./progress.js";
import { OPENCHAT_URL, isPremium, label as memberLabel, limits, redeemKey } from "./membership.js";
import "./http.js?v=11";

let pyodide = null;
let editorReady = null;
let pending = {};
let owned = {};

const FRUIT = ["보라 개다래나무의 씨앗", "빨강 개다래나무의 씨앗", "파랑 개다래나무의 씨앗", "초록 개다래나무의 씨앗", "노랑 개다래나무의 씨앗", "보라 개다래 열매", "빨강 개다래 열매", "파랑 개다래 열매", "초록 개다래 열매", "노랑 개다래 열매", "무지개 개다래 열매", "고대 개다래나무의 씨앗", "고대 개다래 열매", "무지개 개다래나무의 씨앗", "황금 개다래 열매", "악마 개다래나무의 씨앗", "악마 개다래 열매", "황금 개다래나무의 씨앗", "자수석", "홍수석", "청수석", "녹수석", "황수석", "자수석 결정", "홍수석 결정", "청수석 결정", "녹수석 결정", "황수석 결정", "무지개 수석"];
const EYES = ["캣츠아이【EX】", "캣츠아이【레어】", "캣츠아이【슈퍼 레어】", "캣츠아이【울트라 슈퍼 레어】", "캣츠아이【레전드】", "캣츠아이【다크】"];
function LIMITS() {
  return limits();
}
const NAMES = { catfood: "통조림", xp: "XP", normal: "일반 티켓", legend: "레전드 티켓", platinum: "플래티넘 티켓", np: "NP", catfruit: "개다래", catseyes: "캣츠아이" };

function liftForKeyboard() {
  const vv = window.visualViewport;
  const kb = vv ? Math.max(0, window.innerHeight - vv.height - vv.offsetTop) : 0;
  document.documentElement.style.setProperty("--kb", kb + "px");
  const el = document.activeElement;
  if (kb && el && el.matches && el.matches("input,textarea")) el.scrollIntoView({ block: "center" });
}

const STORE_KEY = "nyanko-codes";
const STORE_MAX = 20;

function readStore() {
  try {
    const raw = JSON.parse(localStorage.getItem(STORE_KEY) || "[]");
    return Array.isArray(raw) ? raw : [];
  } catch (err) {
    return [];
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

function paintStore() {
  const box = document.getElementById("code-store");
  const list = document.getElementById("code-list");
  const items = readStore();
  const visible = document.getElementById("section-load").classList.contains("active")
    || document.getElementById("section-result").classList.contains("active");
  if (!items.length || !visible) {
    box.classList.add("hidden");
    return;
  }
  box.classList.remove("hidden");
  list.innerHTML = items.map((item, index) => {
    const when = new Date(item.at);
    const stamp = `${when.getMonth() + 1}.${when.getDate()} ${String(when.getHours()).padStart(2, "0")}:${String(when.getMinutes()).padStart(2, "0")}`;
    return `<article class="code-row" data-i="${index}"><time>${stamp}</time><p><small>이어하기 코드</small><strong>${escapeHtml(item.transfer)}</strong></p><p><small>인증 번호</small><strong>${escapeHtml(item.confirmation)}</strong></p><button class="code-x" type="button" data-remove="${index}">삭제</button></article>`;
  }).join("");
}

function rememberCodes(transfer, confirmation) {
  const next = readStore().filter((item) => item.transfer !== transfer || item.confirmation !== confirmation);
  next.unshift({ transfer, confirmation, at: Date.now() });
  localStorage.setItem(STORE_KEY, JSON.stringify(next.slice(0, STORE_MAX)));
  paintStore();
}

function useStored(index) {
  const item = readStore()[index];
  if (!item) return;
  document.getElementById("transfer_code").value = item.transfer;
  document.getElementById("confirmation_code").value = item.confirmation;
  logAction("");
  showSection("section-load");
}

function removeStored(index) {
  const next = readStore();
  next.splice(index, 1);
  localStorage.setItem(STORE_KEY, JSON.stringify(next));
  paintStore();
}

function showSection(id) {
  document.querySelectorAll(".section").forEach((s) => s.classList.remove("active"));
  const el = document.getElementById(id);
  if (el) el.classList.add("active");
  paintStore();
}

function logAction(msg) {
  document.getElementById("action-log").textContent = msg;
}

function paintMember() {
  const premium = isPremium();
  const memberLine = document.getElementById("member-line");
  const tierLine = document.getElementById("tier-line");
  if (memberLine) {
    memberLine.textContent = premium
      ? `${memberLabel()}입니다. 고급회원을 누르면 바로 이어갑니다.`
      : "회원 종류를 고르세요.";
  }
  if (tierLine) {
    tierLine.textContent = premium
      ? "고급회원 · 항목을 누르면 수량 창이 열립니다."
      : "무료회원은 통조림 30,000 / XP 10,000,000 / 일반 티켓 20까지입니다.";
  }
}

function enterFree() {
  logAction("무료회원으로 시작합니다.");
  showSection("section-load");
}

function enterPremium() {
  if (isPremium()) {
    logAction(`${memberLabel()}으로 이어갑니다.`);
    showSection("section-load");
    return;
  }
  logAction("");
  showSection("section-key");
}

function openPlans() {
  document.getElementById("modal-plans").classList.remove("hidden");
}

async function redeemClicked() {
  const input = document.getElementById("member-key");
  const result = await redeemKey(input.value);
  logAction(result.message);
  if (result.ok) {
    input.value = "";
    paintMember();
    showSection("section-load");
  }
}

function goBack() {
  logAction("");
  showSection("section-load");
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

const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";

async function getLoadPyodide() {
  if (typeof loadPyodide === "function") return loadPyodide;
  const mod = await import(PYODIDE_URL + "pyodide.mjs");
  return mod.loadPyodide;
}

function ensureEditor() {
  if (editorReady) return editorReady;
  editorReady = (async () => {
    startDl("런타임 받는 중");
    setPhaseProgress(4, "런타임 받는 중");
    try {
      const load = await getLoadPyodide();
      try {
        pyodide = await load({
          indexURL: PYODIDE_URL,
          packages: ["micropip", "pyyaml", "requests"],
        });
      } catch (err) {
        pyodide = await load({ indexURL: PYODIDE_URL });
        await pyodide.loadPackage(["micropip", "pyyaml", "requests"]);
      }
      setPhaseProgress(55, "에디터 설치 중");
      const source = await (await fetch("/editor.py", { cache: "force-cache" })).text();
      setPhaseProgress(78, "에디터 설치 중");
      await pyodide.runPythonAsync(source);
      setPhaseProgress(100, "준비 완료");
    } catch (err) {
      editorReady = null;
      throw err;
    } finally {
      stopDl();
    }
  })();
  return editorReady;
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
  try {
    await ensureEditor();
    startDl("세이브 받는 중");
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

function closeModal(which) {
  const id = which || "modal-resource";
  const el = document.getElementById(id);
  if (el) el.classList.add("hidden");
}

function openResource(type) {
  const title = document.getElementById("resource-title");
  const body = document.getElementById("resource-body");
  title.textContent = NAMES[type] || type;
  if (type === "catfruit" || type === "catseyes") {
    const pack = listNames(type);
    const max = LIMITS()[type] || 0;
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
    const max = LIMITS()[type];
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
  const max = LIMITS()[type] || 0;
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
  const max = LIMITS()[key];
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
    rememberCodes(data.transfer_code, data.confirmation_code);
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
document.getElementById("btn-load").addEventListener("click", loadSave);
document.getElementById("code-list").addEventListener("click", (e) => {
  const remove = e.target.closest("[data-remove]");
  if (remove) {
    removeStored(Number(remove.dataset.remove));
    return;
  }
  const row = e.target.closest("[data-i]");
  if (row) useStored(Number(row.dataset.i));
});
paintStore();
paintMember();
document.querySelectorAll("[data-buy]").forEach((el) => {
  el.setAttribute("href", OPENCHAT_URL);
});
document.getElementById("btn-free").addEventListener("click", enterFree);
document.getElementById("btn-premium").addEventListener("click", enterPremium);
document.getElementById("btn-plans").addEventListener("click", openPlans);
document.getElementById("btn-redeem").addEventListener("click", redeemClicked);
document.getElementById("member-key").addEventListener("keydown", (e) => {
  if (e.key === "Enter") redeemClicked();
});
async function boot() {
  const modal = document.getElementById("modal-boot");
  const hint = document.getElementById("boot-hint");
  const retry = document.getElementById("btn-boot-retry");
  document.body.classList.add("booting");
  hint.textContent = "런타임을 받는 동안 기다려 주세요.";
  retry.classList.add("hidden");
  modal.classList.remove("hidden");
  try {
    await ensureEditor();
    modal.classList.add("hidden");
    document.body.classList.remove("booting");
    document.body.classList.add("ready");
    showSection("section-gate");
    paintMember();
  } catch (err) {
    console.error(err);
    hint.textContent = "에디터를 준비하지 못했습니다. " + (err && err.message ? err.message : "");
    retry.classList.remove("hidden");
  }
}

document.getElementById("btn-boot-retry").addEventListener("click", boot);
boot();
document.getElementById("btn-upload").addEventListener("click", modifySave);
document.getElementById("btn-reload").addEventListener("click", () => location.reload());
document.querySelectorAll("[data-back]").forEach((el) => el.addEventListener("click", goBack));
document.querySelectorAll("[data-gate]").forEach((el) => {
  el.addEventListener("click", () => {
    logAction("");
    showSection("section-gate");
  });
});
document.querySelectorAll("[data-copy]").forEach((el) => el.addEventListener("click", () => copyText(el.dataset.copy)));
document.getElementById("resource-grid").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-resource]");
  if (btn) openResource(btn.dataset.resource);
});
document.querySelectorAll(".modal").forEach((modal) => {
  modal.addEventListener("click", (e) => {
    if (e.target === modal && !modal.hasAttribute("data-lock")) modal.classList.add("hidden");
  });
});
document.querySelectorAll("[data-close]").forEach((el) => {
  el.addEventListener("click", () => {
    const modal = el.closest(".modal");
    if (modal) modal.classList.add("hidden");
  });
});
