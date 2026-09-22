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
   TELEGRAM GROUP LIST CONTAINER
========================================================= */

/*
The frontend creates its own group-list container if the
HTML does not already provide one.

This means the existing control-center.html does not have
to be destroyed or rewritten just to support My Telegram
Groups.
*/

function getTelegramGroupsContainer() {

  let container =
    document.getElementById(
      "telegramGroupsList"
    );

  if (container) {

    return container;
  }

  container =
    document.createElement(
      "div"
    );

  container.id =
    "telegramGroupsList";

  container.style.marginTop =
    "16px";

  /*
  Try to place the list near the existing
  "My Telegram Groups" area.
  */

  const candidates = [
    document.getElementById(
      "myTelegramGroups"
    ),
    document.querySelector(
      "[data-section='telegram-groups']"
    ),
    document.querySelector(
      ".telegram-groups"
    )
  ];

  const target =
    candidates.find(
      element => element
    );

  if (target) {

    target.appendChild(
      container
    );

  } else {

    /*
    Fallback: place it near the top of the
    Control Center page.
    */

    const firstMain =
      document.querySelector(
        "main"
      );

    if (firstMain) {

      firstMain.prepend(
        container
      );

    } else {

      document.body.prepend(
        container
      );
    }
  }

  return container;
}


/* =========================================================
   TELEGRAM GROUP LIST STYLING
========================================================= */

function ensureTelegramGroupsStyles() {

  if (
    document.getElementById(
      "racaalTelegramGroupsStyles"
    )
  ) {

    return;
  }

  const style =
    document.createElement(
      "style"
    );

  style.id =
    "racaalTelegramGroupsStyles";

  style.textContent = `

    #telegramGroupsList {
      display: flex;
      flex-direction: column;
      gap: 12px;
      width: 100%;
      box-sizing: border-box;
    }

    .racaal-telegram-group-card {
      border: 1px solid #d9dfe7;
      border-radius: 12px;
      padding: 16px;
      background: #ffffff;
      box-sizing: border-box;
    }

    .racaal-telegram-group-title {
      font-size: 17px;
      font-weight: 600;
      margin-bottom: 6px;
    }

    .racaal-telegram-group-id {
      font-size: 14px;
      opacity: 0.75;
      margin-bottom: 6px;
      word-break: break-word;
    }

    .racaal-telegram-group-status {
      font-size: 13px;
      margin-bottom: 12px;
      opacity: 0.8;
    }

    .racaal-telegram-group-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .racaal-manage-group-button,
    .racaal-refresh-groups-button {
      cursor: pointer;
      border: 0;
      border-radius: 8px;
      padding: 9px 14px;
      font-size: 14px;
    }

    .racaal-manage-group-button {
      background: #111827;
      color: #ffffff;
    }

    .racaal-refresh-groups-button {
      background: #e5e7eb;
      color: #111827;
    }

    .racaal-telegram-empty {
      padding: 14px;
      border-radius: 10px;
      background: #f6f7f9;
      color: #555;
    }

    .racaal-telegram-loading {
      padding: 14px;
      opacity: 0.75;
    }

  `;

  document.head.appendChild(
    style
  );
}


/* =========================================================
   TELEGRAM GROUP DATA NORMALIZATION
========================================================= */

/*
The backend may return:

{
  "groups": [...]
}

or:

{
  "telegram_groups": [...]
}

or directly:

[...]

This helper makes the frontend tolerant of those formats.
*/

function normalizeTelegramGroups(data) {

  if (Array.isArray(data)) {

    return data;
  }

  if (
    Array.isArray(
      data?.groups
    )
  ) {

    return data.groups;
  }

  if (
    Array.isArray(
      data?.telegram_groups
    )
  ) {

    return data.telegram_groups;
  }

  if (
    Array.isArray(
      data?.registered_groups
    )
  ) {

    return data.registered_groups;
  }

  return [];
}


/* =========================================================
   TELEGRAM GROUP DISPLAY HELPERS
========================================================= */

function getTelegramGroupId(group) {

  return String(
    group?.group_id ??
    group?.telegram_group_id ??
    group?.id ??
    ""
  );
}


function getTelegramGroupName(group) {

  return (
    group?.group_name ??
    group?.name ??
    group?.title ??
    group?.telegram_group_name ??
    "Telegram Group"
  );
}


function getTelegramGroupStatus(group) {

  return (
    group?.status ??
    group?.connection_status ??
    group?.state ??
    "registered"
  );
}


function getTelegramGroupRegisteredAt(group) {

  return (
    group?.registered_at ??
    group?.created_at ??
    ""
  );
}


/* =========================================================
   TELEGRAM GROUP LIST RENDERING
========================================================= */

