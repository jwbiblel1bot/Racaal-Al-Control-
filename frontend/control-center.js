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
  "demo-group";

const messageBox =
  document.getElementById("message");

const inputs = [
  ...document.querySelectorAll("[data-path]")
];

let currentSettings = {};
let isSaving = false;
let isLoading = false;


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
      button.textContent = busyText;
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
        "Accept": "application/json",

        ...(options.body
          ? {
              "Content-Type":
                "application/json"
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

    el.value = value;
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
    document.getElementById(
      "groupId"
    );

  if (groupIdElement) {

    groupIdElement.textContent =
      `Group ID: ${groupId}`;
  }

  const telegramGroupIdInput =
    document.getElementById(
      "telegramGroupId"
    );

  if (
    telegramGroupIdInput &&
    groupId !== "demo-group"
  ) {

    telegramGroupIdInput.value =
      groupId;
  }
}


/* =========================================================
   LOAD GROUP SETTINGS
========================================================= */

async function loadGroupSettings() {

  if (isLoading) {
    return;
  }

  isLoading = true;

  try {

    updateGroupDisplay();

    const url =
      `/control/groups/` +
      `${encodeURIComponent(groupId)}` +
      `/settings`;

    const data =
      await apiRequest(url);

    if (!data.settings) {

      throw new Error(
        "API response does not contain settings."
      );
    }

    applySettings(
      data.settings
    );

    showMessage(
      "Group settings loaded."
    );

    updateTelegramStatus(
      "Group settings are connected to RACAAL Control."
    );

  } catch (error) {

    console.error(
      "LOAD GROUP SETTINGS ERROR:",
      error
    );

    showMessage(
      `Could not load settings: ${error.message}`,
      true
    );

    updateTelegramStatus(
      "Unable to load group configuration."
    );

  } finally {

    isLoading = false;
  }
}


/* =========================================================
   SAVE GROUP SETTINGS
========================================================= */

async function saveGroupSettings() {

  if (isSaving) {
    return;
  }

  isSaving = true;

  const saveTop =
    document.getElementById(
      "saveTop"
    );

  const saveBottom =
    document.getElementById(
      "saveBottom"
    );

  setButtonBusy(
    saveTop,
    true,
    "Saving..."
  );

  setButtonBusy(
    saveBottom,
    true,
    "Saving..."
  );

  try {

    const settings =
      collectSettings();

    console.log(
      "RACAAL SETTINGS TO SAVE:",
      settings
    );

    const url =
      `/control/groups/` +
      `${encodeURIComponent(groupId)}` +
      `/settings`;

    const data =
      await apiRequest(
        url,
        {
          method: "PUT",

          body: JSON.stringify({
            settings
          })
        }
      );

    if (!data.settings) {

      throw new Error(
        "API response does not contain saved settings."
      );
    }

    applySettings(
      data.settings
    );

    showMessage(
      "Group settings saved permanently."
    );

  } catch (error) {

    console.error(
      "SAVE GROUP SETTINGS ERROR:",
      error
    );

    showMessage(
      `Could not save settings: ${error.message}`,
      true
    );

  } finally {

    isSaving = false;

    setButtonBusy(
      saveTop,
      false
    );

    setButtonBusy(
      saveBottom,
      false
    );
  }
}


/* =========================================================
   TELEGRAM STATUS
========================================================= */

function updateTelegramStatus(text) {

  const statusText =
    document.getElementById(
      "telegramStatusText"
    );

  if (statusText) {

    statusText.textContent =
      text;
  }
}


/* =========================================================
   TELEGRAM GROUP REGISTRATION
========================================================= */

/*
IMPORTANT:

This frontend is prepared for the Telegram registration
API, but the actual registration authority belongs in the
backend.

The backend must eventually verify:

1. Telegram group ID
2. Telegram bot membership
3. Bot permissions
4. Customer/account ownership
5. Super Admin rules
6. Existing group registration
7. Subscription/trial permissions

The browser must NOT decide those things by itself.
*/

async function registerTelegramGroup() {

  const button =
    document.getElementById(
      "connectTelegram"
    );

  const input =
    document.getElementById(
      "telegramGroupId"
    );

  if (!input) {

    showMessage(
      "Telegram Group ID field was not found.",
      true
    );

    return;
  }

  const enteredGroupId =
    input.value.trim();

  if (!enteredGroupId) {

    showMessage(
      "Enter the Telegram Group ID before registering the group.",
      true
    );

    return;
  }

  /*
  Telegram supergroup IDs normally begin with -100.
  We do not invent an ID. We only perform a basic format
  check here. Final verification belongs to the backend.
  */

  if (
    !/^-?\d+$/.test(
      enteredGroupId
    )
  ) {

    showMessage(
      "The Telegram Group ID must be a valid numeric Telegram ID.",
      true
    );

    return;
  }

  setButtonBusy(
    button,
    true,
    "Registering..."
  );

  updateTelegramStatus(
    "Registering Telegram group..."
  );

  try {

    /*
    This endpoint will be implemented in the RACAAL
    Control backend.

    The backend—not this JavaScript—will perform the
    secure registration and verification.
    */

    const data =
      await apiRequest(
        "/control/telegram/register",
        {
          method: "POST",

          body: JSON.stringify({
            group_id:
              enteredGroupId
          })
        }
      );

    const registeredGroupId =
      data.group_id ||
      enteredGroupId;

    updateTelegramStatus(
      data.message ||
      "Telegram group registered successfully."
    );

    showMessage(
      `Telegram group ${registeredGroupId} is registered.`
    );

    /*
    If the backend returns the canonical group ID,
    update the browser URL so the Control Center opens
    directly for that group.
    */

    if (
      registeredGroupId &&
      registeredGroupId !== groupId
    ) {

      const newUrl =
        `${window.location.pathname}` +
        `?group_id=` +
        encodeURIComponent(
          registeredGroupId
        );

      window.history.replaceState(
        {},
        "",
        newUrl
      );

      /*
      Reload the group's settings using the newly
      registered ID without forcing a full page reload.
      */

      await loadGroupSettings();
    }

  } catch (error) {

    console.error(
      "TELEGRAM REGISTRATION ERROR:",
      error
    );

    updateTelegramStatus(
      "Telegram registration could not be completed."
    );

    showMessage(
      `Telegram registration failed: ${error.message}`,
      true
    );

  } finally {

    setButtonBusy(
      button,
      false
    );
  }
}


/* =========================================================
   API HEALTH CHECK
========================================================= */

async function checkControlApi() {

  try {

    const data =
      await apiRequest(
        "/health"
      );

    console.log(
      "RACAAL CONTROL API HEALTH:",
      data
    );

    return data;

  } catch (error) {

    console.error(
      "RACAAL CONTROL API HEALTH ERROR:",
      error
    );

    return null;
  }
}


/* =========================================================
   FUTURE CENTRAL PLATFORM CONTROL INTERFACE
========================================================= */

/*
These functions establish the frontend structure for the
future RACAAL platform.

They intentionally do NOT contain business rules.

Future backend areas can include:

/control/platform
/control/super-admin
/control/customers
/control/groups
/control/telegram
/control/whatsapp
/control/facebook
/control/website
/control/modules
/control/subscriptions
/control/payments
/control/analytics
/control/white-label
/control/ai
/control/security

The frontend can later call those secure endpoints.
*/


async function getPlatformStatus() {

  return apiRequest(
    "/control/platform/status"
  );
}


async function getCurrentAccount() {

  return apiRequest(
    "/control/account"
  );
}


async function getMyPermissions() {

  return apiRequest(
    "/control/permissions"
  );
}


/* =========================================================
   EVENT HANDLERS
========================================================= */

const saveTop =
  document.getElementById(
    "saveTop"
  );

if (saveTop) {

  saveTop.addEventListener(
    "click",
    saveGroupSettings
  );
}


const saveBottom =
  document.getElementById(
    "saveBottom"
  );

if (saveBottom) {

  saveBottom.addEventListener(
    "click",
    saveGroupSettings
  );
}


const connectTelegram =
  document.getElementById(
    "connectTelegram"
  );

if (connectTelegram) {

  connectTelegram.addEventListener(
    "click",
    registerTelegramGroup
  );
}


/* =========================================================
   STARTUP
========================================================= */

async function initializeControlCenter() {

  console.log(
    "========================================"
  );

  console.log(
    "RACAAL AI CONTROL CENTER"
  );

  console.log(
    "Group:",
    groupId
  );

  console.log(
    "API:",
    API_BASE
  );

  console.log(
    "========================================"
  );

  updateGroupDisplay();

  /*
  Check the API first.
  This does not expose any secret credentials.
  */

  const health =
    await checkControlApi();

  if (!health) {

    showMessage(
      "RACAAL Control API is not responding.",
      true
    );

  }

  /*
  Load the selected group's persistent settings.
  */

  await loadGroupSettings();
}


initializeControlCenter();
