const API_BASE = "https://racaal-al-control.onrender.com";

const params = new URLSearchParams(location.search);
const groupId = params.get("group_id") || "demo-group";

const messageBox = document.getElementById("message");
const inputs = [...document.querySelectorAll("[data-path]")];

function pathParts(path) {
  return path.split(".");
}

function setNested(obj, path, value) {
  const parts = pathParts(path);
  let cur = obj;

  for (let i = 0; i < parts.length - 1; i++) {
    cur[parts[i]] ??= {};
    cur = cur[parts[i]];
  }

  cur[parts.at(-1)] = value;
}

function getNested(obj, path) {
  return pathParts(path).reduce((v, k) => v?.[k], obj);
}

function showMessage(text, error = false) {
  messageBox.hidden = false;
  messageBox.textContent = text;
  messageBox.className = error ? "message error" : "message";

  setTimeout(() => {
    messageBox.hidden = true;
  }, 5000);
}

function readValue(el) {
  if (el.type === "checkbox") {
    return el.checked;
  }

  if (el.type === "number") {
    return Number(el.value);
  }

  if (
    el.tagName === "TEXTAREA" &&
    ["protection.blacklist", "protection.whitelist"].includes(el.dataset.path)
  ) {
    return el.value
      .split("\n")
      .map(x => x.trim())
      .filter(Boolean);
  }

  return el.value;
}

function writeValue(el, value) {
  if (el.type === "checkbox") {
    el.checked = Boolean(value);
  } else if (el.tagName === "TEXTAREA" && Array.isArray(value)) {
    el.value = value.join("\n");
  } else if (value !== undefined && value !== null) {
    el.value = value;
  }
}

function collectSettings() {
  const settings = {};

  inputs.forEach(el => {
    setNested(settings, el.dataset.path, readValue(el));
  });

  return settings;
}

function applySettings(settings) {
  inputs.forEach(el => {
    writeValue(el, getNested(settings, el.dataset.path));
  });
}

async function load() {
  document.getElementById("groupId").textContent = `Group ID: ${groupId}`;

  try {
    const url =
      `${API_BASE}/control/groups/${encodeURIComponent(groupId)}/settings`;

    console.log("Loading settings from:", url);

    const r = await fetch(url);

    const responseText = await r.text();

    console.log("Load HTTP status:", r.status);
    console.log("Load response:", responseText);

    if (!r.ok) {
      throw new Error(`HTTP ${r.status}: ${responseText}`);
    }

    const data = JSON.parse(responseText);

    if (!data.settings) {
      throw new Error("API response does not contain settings.");
    }

    applySettings(data.settings);

    showMessage("Group settings loaded.");
  } catch (e) {
    console.error("LOAD ERROR:", e);

    showMessage(
      `Could not load settings: ${e.message}`,
      true
    );
  }
}

async function save() {
  const settings = collectSettings();

  const url =
    `${API_BASE}/control/groups/${encodeURIComponent(groupId)}/settings`;

  console.log("Saving settings to:", url);
  console.log("Settings:", settings);

  try {
    const r = await fetch(url, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        settings: settings
      })
    });

    const responseText = await r.text();

    console.log("Save HTTP status:", r.status);
    console.log("Save response:", responseText);

    if (!r.ok) {
      throw new Error(`HTTP ${r.status}: ${responseText}`);
    }

    const data = JSON.parse(responseText);

    if (!data.settings) {
      throw new Error("API response does not contain saved settings.");
    }

    applySettings(data.settings);

    showMessage("Group settings saved permanently.");
  } catch (e) {
    console.error("SAVE ERROR:", e);

    showMessage(
      `Could not save settings: ${e.message}`,
      true
    );
  }
}

document
  .getElementById("saveTop")
  .addEventListener("click", save);

document
  .getElementById("saveBottom")
  .addEventListener("click", save);

load();