function renderTelegramGroups(groups) {

  ensureTelegramGroupsStyles();

  const container =
    getTelegramGroupsContainer();

  container.innerHTML = "";

  if (!groups.length) {

    const empty =
      document.createElement(
        "div"
      );

    empty.className =
      "racaal-telegram-empty";

    empty.textContent =
      "No Telegram groups connected yet.";

    container.appendChild(
      empty
    );

    return;
  }

  groups.forEach(group => {

    const id =
      getTelegramGroupId(
        group
      );

    if (!id) {
      return;
    }

    const name =
      getTelegramGroupName(
        group
      );

    const status =
      getTelegramGroupStatus(
        group
      );

    const registeredAt =
      getTelegramGroupRegisteredAt(
        group
      );

    const card =
      document.createElement(
        "div"
      );

    card.className =
      "racaal-telegram-group-card";

    const title =
      document.createElement(
        "div"
      );

    title.className =
      "racaal-telegram-group-title";

    title.textContent =
      name;

    const idElement =
      document.createElement(
        "div"
      );

    idElement.className =
      "racaal-telegram-group-id";

    idElement.textContent =
      `Group ID: ${id}`;

    const statusElement =
      document.createElement(
        "div"
      );

    statusElement.className =
      "racaal-telegram-group-status";

    statusElement.textContent =
      registeredAt
        ? `Status: ${status} • Registered: ${registeredAt}`
        : `Status: ${status}`;

    const actions =
      document.createElement(
        "div"
      );

    actions.className =
      "racaal-telegram-group-actions";

    const manageButton =
      document.createElement(
        "button"
      );

    manageButton.type =
      "button";

    manageButton.className =
      "racaal-manage-group-button";

    manageButton.textContent =
      "Manage";

    manageButton.addEventListener(
      "click",
      () => {

        openTelegramGroup(
          id
        );

      }
    );

    actions.appendChild(
      manageButton
    );

    card.appendChild(
      title
    );

    card.appendChild(
      idElement
    );

    card.appendChild(
      statusElement
    );

    card.appendChild(
      actions
    );

    container.appendChild(
      card
    );

  });
}


/* =========================================================
   OPEN / MANAGE TELEGRAM GROUP
========================================================= */

function openTelegramGroup(
  selectedGroupId
) {

  if (!selectedGroupId) {

    showMessage(
      "The selected Telegram group does not have a valid Group ID.",
      true
    );

    return;
  }

  const newUrl =
    `${window.location.pathname}` +
    `?group_id=` +
    encodeURIComponent(
      selectedGroupId
    );

  /*
  Use normal navigation so the whole Control Center
  initializes cleanly with the selected group.
  */

  window.location.href =
    newUrl;
}


/* =========================================================
   LOAD MY TELEGRAM GROUPS
========================================================= */

async function loadTelegramGroups() {

  if (isLoadingTelegramGroups) {

    return;
  }

  isLoadingTelegramGroups = true;

  ensureTelegramGroupsStyles();

  const container =
    getTelegramGroupsContainer();

  container.innerHTML =
    "";

  const loading =
    document.createElement(
      "div"
    );

  loading.className =
    "racaal-telegram-loading";

  loading.textContent =
    "Loading Telegram groups...";

  container.appendChild(
    loading
  );

  try {

    const data =
      await apiRequest(
        "/control/telegram/groups"
      );

    console.log(
      "RACAAL TELEGRAM GROUPS:",
      data
    );

    const groups =
      normalizeTelegramGroups(
        data
      );

    renderTelegramGroups(
      groups
    );

    console.log(
      `RACAAL: ${groups.length} Telegram group(s) loaded.`
    );

    return groups;

  } catch (error) {

    console.error(
      "LOAD TELEGRAM GROUPS ERROR:",
      error
    );

    container.innerHTML =
      "";

    const errorBox =
      document.createElement(
        "div"
      );

    errorBox.className =
      "racaal-telegram-empty";

    errorBox.textContent =
      `Could not load Telegram groups: ${error.message}`;

    container.appendChild(
      errorBox
    );

    showMessage(
      `Could not load Telegram groups: ${error.message}`,
      true
    );

    return [];

  } finally {

    isLoadingTelegramGroups =
      false;
  }
}


/* =========================================================
   TELEGRAM GROUP LIST HEADER / REFRESH
========================================================= */

function createTelegramGroupsRefreshButton() {

  if (
    document.getElementById(
      "refreshTelegramGroups"
    )
  ) {

    return;
  }

  const button =
    document.createElement(
      "button"
    );

  button.id =
    "refreshTelegramGroups";

  button.type =
    "button";

  button.className =
    "racaal-refresh-groups-button";

  button.textContent =
    "Refresh Groups";

  button.addEventListener(
    "click",
    async () => {

      setButtonBusy(
        button,
        true,
        "Refreshing..."
      );

      await loadTelegramGroups();

      setButtonBusy(
        button,
        false
      );
    }
  );

  const container =
    getTelegramGroupsContainer();

  /*
  Place refresh button immediately before
  the group cards.
  */

  container.parentNode?.insertBefore(
    button,
    container
  );
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
      await apiRequest(
        url
      );

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
  Basic frontend format validation only.
  Final verification belongs to the backend.
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
      data.telegram_group_id ||
      enteredGroupId;

    updateTelegramStatus(
      data.message ||
      "Telegram group registered successfully."
    );

    showMessage(
      `Telegram group ${registeredGroupId} is registered.`
    );

    /*
    Refresh My Telegram Groups immediately after
    successful registration.
    */

    await loadTelegramGroups();

    /*
    If the backend returns the canonical group ID,
    or the entered ID is different from the current
    page group, update the URL.
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
      Reload the selected group's settings.
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

    /*
  =========================================================
     VERIFIED TELEGRAM GROUP CHECK
  =========================================================

  The Telegram bot discovers the group automatically.

  The administrator must NOT manually enter a Group ID.

  The secure setup page passes the verified Group ID
  to the Control Center.
  =========================================================
  */

  if (!groupId) {

    console.warn(
      "RACAAL Control Center opened without a verified Telegram group."
    );

    showMessage(
      "No Telegram group has been selected. Please open the secure setup link sent by the RACAAL Telegram bot.",
      true
    );

    return;
  }

  updateGroupDisplay();

  /*
  Check the API first.
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
  Load the Telegram groups list.
  */

  await loadTelegramGroups();

  /*
  Add the refresh control.
  */

  createTelegramGroupsRefreshButton();

  /*
  Load the selected group's persistent settings.
  */

  await loadGroupSettings();
}


initializeControlCenter();
