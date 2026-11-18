let sessionToken="", currentAuthType="guest", currentUserTier="guest", currentVipKey="", selectedTier="guest", currentDeviceId="";
let pending={}, currentSave={}, owned={};
const PAGE=document.body.dataset.page||"home";
const PAGE_TIER=document.body.dataset.tier||"guest";
const FRUIT=["보라 개다래나무의 씨앗","빨강 개다래나무의 씨앗","파랑 개다래나무의 씨앗","초록 개다래나무의 씨앗","노랑 개다래나무의 씨앗","보라 개다래 열매","빨강 개다래 열매","파랑 개다래 열매","초록 개다래 열매","노랑 개다래 열매","무지개 개다래 열매","고대 개다래나무의 씨앗","고대 개다래 열매","무지개 개다래나무의 씨앗","황금 개다래 열매","악마 개다래나무의 씨앗","악마 개다래 열매","황금 개다래나무의 씨앗","자수석","홍수석","청수석","녹수석","황수석","자수석 결정","홍수석 결정","청수석 결정","녹수석 결정","황수석 결정","무지개 수석"];
const EYES=["캣츠아이【EX】","캣츠아이【레어】","캣츠아이【슈퍼 레어】","캣츠아이【울트라 슈퍼 레어】","캣츠아이【레전드】","캣츠아이【다크】"];
const LIMITS={
  guest:{catfood:25000,xp:20000000,normal:15},
  gold:{catfood:100000,xp:100000000,normal:200,legend:5,platinum:5,catfruit:20,np:1500,catseyes:20},
  vip:{catfood:1000000,xp:100000000,normal:999,legend:999,platinum:999,catfruit:998,np:9999,catseyes:999}
};
function liftForKeyboard(){
  const vv=window.visualViewport;
  const kb=vv?Math.max(0, window.innerHeight-vv.height-vv.offsetTop):0;
  document.documentElement.style.setProperty("--kb", kb+"px");
  const el=document.activeElement;
  if(kb && el && el.matches && el.matches("input,textarea")) el.scrollIntoView({block:"center"});
}
if(window.visualViewport){
  visualViewport.addEventListener("resize", liftForKeyboard);
  visualViewport.addEventListener("scroll", liftForKeyboard);
}
document.addEventListener("focusin", e=>{
  if(e.target.matches && e.target.matches("input,textarea")) setTimeout(liftForKeyboard, 80);
});
function getOrCreateDeviceId(){
  let id=localStorage.getItem("nyansly_device_id");
  if(!id){id=(crypto.randomUUID?crypto.randomUUID():Math.random().toString(36).slice(2));localStorage.setItem("nyansly_device_id",id)}
  return id;
}
currentDeviceId=getOrCreateDeviceId();
function showSection(id){
  document.querySelectorAll(".section").forEach(s=>s.classList.remove("active"));
  const el=document.getElementById(id); if(el) el.classList.add("active");
}
function logAction(msg){
  const box=document.getElementById("action-log");
  if(box) box.textContent=msg;
}
function openInfo(type){ document.getElementById("modal-"+type).classList.remove("hidden"); }
function copyText(id){ navigator.clipboard.writeText(document.getElementById(id).innerText).then(()=>logAction("복사했습니다")).catch(()=>logAction("복사에 실패했습니다")); }
function cap(){ return LIMITS[currentUserTier]||LIMITS.guest; }
function editPath(tier){
  if(tier==="gold") return "/editpage-gold";
  if(tier==="vip"||tier==="catmaster") return "/editpage-vip";
  return "/editpage";
}
function memberPath(tier){
  return tier==="gold" ? "/goldmember" : "/vipmember";
}
function applyTierUi(){
  const paid=currentUserTier==="gold"||currentUserTier==="vip";
  ["btn-legend","btn-platinum","btn-catfruit","btn-np","btn-catseyes"].forEach(id=>{
    const el=document.getElementById(id);
    if(el) el.classList.toggle("hidden", !paid);
  });
  const line=document.getElementById("tier-line");
  if(!line) return;
  const names={guest:"일반",gold:"골드",vip:"VIP"};
  line.textContent=(names[currentUserTier]||"일반")+" · 눌러서 수량을 넣으세요.";
}
const FIELDS={catfood:"catfood",xp:"xp",normal:"normal_tickets",legend:"legend_tickets",platinum:"platinum_tickets",np:"np",catfruit:"catfruit",catseyes:"catseyes"};
function fmt(n){ return Number(n||0).toLocaleString("ko-KR"); }
function amountOf(type){
  if(type==="catfruit" && pending.catfruitEach) return pending.catfruitEach;
  if(type==="catseyes" && pending.catseyesEach) return pending.catseyesEach;
  if(pending[type]!=null) return pending[type];
  return owned[type];
}
function closeTiktok(){
  const modal=document.getElementById("modal-tiktok");
  if(modal) modal.classList.add("hidden");
}
async function verifyKey(){
  const key=document.getElementById("vip_key").value.trim();
  if(!key) return logAction("키를 입력하세요");
  selectedTier=PAGE_TIER;
  const fd=new FormData();
  fd.append("vip_key",key); fd.append("device_id",currentDeviceId); fd.append("requested_tier",selectedTier);
  try{
    const r=await fetch("/api/verify_key",{method:"POST",body:fd});
    const d=await r.json();
    if(!d.success) return logAction(d.error||"유효하지 않은 키");
    const tier=d.tier==="catmaster"?"vip":(d.tier||selectedTier);
    sessionStorage.setItem("nyansly_key", key);
    sessionStorage.setItem("nyansly_tier", tier);
    location.href=editPath(tier);
  }catch{ logAction("서버 통신 오류"); }
}
async function loadSave(){
  const tc=document.getElementById("transfer_code").value.trim();
  const cc=document.getElementById("confirmation_code").value.trim();
  if(!tc||!cc) return logAction("코드와 인증 번호를 입력하세요");
  const fd=new FormData();
  fd.append("transfer_code",tc); fd.append("confirmation_code",cc);
  fd.append("membership_type",currentAuthType); fd.append("requested_tier",currentUserTier);
  if(currentAuthType==="member"){ fd.append("vip_key",currentVipKey); fd.append("device_id",currentDeviceId); }
  try{
    const r=await fetch("/api/load_save",{method:"POST",body:fd});
    const d=await r.json();
    if(!d.success) return logAction(d.error||"불러오기 실패");
    sessionToken=d.token;
    currentSave=d;
    owned={
      catfood:d.catfood??0, xp:d.xp??0, normal:d.normal_tickets??0,
      legend:d.legend_tickets??0, platinum:d.platinum_tickets??0, np:d.np??0,
      catfruit:Array.isArray(d.catfruit)?d.catfruit:[],
      catseyes:Array.isArray(d.catseyes)?d.catseyes:[]
    };
    applyTierUi();
    showSection("section-modify");
    logAction("세이브를 불러왔습니다");
  }catch{ logAction("서버 통신 오류"); }
}
function listNames(kind){
  const names=kind==="catfruit"?FRUIT:EYES;
  const raw=amountOf(kind);
  const cur=Array.isArray(raw)?raw:[];
  const n=cur.length||names.length;
  return {names, cur, n};
}
function openResource(type){
  const title=document.getElementById("resource-title");
  const body=document.getElementById("resource-body");
  const names={catfood:"통조림",xp:"XP",normal:"일반 티켓",legend:"레전드 티켓",platinum:"플래티넘 티켓",np:"NP",catfruit:"개다래",catseyes:"캣츠아이"};
  const icons={catfood:"fa-jar",xp:"fa-bolt",normal:"fa-ticket",legend:"fa-scroll",platinum:"fa-gem",np:"fa-coins",catfruit:"fa-seedling",catseyes:"fa-eye"};
  title.querySelector("span").textContent=names[type]||type;
  title.querySelector("i").className="fa-solid "+(icons[type]||"fa-pen");
  if(type==="catfruit"||type==="catseyes"){
    const pack=listNames(type);
    const max=(cap()[type]||0);
    const rows=[];
    for(let i=0;i<pack.n;i++){
      const label=pack.names[i];
      if(!label) continue;
      const have=Array.isArray(owned[type])?Number(owned[type][i]||0):0;
      const val=pack.cur[i]??"";
      if(type==="catfruit" && i===18) rows.push(`<p class="hint" style="margin:12px 0 0">수석</p>`);
      rows.push(`<label class="line"><span>${label}<small>현재 ${fmt(have)}</small></span><input class="input each" data-i="${i}" type="number" min="0" max="${max}" value="${val}"></label>`);
    }
    body.innerHTML=`
      <p class="hint">최대 ${max.toLocaleString()}. 일괄은 모든 칸을 같은 수로 채웁니다.</p>
      <input id="bulk-val" class="input" type="number" min="0" max="${max}" placeholder="일괄 수량">
      <button class="btn" style="margin-top:8px" onclick="fillBulk()"><i class="fa-solid fa-fill-drip"></i>모든 종류에 같은 수량</button>
      <div style="margin-top:8px">${rows.join("")}</div>
      <button class="btn primary" style="margin-top:10px" onclick="saveEach('${type}')"><i class="fa-solid fa-floppy-disk"></i>이 수량으로 저장</button>`;
  } else {
    const max=cap()[type];
    const have=owned[type];
    const now=amountOf(type);
    body.innerHTML=`<p class="hint">현재 ${have==null?"-":fmt(have)}개 · 최대 ${Number(max||0).toLocaleString("ko-KR")}</p>
      <input id="res-val" class="input" type="number" placeholder="바꿀 수량" value="${now==null?"":now}">
      <button class="btn primary" style="margin-top:8px" onclick="savePending('${type}')"><i class="fa-solid fa-floppy-disk"></i>저장</button>`;
  }
  document.getElementById("modal-resource").classList.remove("hidden");
}
function fillBulk(){
  const v=document.getElementById("bulk-val").value;
  if(v==="") return logAction("일괄 수량을 입력하세요");
  document.querySelectorAll(".each").forEach(el=>el.value=v);
  logAction("모든 칸을 "+v+"으로 채웠습니다");
}
function saveEach(type){
  const vals=[...document.querySelectorAll(".each")].map(el=>Number(el.value||0));
  const max=cap()[type]||0;
  if(vals.some(n=>n>max)) return logAction("최대 "+max+"까지입니다");
  if(type==="catfruit"){ pending.catfruitEach=vals; delete pending.catfruit; }
  else { pending.catseyesEach=vals; delete pending.catseyes; }
  currentSave[type]=vals;
  document.getElementById("modal-resource").classList.add("hidden");
  logAction((type==="catfruit"?"개다래":"캣츠아이")+" 수량을 저장했습니다. 업로드하면 반영됩니다");
}
function savePending(key){
  const v=document.getElementById("res-val").value;
  if(v==="") return logAction("수량을 입력하세요");
  const n=Number(v);
  const max=cap()[key];
  if(max!=null && n>max) return logAction("최대 "+max.toLocaleString()+"까지입니다");
  pending[key]=n;
  currentSave[FIELDS[key]]=n;
  document.getElementById("modal-resource").classList.add("hidden");
  logAction("저장했습니다. 업로드하면 반영됩니다");
}
async function modifySave(){
  const fd=new FormData();
  if(pending.catfood!=null) fd.append("catfood",pending.catfood);
  if(pending.xp!=null) fd.append("xp",pending.xp);
  if(pending.normal!=null) fd.append("normal_tickets",pending.normal);
  if(pending.legend!=null) fd.append("legend_tickets",pending.legend);
  if(pending.platinum!=null) fd.append("platinum_tickets",pending.platinum);
  if(pending.np!=null) fd.append("np",pending.np);
  if(pending.catfruitEach) fd.append("catfruit_each", JSON.stringify(pending.catfruitEach));
  else if(pending.catfruit!=null) fd.append("catfruit",pending.catfruit);
  if(pending.catseyesEach) fd.append("catseyes_each", JSON.stringify(pending.catseyesEach));
  else if(pending.catseyes!=null) fd.append("catseyes",pending.catseyes);
  const btn=document.getElementById("btn-upload");
  const label=btn.querySelector("span");
  btn.disabled=true; label.textContent="업로드 중";
  try{
    const r=await fetch("/api/modify_and_upload",{method:"POST",headers:{"x-session-token":sessionToken},body:fd});
    const d=await r.json();
    if(!r.ok || !d.success){
      logAction(d.detail||d.error||"업로드 실패");
      if(r.status===401) logAction("세션이 만료되었습니다. 세이브를 다시 불러오세요.");
      return;
    }
    showSection("section-result");
    document.getElementById("new_transfer_code").textContent=d.transfer_code;
    document.getElementById("new_confirmation_code").textContent=d.confirmation_code;
    if(d.key_burned) document.getElementById("result-desc").textContent="새 코드로 이어하세요. 1회용 키는 사용 처리되었습니다.";
  }catch{ logAction("서버 통신 오류"); }
  finally{ btn.disabled=false; label.textContent="변경사항 업로드"; }
}
function bootEdit(){
  if(PAGE_TIER==="guest"){
    currentAuthType="guest";
    currentUserTier="guest";
    applyTierUi();
    return;
  }
  const key=sessionStorage.getItem("nyansly_key")||"";
  const tier=sessionStorage.getItem("nyansly_tier")||"";
  if(!key || (tier && tier!==PAGE_TIER)){
    location.replace(memberPath(PAGE_TIER));
    return;
  }
  currentAuthType="member";
  currentVipKey=key;
  currentUserTier=PAGE_TIER;
  selectedTier=PAGE_TIER;
  applyTierUi();
}
if(PAGE==="edit") bootEdit();
