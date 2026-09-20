const API_BASE = "https://racaal-al-control.onrender.com";
const params = new URLSearchParams(location.search);
const groupId = params.get("group_id") || "demo-group";

const messageBox = document.getElementById("message");
const inputs = [...document.querySelectorAll("[data-path]")];

function pathParts(path){ return path.split("."); }

function setNested(obj, path, value){
  const parts = pathParts(path);
  let cur = obj;
  for(let i=0;i<parts.length-1;i++){ cur[parts[i]] ??= {}; cur = cur[parts[i]]; }
  cur[parts.at(-1)] = value;
}

function getNested(obj, path){
  return pathParts(path).reduce((v,k)=>v?.[k], obj);
}

function showMessage(text, error=false){
  messageBox.hidden = false;
  messageBox.textContent = text;
  messageBox.className = error ? "message error" : "message";
  setTimeout(()=>messageBox.hidden=true, 3500);
}

function readValue(el){
  if(el.type === "checkbox") return el.checked;
  if(el.type === "number") return Number(el.value);
  if(el.tagName === "TEXTAREA" && ["protection.blacklist","protection.whitelist"].includes(el.dataset.path))
    return el.value.split("\n").map(x=>x.trim()).filter(Boolean);
  return el.value;
}

function writeValue(el, value){
  if(el.type === "checkbox") el.checked = Boolean(value);
  else if(el.tagName === "TEXTAREA" && Array.isArray(value)) el.value = value.join("\n");
  else if(value !== undefined && value !== null) el.value = value;
}

function collectSettings(){
  const settings = {};
  inputs.forEach(el => setNested(settings, el.dataset.path, readValue(el)));
  return settings;
}

function applySettings(settings){
  inputs.forEach(el => writeValue(el, getNested(settings, el.dataset.path)));
}

async function load(){
  document.getElementById("groupId").textContent = `Group ID: ${groupId}`;
  try{
    const r = await fetch(`${API_BASE}/control/groups/${encodeURIComponent(groupId)}/settings`);
    if(!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    applySettings(data.settings);
  }catch(e){
    showMessage("Using local defaults until the Control API is connected.", true);
  }
}

async function save(){
  try{
    const r = await fetch(`${API_BASE}/control/groups/${encodeURIComponent(groupId)}/settings`,{
      method:"PUT",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({settings:collectSettings()})
    });
    if(!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    applySettings(data.settings);
    showMessage("Group settings saved.");
  }catch(e){
    console.error(e);
    showMessage("Could not save settings. Check that the Control API is deployed.", true);
  }
}

document.getElementById("saveTop").addEventListener("click",save);
document.getElementById("saveBottom").addEventListener("click",save);
load();
