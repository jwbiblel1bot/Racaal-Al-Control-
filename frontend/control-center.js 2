/* RACAAL Control Center frontend controller. No secrets belong in this file. */
const API_BASE = "https://racaal-al-control.onrender.com";
const params = new URLSearchParams(window.location.search);
let groupId = params.get("group_id") || null;
let controlSession = sessionStorage.getItem("racaal_control_session") || "";
let sessionPermanent = sessionStorage.getItem("racaal_session_permanent") === "true";
const messageBox = document.getElementById("message");
const inputs = [...document.querySelectorAll("[data-path]")];
let currentSettings = {};
let isSaving = false;
let isLoading = false;

function pathParts(path) { return path.split("."); }
function setNested(obj, path, value) {
  const parts = pathParts(path); let cur = obj;
  for (let i=0;i<parts.length-1;i++) { cur[parts[i]] ??= {}; cur=cur[parts[i]]; }
  cur[parts.at(-1)] = value;
}
function getNested(obj,path) { return pathParts(path).reduce((v,k)=>v?.[k],obj); }
function showMessage(text,error=false) {
  if (!messageBox) { (error?console.error:console.log)("RACAAL:",text); return; }
  messageBox.hidden=false; messageBox.textContent=text; messageBox.className=error?"message error":"message";
  clearTimeout(showMessage.timer); showMessage.timer=setTimeout(()=>messageBox.hidden=true,6000);
}
function setButtonBusy(button,busy,busyText) {
  if(!button)return;
  if(busy){ if(!button.dataset.originalText)button.dataset.originalText=button.textContent; button.disabled=true; if(busyText)button.textContent=busyText; }
  else {button.disabled=false;if(button.dataset.originalText)button.textContent=button.dataset.originalText;}
}
async function apiRequest(path,options={}) {
  const headers={Accept:"application/json",...(options.body?{"Content-Type":"application/json"}:{}),...(controlSession?{"X-RACAAL-SESSION":controlSession}:{}),...(options.headers||{})};
  const response=await fetch(`${API_BASE}${path}`,{...options,headers});
  const text=await response.text(); let data={};
  if(text){try{data=JSON.parse(text);}catch{data={raw:text};}}
  if(!response.ok)throw new Error(data?.error||data?.message||`Request failed (${response.status})`);
  return data;
}
function readValue(el) {
  if(el.type==="checkbox")return el.checked;
  if(el.type==="number")return Number.isFinite(Number(el.value))?Number(el.value):0;
  if(el.tagName==="TEXTAREA"&&["protection.blacklist","protection.whitelist"].includes(el.dataset.path))return el.value.split("\n").map(x=>x.trim()).filter(Boolean);
  return el.value;
}
function writeValue(el,value) {
  if(el.type==="checkbox"){el.checked=Boolean(value);return;}
  if(el.tagName==="TEXTAREA"&&Array.isArray(value)){el.value=value.join("\n");return;}
  if(value!==undefined&&value!==null)el.value=value;
}
function collectSettings(){const settings={};inputs.forEach(el=>{if(el.dataset.path)setNested(settings,el.dataset.path,readValue(el));});return settings;}
function applySettings(settings){
  if(!settings||typeof settings!=="object")throw new Error("Invalid settings received from the API.");
  inputs.forEach(el=>{const value=getNested(settings,el.dataset.path);if(value!==undefined&&value!==null)writeValue(el,value);});
  currentSettings=structuredClone(settings);
  const title=document.getElementById("groupName"); if(title)title.textContent=settings.telegram?.group_title||"Telegram Group";
  const status=document.getElementById("telegramStatusText"); if(status)status.textContent=settings.telegram?.connection_status||"Registered";
  const commentsEnabled=document.getElementById("commentsEnabled"); if(commentsEnabled)commentsEnabled.checked=Boolean(settings.automation?.comments);
  const commentText=document.getElementById("commentText"); if(commentText)commentText.value=settings.automation?.comment_text||"";
  const commentUrl=document.getElementById("commentUrl"); if(commentUrl)commentUrl.value=settings.automation?.comment_url||"";
  const commentButton=document.getElementById("commentButtonText"); if(commentButton)commentButton.value=settings.automation?.comment_button_text||"Open";
}
function updateGroupDisplay(){
  const el=document.getElementById("groupId");if(el)el.textContent=groupId?`Group ID: ${groupId}`:"Group ID: not verified";
  const title=document.getElementById("groupName");if(title&&!groupId)title.textContent="No verified group";
}
function requireGroup(){if(!groupId||!controlSession)throw new Error("Open the private Control Center link sent by the RACAAL bot after it joins your group.");}
function groupPath(suffix=""){requireGroup();return `/control/groups/${encodeURIComponent(groupId)}${suffix}`;}
async function verifyPermanentToken(){
  const token=params.get("token");if(!token)return false;
  const response=await fetch(`${API_BASE}/control/control-link/verify`,{method:"POST",headers:{Accept:"application/json","Content-Type":"application/json"},body:JSON.stringify({token})});
  const data=await response.json().catch(()=>({}));if(!response.ok||!data.success)throw new Error(data.error||"This Control Center link is invalid or revoked.");
  controlSession=data.session_token;groupId=String(data.group_id);sessionPermanent=Boolean(data.session_permanent);
  sessionStorage.setItem("racaal_control_session",controlSession);sessionStorage.setItem("racaal_session_permanent",String(sessionPermanent));
  const clean=new URL(window.location.href);clean.searchParams.delete("token");clean.searchParams.set("group_id",groupId);history.replaceState({},"",clean.pathname+clean.search+clean.hash);
  return true;
}
async function loadSettings(){requireGroup();if(isLoading)return;isLoading=true;try{const data=await apiRequest(groupPath("/settings"));applySettings(data.settings);updateGroupDisplay();}finally{isLoading=false;}}
async function loadGroups(){
  const holder=document.getElementById("telegramGroups");if(!holder||!controlSession)return;
  try{const data=await apiRequest("/control/my-groups");const groups=data.groups||[];holder.replaceChildren();
    if(!groups.length){const note=document.createElement("p");note.textContent="No Telegram groups are linked yet. Add the RACAAL bot to a group, make it an administrator, then open the private setup link the bot sends you.";holder.appendChild(note);return;}
    for(const group of groups){const card=document.createElement("div");card.style.cssText="display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid #e5e7eb;border-radius:12px;padding:14px;margin:10px 0";const info=document.createElement("div");const name=document.createElement("strong");name.textContent=group.group_title||"Telegram Group";const sub=document.createElement("p");sub.textContent=`Group ID: ${group.group_id} · ${group.connection_status||"registered"}`;sub.style.cssText="margin:5px 0 0;color:#667085;font-size:13px";info.append(name,sub);const manage=document.createElement("button");manage.type="button";manage.className="secondary";manage.textContent=String(group.group_id)===String(groupId)?"Current group":"Manage";manage.addEventListener("click",async()=>{if(String(group.group_id)===String(groupId)){document.getElementById("groupName")?.scrollIntoView({behavior:"smooth"});return;}try{const switched=await apiRequest(`/control/groups/${encodeURIComponent(group.group_id)}/switch-session`,{method:"POST",body:JSON.stringify({})});sessionStorage.setItem("racaal_control_session",switched.session_token);sessionStorage.setItem("racaal_session_permanent","true");location.href=`/?group_id=${encodeURIComponent(group.group_id)}`;}catch(e){showMessage(e.message,true);}});card.append(info,manage);holder.appendChild(card);}
  }catch(e){holder.textContent=`Could not load linked groups: ${e.message}`;}
}
async function saveSettings(button){requireGroup();if(isSaving)return;isSaving=true;setButtonBusy(button,true,"Saving...");try{const data=await apiRequest(groupPath("/settings"),{method:"PUT",body:JSON.stringify({settings:collectSettings()})});applySettings(data.settings);showMessage(data.message||"Group settings saved permanently.");}finally{isSaving=false;setButtonBusy(button,false);}}
function buttonFromFields(text,url){const label=String(text||"").trim(),href=String(url||"").trim();if(!href)return [];if(!label)throw new Error("Button text is required when a URL is provided.");return [{text:label,url:href}];}
function formatDate(value){if(!value)return "Not scheduled";const d=new Date(value);return Number.isNaN(d.getTime())?String(value):d.toLocaleString();}
function localDateTimeInZoneToISO(value,zone){
  if(!value)throw new Error("Choose a date and time.");
  const m=String(value).match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if(!m)throw new Error("The selected date/time is invalid.");
  const target=[+m[1],+m[2],+m[3],+m[4],+m[5]];
  const targetMs=Date.UTC(target[0],target[1]-1,target[2],target[3],target[4]);
  let guess=targetMs;
  try{
    const fmt=new Intl.DateTimeFormat("en-GB",{timeZone:zone||"Africa/Kampala",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"});
    for(let i=0;i<3;i++){
      const parts=Object.fromEntries(fmt.formatToParts(new Date(guess)).filter(p=>p.type!=="literal").map(p=>[p.type,p.value]));
      const actualMs=Date.UTC(+parts.year,+parts.month-1,+parts.day,+parts.hour,+parts.minute);
      guess+=targetMs-actualMs;
    }
    return new Date(guess).toISOString();
  }catch(e){throw new Error(`Invalid timezone: ${zone}`);}
}
async function loadSchedules(){
  const holder=document.getElementById("scheduleItems");if(!holder||!groupId||!controlSession)return;
  try{const data=await apiRequest(groupPath("/schedules"));const items=data.schedules||[];holder.replaceChildren();
    if(!items.length){holder.textContent="No schedules yet.";return;}
    for(const item of items){const card=document.createElement("div");card.className="schedule-item";card.style.cssText="border:1px solid #e5e7eb;border-radius:10px;padding:12px;margin:8px 0";
      const title=document.createElement("strong");title.textContent=item.message||"Scheduled message";card.appendChild(title);
      const detail=document.createElement("p");detail.textContent=`${item.frequency||"once"} · ${formatDate(item.run_at||item.next_run_at)} · ${item.enabled===false?"Paused":"Enabled"}`;card.appendChild(detail);
      const del=document.createElement("button");del.type="button";del.className="secondary";del.textContent="Delete";del.addEventListener("click",async()=>{if(!confirm("Delete this schedule?"))return;try{await apiRequest(groupPath(`/schedules/${encodeURIComponent(item.id)}`),{method:"DELETE"});showMessage("Schedule deleted.");await loadSchedules();}catch(e){showMessage(e.message,true);}});card.appendChild(del);holder.appendChild(card);
    }
  }catch(e){holder.textContent=`Could not load schedules: ${e.message}`;}
}
async function loadButtons(){
  const holder=document.getElementById("buttonItems");if(!holder||!groupId||!controlSession)return;
  try{const data=await apiRequest(groupPath("/buttons"));holder.replaceChildren();const items=data.buttons||[];if(!items.length){holder.textContent="No saved buttons yet.";return;}
    for(const item of items){const row=document.createElement("div");row.style.cssText="display:flex;gap:10px;align-items:center;justify-content:space-between;padding:8px 0";const label=document.createElement("span");label.textContent=`${item.text} — ${item.url}`;row.appendChild(label);const del=document.createElement("button");del.type="button";del.className="secondary";del.textContent="Delete";del.addEventListener("click",async()=>{try{await apiRequest(groupPath(`/buttons/${encodeURIComponent(item.id)}`),{method:"DELETE"});showMessage("Button deleted.");await loadButtons();}catch(e){showMessage(e.message,true);}});row.appendChild(del);holder.appendChild(row);}
  }catch(e){holder.textContent=`Could not load buttons: ${e.message}`;}
}
async function saveCommentsConfig(data){requireGroup();const url=String(data.url||"").trim();const buttons=buttonFromFields(data.button_text,url);const result=await apiRequest(groupPath("/comments"),{method:"PUT",body:JSON.stringify({enabled:Boolean(data.enabled),comment_text:data.text||"",comment_url:url,comment_buttons:buttons,comment_button_text:data.button_text||"Open"})});showMessage("Comments settings saved.");return result;}
async function createSchedule(data){requireGroup();const raw=data.run_at||data.scheduled_for||"";if(!raw)throw new Error("Choose a date and time for the schedule.");const zone=data.timezone||"Africa/Kampala";const runAt=localDateTimeInZoneToISO(raw,zone);if(new Date(runAt).getTime()<=Date.now())throw new Error("Choose a future date and time.");const result=await apiRequest(groupPath("/schedules"),{method:"POST",body:JSON.stringify({message:data.message,frequency:data.frequency||"once",run_at:runAt,timezone:zone,buttons:data.buttons||[]})});await loadSchedules();return result;}
async function sendBroadcast(data){requireGroup();const result=await apiRequest(groupPath("/broadcast"),{method:"POST",body:JSON.stringify(data)});showMessage(result.message||"Broadcast sent.");return result;}
async function scheduleBroadcast(data){return createSchedule({message:data.message,frequency:"once",run_at:data.run_at||data.scheduled_for,timezone:data.timezone||document.getElementById("scheduleTimezone")?.value||"Africa/Kampala",buttons:data.buttons||[]});}
async function createButton(data){requireGroup();const result=await apiRequest(groupPath("/buttons"),{method:"POST",body:JSON.stringify(data)});await loadButtons();return result;}
async function revokePermanentControlLink(){requireGroup();return apiRequest(groupPath("/control-link/revoke"),{method:"POST",body:JSON.stringify({})});}
window.RACAAL={showMessage,saveCommentsConfig,createSchedule,sendBroadcast,scheduleBroadcast,createButton,revokePermanentControlLink,get sessionPermanent(){return sessionPermanent;},loadSchedules,loadButtons};

function setupHandlers(){
  ["saveTop","saveBottom"].forEach(id=>{const b=document.getElementById(id);if(b)b.addEventListener("click",()=>saveSettings(b).catch(e=>showMessage(e.message,true)));});
  const saveCommentsButton=document.getElementById("saveComments");if(saveCommentsButton)saveCommentsButton.addEventListener("click",async()=>{try{await saveCommentsConfig({enabled:document.getElementById("commentsEnabled")?.checked,text:document.getElementById("commentText")?.value,button_text:document.getElementById("commentButtonText")?.value,url:document.getElementById("commentUrl")?.value});}catch(e){showMessage(e.message,true);}});
  const createScheduleButton=document.getElementById("createSchedule");if(createScheduleButton)createScheduleButton.addEventListener("click",async()=>{try{await createSchedule({message:document.getElementById("scheduleMessage")?.value,frequency:document.getElementById("scheduleFrequency")?.value,run_at:document.getElementById("scheduleTime")?.value,timezone:document.getElementById("scheduleTimezone")?.value,buttons:buttonFromFields(document.getElementById("scheduleButtonText")?.value,document.getElementById("scheduleButtonUrl")?.value)});showMessage("Schedule saved. The Telegram bot will deliver it when due.");}catch(e){showMessage(e.message,true);}});
  const send=document.getElementById("sendBroadcast");if(send)send.addEventListener("click",async()=>{try{await sendBroadcast({message:document.getElementById("broadcastMessage")?.value,buttons:buttonFromFields(document.getElementById("broadcastButtonText")?.value,document.getElementById("broadcastButtonUrl")?.value)});}catch(e){showMessage(e.message,true);}});
  const scheduleBroadcastButton=document.getElementById("scheduleBroadcast");if(scheduleBroadcastButton)scheduleBroadcastButton.addEventListener("click",async()=>{try{await scheduleBroadcast({message:document.getElementById("broadcastMessage")?.value,run_at:document.getElementById("broadcastScheduleTime")?.value,buttons:buttonFromFields(document.getElementById("broadcastButtonText")?.value,document.getElementById("broadcastButtonUrl")?.value)});showMessage("Broadcast scheduled.");}catch(e){showMessage(e.message,true);}});
  const createButtonButton=document.getElementById("createButton");if(createButtonButton)createButtonButton.addEventListener("click",async()=>{try{await createButton({text:document.getElementById("buttonLabel")?.value,url:document.getElementById("buttonUrl")?.value});showMessage("Button saved.");}catch(e){showMessage(e.message,true);}});
  const revoke=document.getElementById("revokeControlLink");if(revoke)revoke.addEventListener("click",async()=>{if(!confirm("Revoke this permanent Control Center link?"))return;try{await revokePermanentControlLink();sessionStorage.removeItem("racaal_control_session");sessionStorage.removeItem("racaal_session_permanent");controlSession="";const s=document.getElementById("controlLinkStatus");if(s)s.textContent="Link revoked. Request a new private link from the Telegram bot.";showMessage("Permanent link revoked.");}catch(e){showMessage(e.message,true);}});
}
async function init(){
  try{await verifyPermanentToken();}catch(e){showMessage(e.message,true);const status=document.getElementById("controlLinkStatus");if(status)status.textContent=e.message;return;}
  updateGroupDisplay();setupHandlers();
  if(!groupId||!controlSession){showMessage("Open the private Control Center link sent by the RACAAL bot to verify this group.",true);return;}
  try{await loadSettings();await Promise.all([loadGroups(),loadSchedules(),loadButtons()]);const status=document.getElementById("controlLinkStatus");if(status)status.textContent=sessionPermanent?"✓ Permanent Control Center session connected.":"✓ Control Center session connected.";}catch(e){showMessage(e.message,true);}
}
document.addEventListener("DOMContentLoaded",init);
