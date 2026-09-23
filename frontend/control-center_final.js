const API_BASE = "https://racaal-al-control.onrender.com";

/*
===========================================================
RACAAL AI — CENTRAL CONTROL CENTER FRONTEND
===========================================================

This file is the browser-side controller for the RACAAL
Control Center.

IMPORTANT:
- Do NOT put Supabase service-role keys here.
- Do NOT put OpenAI API keys here.
- Do NOT put Telegram bot tokens here.
- Platform authority and business rules belong in the backend.
- Customer/group settings are stored through the RACAAL API.

Architecture:

Control Center
      ↓
RACAAL Control API
      ↓
Supabase
      ↓
Telegram / WhatsApp / Website adapters
      ↓
RACAAL AI Engine
      ↓
RACAAL Modules
===========================================================
*/


/* =========================================================
   PAGE STATE
========================================================= */

const params = new URLSearchParams(window.location.search);

const groupId =
  params.get("group_id") ||
  null;

const controlSession =
  sessionStorage.getItem("racaal_control_session") ||
  "";

if (!groupId || !controlSession) {
  console.warn("RACAAL Control Center requires a verified Telegram session.");
}

const messageBox =
  document.getElementById("message");

const inputs = [
  ...document.querySelectorAll("[data-path]")
];

let currentSettings = {};
let isSaving = false;
let isLoading = false;
let isLoadingTelegramGroups = false;


/* =========================================================
   BASIC HELPERS
========================================================= */

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

  return pathParts(path).reduce(
    (value, key) => value?.[key],
    obj
  );
}


/* =========================================================
   USER MESSAGE
========================================================= */

function showMessage(text, error = false) {

  if (!messageBox) {

    console.log(
      error ? "RACAAL ERROR:" : "RACAAL:",
      text
    );

    return;
  }

  messageBox.hidden = false;

  messageBox.textContent = text;

  messageBox.className =
    error
      ? "message error"
      : "message";

  clearTimeout(showMessage.timer);

  showMessage.timer = setTimeout(() => {

    messageBox.hidden = true;

  }, 5000);
}


/* =========================================================
   BUTTON STATE
========================================================= */

function setButtonBusy(button, busy, busyText) {

  if (!button) {
    return;
  }

  if (busy) {

    if (!button.dataset.originalText) {

      button.dataset.originalText =
        button.textContent;
    }

    button.disabled = true;

    if (busyText) {

      button.textContent =
        busyText;
    }

  } else {

    button.disabled = false;

    if (button.dataset.originalText) {

      button.textContent =
        button.dataset.originalText;
    }
  }
}


/* =========================================================
   API REQUEST HELPER
========================================================= */

async function apiRequest(
  path,
  options = {}
) {

  const url =
    `${API_BASE}${path}`;

  console.log(
    "RACAAL API REQUEST:",
    options.method || "GET",
    url
  );

  const response =
    await fetch(url, {

      ...options,

      headers: {

        "Accept":
          "application/json",

        ...(options.body
          ? {
              "Content-Type":
                "application/json"
            }
          : {}),

        ...(controlSession
          ? {
              "X-RACAAL-SESSION":
                controlSession
            }
          : {}),

        ...(options.headers || {})
      }
    });

  const responseText =
    await response.text();

  console.log(
    "RACAAL API STATUS:",
    response.status
  );

  console.log(
    "RACAAL API RESPONSE:",
    responseText
  );

  let data = {};

  if (responseText) {

    try {

      data =
        JSON.parse(responseText);

    } catch {

      data = {
        raw: responseText
      };
    }
  }

  if (!response.ok) {

    const errorMessage =
      data?.error ||
      data?.message ||
      responseText ||
      `HTTP ${response.status}`;

    throw new Error(
      errorMessage
    );
  }

  return data;
}


/* =========================================================
   SETTINGS VALUE HANDLING
========================================================= */

function readValue(el) {

  if (el.type === "checkbox") {

    return el.checked;
  }

  if (el.type === "number") {

    const value =
      Number(el.value);

    return Number.isFinite(value)
      ? value
      : 0;
  }

  if (
    el.tagName === "TEXTAREA" &&
    [
      "protection.blacklist",
      "protection.whitelist"
    ].includes(el.dataset.path)
  ) {

    return el.value
      .split("\n")
      .map(item => item.trim())
      .filter(Boolean);
  }

  return el.value;
}


function writeValue(el, value) {

  if (el.type === "checkbox") {

    el.checked =
      Boolean(value);

    return;
  }

  if (
    el.tagName === "TEXTAREA" &&
    Array.isArray(value)
  ) {

    el.value =
      value.join("\n");

    return;
  }

  if (
    value !== undefined &&
    value !== null
  ) {

    el.value =
      value;
  }
}


/* =========================================================
   SETTINGS COLLECTION
========================================================= */

function collectSettings() {

  const settings = {};

  inputs.forEach(el => {

    const path =
      el.dataset.path;

    if (!path) {
      return;
    }

    setNested(
      settings,
      path,
      readValue(el)
    );

  });

  return settings;
}


function applySettings(settings) {

  if (
    !settings ||
    typeof settings !== "object"
  ) {

    throw new Error(
      "Invalid settings received from the API."
    );
  }

  inputs.forEach(el => {

    const path =
      el.dataset.path;

    if (!path) {
      return;
    }

    const value =
      getNested(
        settings,
        path
      );

    if (
      value !== undefined &&
      value !== null
    ) {

      writeValue(
        el,
        value
      );
    }

  });

  currentSettings =
    structuredClone(settings);
}


/* =========================================================
   GROUP INFORMATION
========================================================= */

function updateGroupDisplay() {

  const groupIdElement =
    document.getElementById("groupId");

  if (groupIdElement) {
    groupIdElement.textContent =
      groupId
        ? `Group ID: ${groupId}`
        : "Group ID: not verified";
  }

  const telegramGroupIdInput =
    document.getElementById("telegramGroupId");

  if (telegramGroupIdInput) {
    telegramGroupIdInput.value = groupId || "";
    telegramGroupIdInput.readOnly = true;
  }
}
async function registerTelegramGroup() {

  showMessage(
    "Manual Group ID registration is disabled. Add RACAAL to the Telegram group and use the private Control Center button.",
    true
  );
}

