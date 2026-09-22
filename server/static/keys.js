// 由 notebooks/05_接成服務.ipynb 產生；請修改來源儲存格。
const KEY_FIELDS = [
  {
    id: "tmdb",
    label: "TMDB Read Access Token",
    apply: "https://www.themoviedb.org/settings/api",
    note: "在 TMDB 的 API 設定頁選 API 讀取存取權杖（Read Access Token），不是 API Key。",
  },
  {
    id: "gemini",
    label: "Gemini API Key",
    apply: "https://aistudio.google.com/apikey",
    note: "Google AI Studio 的 Create API key，速率限制按專案計算，同專案金鑰共用限制。",
  },
];

/** 後端回 401 時會告訴我們是哪一把不見了。 */
function noteMissingKey(data) {
  if (!data || !data.need_key) return false;
  state.keyMissing[data.need_key] = true;
  state.keyStatus[data.need_key] = false;
  return true;
}

async function loadKeyStatus() {
  try {
    const response = await fetch(`${API}/keys/`);
    const data = await response.json();
    if (response.ok && data.keys) {
      state.keyStatus = data.keys;
      state.dataMode = data.mode;
      const banner = $("data-mode");
      banner.textContent = data.mode === "demo"
        ? "示範資料｜虛構電影・聊天為固定回應，未呼叫 AI"
        : "真實 API｜電影與聊天資料由外部服務提供";
      banner.className = "data-mode " + (data.mode || "");

      for (const field of KEY_FIELDS) {
        if (data.keys[field.id]) state.keyMissing[field.id] = false;
      }
    }
  } catch {
    $("data-mode").textContent = "無法確認資料模式，請檢查本機服務。";
  }
  render();
}

function renderKeyButton() {
  const missing = state.dataMode === "demo" ? [] : KEY_FIELDS.filter((f) => state.keyStatus[f.id] === false);
  if (!changed("keyButton", missing.map((f) => f.id).join(","))) return;
  const button = $("key-open");
  button.className = missing.length ? "key-btn missing" : "key-btn";
  button.textContent = missing.length ? "⚠ 設定 API 金鑰" : "API 金鑰";
}

function openKeyDialog(message) {
  const host = $("key-modal-host");

  const fields = KEY_FIELDS.map((field) => {
    const on = state.keyStatus[field.id];
    return el("label", { class: "key-field" },
      el("div", { class: "key-field-head" },
        el("span", { class: "key-label", text: field.label }),
        el("span", {
          class: `key-state ${on ? "on" : "off"}`,
          text: on ? "已設定" : "未設定",
        }),
        el("a", {
          class: "key-link", href: field.apply,
          target: "_blank", rel: "noopener noreferrer",
          text: "去申請 →",
        })),
      el("input", {
        type: "password", class: "key-input", id: `key-input-${field.id}`,
        placeholder: on ? "留空表示沿用現在這一把" : "貼上你申請的金鑰",
        autocomplete: "off",
      }),
      el("div", { class: "key-note", text: field.note }));
  });

  const close = () => setChildren(host);

  setChildren(host, el("div", { class: "modal-overlay", onClick: close },
    el("div", { class: "modal-card", onClick: (event) => event.stopPropagation() },
      el("button", {
        type: "button", class: "modal-close", "aria-label": "關閉", text: "×", onClick: close,
      }),
      el("div", { class: "modal-section" },
        el("h3", { class: "modal-section-title", text: "API 金鑰設定" }),
        el("p", { class: "key-intro" },
          "示範模式使用固定資料，不需要金鑰。",
          el("br"),
          "真實 API 模式需填入自己的金鑰；同專案的金鑰共用配額。",
          el("br"),
          "存下去會寫進專案根目錄的 .env，伺服器馬上改用新的，不用重啟。"),
        fields,
        el("div", { class: "modal-footer" },
          el("span", {
            class: `key-message${message ? " error" : ""}`,
            id: "key-message",
            text: message || "",
          }),
          el("button", {
            type: "button", class: "key-save", id: "key-save",
            text: "儲存並重新載入", onClick: submitKeys,
          }))))));

  const first = KEY_FIELDS.find((f) => state.keyStatus[f.id] === false) || KEY_FIELDS[0];
  $(`key-input-${first.id}`).focus();
}

async function submitKeys() {
  const payload = {};
  for (const field of KEY_FIELDS) {
    const value = $(`key-input-${field.id}`).value.trim();
    if (value) payload[field.id] = value;
  }

  const message = $("key-message");
  if (Object.keys(payload).length === 0) {
    message.className = "key-message error";
    message.textContent = "兩欄都是空的，沒有東西可以存。";
    return;
  }

  const button = $("key-save");
  button.disabled = true;
  message.className = "key-message";
  message.textContent = "儲存中…";

  try {
    const response = await fetch(`${API}/keys/`, {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      message.className = "key-message error";
      message.textContent = data.error || "儲存失敗";
      button.disabled = false;
      return;
    }
    state.keyStatus = data.keys;
    state.keyMissing = { tmdb: false, gemini: false };
    setChildren($("key-modal-host"));
    reloadEverything();
  } catch {
    message.className = "key-message error";
    message.textContent = "無法連線到後端伺服器";
    button.disabled = false;
  }
}

/** 換過金鑰之後，把資料整個重抓一次。 */
function reloadEverything() {
  state.loadGeneration += 1;   // 讓還在跑的舊載入停下來，不然它們會繼續打 TMDB
  for (const cinema of CINEMAS) {
    state.cinemas[cinema.key] = {
      titles: [], movies: [], loading: true, error: "", enriching: false, tmdbError: "",
    };
  }
  state.genres = {};
  state.genreError = "";
  state.selected = null;
  movieNodes.clear();
  render();

  loadGenres();
  for (const cinema of CINEMAS) loadCinema(cinema);
}


/* --------------------------------------------------------------------------
 * 啟動
 * -------------------------------------------------------------------------- */
