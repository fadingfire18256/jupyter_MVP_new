// 由 notebooks/05_接成服務.ipynb 產生；請修改來源儲存格。
function cycleAdult() {
  const order = { off: "true", true: "false", false: "off" };
  state.filters.adult = order[state.filters.adult];
  render();
}

function toggleGenrePanel() {
  state.genrePanelOpen = !state.genrePanelOpen;
  if (!state.genrePanelOpen) state.filters.genreId = null;  // 收起來就順手清掉選擇
  render();
}

function selectGenre(id) {
  state.filters.genreId = state.filters.genreId === id ? null : id;
  render();
}

/** 排序鍵按一下換一種：不排 -> 高到低 -> 低到高 -> 不排。
 *  同時把另外兩個鍵關掉，因為一次只排一個欄位。 */
function cycleSlider(key) {
  const current = state.filters[key].mode;
  const next = current === "off" ? "desc" : current === "desc" ? "asc" : "off";
  for (const other of SORT_KEYS) {
    state.filters[other] = other === key
      ? { mode: next, threshold: next === "off" ? null : state.filters[key].threshold }
      : { mode: "off", threshold: null };
  }
  render();
}

function setThreshold(key, value) {
  state.filters[key].threshold = value;
  render();
}

function resetThreshold(key) {
  state.filters[key].threshold = null;
  render();
}

function addToWatchlist(movie) {
  if (inWatchlist(movie)) return;
  state.watchlist = [...state.watchlist, movie];
  saveWatchlist();
  render();
}

function removeFromWatchlist(movie) {
  state.watchlist = state.watchlist.filter((item) => !sameMovie(item, movie));
  saveWatchlist();
  render();
}

/** 點一部電影：開詳細資料，同時記進「最近瀏覽」（只留最新 10 筆）。 */
function selectMovie(movie) {
  state.selected = movie;
  state.recent = [movie, ...state.recent.filter((item) => !sameMovie(item, movie))].slice(0, 10);
  render();
}

function closeModal() {
  state.selected = null;
  render();
}

async function sendChat(text) {
  const message = (text || "").trim();
  if (!message || state.chat.sending) return;

  state.chat.messages = [...state.chat.messages, { role: "user", content: message }];
  state.chat.sending = true;
  $("chat-input").value = "";
  render();

  try {
    const response = await fetch(`${API}/chat/`, {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({
        movies: visibleMovies().slice(0, 200),
        genres: state.genres,
        messages: [{ role: "user", content: message }],
        session_id: state.chat.sessionId,
      }),
    });
    const data = await response.json();
    noteMissingKey(data);
    state.chat.messages = [...state.chat.messages, {
      role: "assistant",
      content: data.reply || data.error || "（無回應）",
    }];
  } catch {
    state.chat.messages = [...state.chat.messages, {
      role: "assistant",
      content: "無法連線聊天服務",
    }];
  }
  state.chat.sending = false;
  render();
}


/* --------------------------------------------------------------------------
 * 畫面
 *
 * 沒有框架，所以自己處理「不要重畫沒變的東西」：
 * 每一區先算一個簽章，跟上次一樣就跳過。
 * 這不只是省效能 —— 一直重建 <img> 會讓海報閃爍，
 * 而且重建 <input> 會把游標和拖曳中的滑桿弄掉。
 * -------------------------------------------------------------------------- */
