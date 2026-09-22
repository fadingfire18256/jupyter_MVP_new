// 由 notebooks/05_接成服務.ipynb 產生；請修改來源儲存格。
const signatures = {};

function changed(name, value) {
  if (signatures[name] === value) return false;
  signatures[name] = value;
  return true;
}

let renderQueued = false;

/** 補資料時每回來一筆就重畫一次太浪費，合併到下一個畫面更新再處理。 */
function scheduleRender() {
  if (renderQueued) return;
  renderQueued = true;
  requestAnimationFrame(() => {
    renderQueued = false;
    render();
  });
}

function render() {
  const merged = mergedMovies();
  const visible = searchMovies(applyFilters(merged, state.filters), state.search);
  const limits = bounds(merged);

  renderWatchlist();
  renderRecent();
  renderCategoryButtons();
  renderGenreSubmenu();
  renderSliderBar(limits);
  renderMovieArea(visible);
  renderChat(visible);
  renderModal();
  renderKeyButton();
}


/* ---------- 左欄：待看清單 ---------- */
function renderWatchlist() {
  const list = state.watchlist;
  if (!changed("watchlist", list.map(movieId).join("|"))) return;

  const host = $("watchlist-block");
  setChildren(host,
    el("div", { class: "watchlist-header" },
      el("span", { class: "watchlist-title", text: "待看電影清單" }),
      el("span", { class: "watchlist-count", text: list.length })),
    list.length === 0
      ? el("div", { class: "watchlist-empty" }, "尚無待看電影", el("br"), "點擊電影的「加入待看清單」按鈕")
      : el("ul", { class: "watchlist-list" }, list.map((movie) => {
          const meta = movie.meta;
          return el("li", { class: "watchlist-item" },
            el("div", { class: "watchlist-item-top" },
              meta && meta.poster_path && el("img", {
                src: IMG_SMALL + meta.poster_path, alt: "",
                class: "watchlist-poster", loading: "lazy",
              }),
              el("div", { class: "watchlist-item-title", text: movie.title })),
            el("button", {
              type: "button", class: "watchlist-remove-btn", text: "刪除待看電影",
              onClick: () => removeFromWatchlist(movie),
            }));
        })));
}


/* ---------- 左欄：最近瀏覽 ---------- */
function renderRecent() {
  const list = state.recent;
  const signature = list.map(movieId).join("|") + "#" + state.watchlist.map(movieId).join("|");
  if (!changed("recent", signature)) return;

  const host = $("recent-block");
  setChildren(host,
    el("div", { class: "recent-header" },
      el("span", { class: "recent-title", text: "最近瀏覽電影" }),
      el("span", { class: "recent-count" }, list.length, "/10")),
    list.length === 0
      ? el("div", { class: "recent-empty", text: "點擊電影後會記錄在此" })
      : el("ul", { class: "recent-list" }, list.map((movie) => {
          const meta = movie.meta;
          const added = inWatchlist(movie);
          return el("li", { class: "recent-item" },
            el("button", {
              type: "button", class: "recent-item-main",
              onClick: () => selectMovie(movie),
            },
              meta && meta.poster_path && el("img", {
                src: IMG_SMALL + meta.poster_path, alt: "",
                class: "recent-poster", loading: "lazy",
              }),
              el("span", { class: "recent-item-title", text: movie.title })),
            el("button", {
              type: "button",
              class: `watchlist-add-btn recent-add${added ? " added" : ""}`,
              disabled: added,
              text: added ? "已加入" : "加入待看",
              onClick: () => addToWatchlist(movie),
            }));
        })));
}


/* ---------- 篩選列：五顆按鈕 ---------- */
function renderCategoryButtons() {
  const filters = state.filters;
  const signature = JSON.stringify(filters) + "#" + state.genrePanelOpen;
  if (!changed("categoryButtons", signature)) return;

  const adultBadge = filters.adult === "off" ? "" : filters.adult;

  setChildren($("category-buttons"), ...FILTER_BUTTONS.map((button) => {
    let active;
    let badge = "";

    if (button.type === "bool") {
      active = filters.adult !== "off";
      badge = adultBadge;
    } else if (button.type === "genre") {
      active = state.genrePanelOpen;
    } else {
      const filter = filters[button.key];
      active = filter.mode !== "off" || filter.threshold != null;
      const parts = [];
      if (filter.mode !== "off") parts.push(modeLabel(filter.mode));
      if (filter.threshold != null) parts.push(`≥${filter.threshold}`);
      badge = parts.join(" ");
    }

    return el("button", {
      type: "button",
      class: `category-btn${active ? " active" : ""}`,
      onClick: () => {
        if (button.type === "bool") cycleAdult();
        else if (button.type === "genre") toggleGenrePanel();
        else cycleSlider(button.key);
      },
    }, button.label, badge && el("span", { class: "mode-badge", text: badge }));
  }));
}


/* ---------- 篩選列：類型子選單 ---------- */
function renderGenreSubmenu() {
  const open = state.genrePanelOpen;
  const signature = `${open}|${state.filters.genreId}|${state.genreError}|${Object.keys(state.genres).length}`;
  if (!changed("genreSubmenu", signature)) return;

  const host = $("genre-host");
  if (!open) {
    setChildren(host);
    return;
  }

  setChildren(host,
    el("div", { class: "genre-submenu" },
    state.genreError && el("span", { class: "status error", text: state.genreError }),
    Object.entries(state.genres).map(([id, name]) => el("button", {
      type: "button",
      class: `genre-btn${Number(state.filters.genreId) === Number(id) ? " active" : ""}`,
      text: name,
      onClick: () => selectGenre(Number(id)),
    }))));
}


/* ---------- 篩選列：門檻滑桿 ---------- */
//
// 滑桿只有在「有排序鍵開著」的時候出現。
// 拖曳中每移動一格就會觸發重畫，這時候絕對不能重建 <input>，
// 不然滑鼠會跟拖曳中的滑桿斷開 —— 所以同一個鍵時只更新數值。
function renderSliderBar(limits) {
  const key = SORT_KEYS.find((name) => state.filters[name].mode !== "off");
  const host = $("slider-host");

  if (!key) {
    if (changed("sliderKey", "")) setChildren(host);
    return;
  }

  const spec = sliderSpec(key, limits);
  const rebuild = changed("sliderKey", key);

  if (rebuild) {
    setChildren(host,
    el("div", { class: "slider-bar" },
      el("label", { class: "slider-label", id: "slider-label" }),
      el("div", { class: "slider-row" },
        el("span", { class: "slider-bound", id: "slider-min" }),
        el("input", {
          type: "range", id: "slider-input",
          onInput: (event) => setThreshold(key, Number(event.target.value)),
        }),
        el("span", { class: "slider-bound", id: "slider-max" })),
      el("button", {
        type: "button", class: "slider-reset", text: "清除門檻",
        onClick: () => resetThreshold(key),
      })));
  }

  const filter = state.filters[key];
  setChildren($("slider-label"),
    filter.mode !== "off" && el("span", { class: "rank-tag" }, "ranking ", modeLabel(filter.mode)),
    spec.label);
  $("slider-min").textContent = spec.minLabel;
  $("slider-max").textContent = spec.maxLabel;

  const input = $("slider-input");
  input.min = spec.min;
  input.max = spec.max;
  input.step = spec.step;
  if (Number(input.value) !== spec.value) input.value = spec.value;
}

function sliderSpec(key, limits) {
  const threshold = state.filters[key].threshold;

  if (key === "popularity") {
    const max = Math.ceil(limits.popularityMax);
    const value = threshold ?? 0;
    return {
      label: ["熱門度 ≥ ", value, "（低於此值忽略）"],
      min: 0, max, step: 1, value, minLabel: "0", maxLabel: String(max),
    };
  }

  if (key === "voteAverage") {
    const value = threshold ?? 0;
    return {
      label: ["評分 ≥ ", value, "（低於此值忽略）"],
      min: 0, max: 10, step: 0.1, value, minLabel: "0", maxLabel: "10",
    };
  }

  // releaseDate：滑桿上跑的是月份序號，顯示的時候才換回「幾年幾月」
  const min = limits.yearMin * 12 + 1;
  const max = limits.yearMax * 12 + 12;
  const value = threshold ?? min;
  return {
    label: ["上映日期 ≥ ", monthLabel(value), "（早於此月忽略）"],
    min, max, step: 1, value,
    minLabel: monthLabel(min), maxLabel: monthLabel(max),
  };
}


/* ---------- 中欄：狀態訊息 + 電影清單 ---------- */
//
// 清單用「同一部電影就重用同一個 <li>」的方式更新。
// 補資料的過程中這個函式會被呼叫幾十次，每次都整份重建的話
// 海報會不停重新載入而閃爍，捲軸位置也會被拉回頂端。
const movieNodes = new Map();

function renderMovieArea(visible) {
  const stores = CINEMAS.map((cinema) => state.cinemas[cinema.key]);
  const loading = stores.some((store) => store.loading);
  const errors = stores.map((store) => store.error).filter(Boolean);
  const tmdbErrors = stores.map((store) => store.tmdbError).filter(Boolean);
  const enriching = stores.some((store) => store.enriching);

  const notices = [];
  if (loading) {
    notices.push(["status", "載入中…"]);
  } else if (errors.length) {
    notices.push(["status error", errors.join("；")]);
  } else {
    // 影城本身沒掛，但 TMDB 可能單獨出事；出事了照樣把拿得到的電影顯示出來
    if (tmdbErrors.length) notices.push(["status error", tmdbErrors.join("；")]);
    if (enriching) notices.push(["status", "查詢 TMDB 資料中…"]);
    if (!enriching && visible.length === 0) notices.push(["status", "目前沒有電影資料"]);
  }

  if (changed("notices", JSON.stringify(notices))) {
    const area = $("movie-area");
    for (const stale of area.querySelectorAll("p.status")) stale.remove();
    const list = $("movie-list");
    for (const [className, text] of notices) {
      area.insertBefore(el("p", { class: className, text }), list);
    }
  }

  reconcileMovieList(visible);
}

function reconcileMovieList(visible) {
  const list = $("movie-list");
  const wanted = visible.map(movieNode);

  // 標準的 keyed 比對：把需要的節點依序搬到定位，剩下的刪掉。
  // insertBefore 對已經在畫面上的節點是「搬移」而不是「重建」。
  let cursor = list.firstChild;
  for (const node of wanted) {
    if (cursor === node) {
      cursor = cursor.nextSibling;
      continue;
    }
    list.insertBefore(node, cursor);
  }
  while (cursor) {
    const next = cursor.nextSibling;
    list.removeChild(cursor);
    cursor = next;
  }
}

function movieNode(movie) {
  const id = movieId(movie);
  const signature = [
    movie.title,
    (movie.sources || []).join(","),
    inWatchlist(movie),
    Object.keys(state.genres).length,
  ].join("|");

  const cached = movieNodes.get(id);
  if (cached && cached.signature === signature) return cached.node;

  const node = buildMovieItem(movie);
  movieNodes.set(id, { signature, node });
  return node;
}

function buildMovieItem(movie) {
  const meta = movie.meta;
  const labels = (movie.sources || []).map((key) => {
    const cinema = CINEMAS.find((item) => item.key === key);
    return cinema ? cinema.label : key;
  });
  const added = inWatchlist(movie);

  const info = [];
  if (meta && meta.title && meta.title !== movie.title) {
    info.push(field("片名:", meta.title));
  }
  if (meta) {
    info.push(field("上映日期:", meta.release_date || "-"));
    info.push(field("評分:", meta.vote_average ? `★ ${meta.vote_average.toFixed(1)}` : "-"));
    if (meta.genre_ids && meta.genre_ids.length) info.push(field("類型:", genreNames(meta.genre_ids)));
    if (meta.original_language) info.push(field("語言:", meta.original_language));
  }

  return el("li", { class: "movie-item", onClick: () => selectMovie(movie) },
    el("div", { class: "movie-title" },
      movie.title,
      labels.length > 0 && el("span", { class: "movie-sources" },
        labels.map((label) => el("span", { class: "source-tag", text: label })))),
    meta && el("div", { class: "movie-meta" },
      meta.poster_path && el("img", {
        src: IMG_SMALL + meta.poster_path, alt: "", class: "movie-poster", loading: "lazy",
      }),
      el("div", { class: "movie-info" }, info)),
    el("div", { class: "movie-actions" },
      el("button", {
        type: "button",
        class: `watchlist-add-btn${added ? " added" : ""}`,
        disabled: added,
        text: added ? "已加入待看清單" : "加入待看清單",
        onClick: (event) => {
          event.stopPropagation();   // 不要順便把詳細資料視窗打開
          addToWatchlist(movie);
        },
      })));
}

function field(label, value) {
  return el("div", { class: "movie-field" },
    el("span", { class: "field-label", text: label }), " ", value);
}


/* ---------- 右欄：聊天 ---------- */
function renderChat(visible) {
  const disabled = visible.length === 0;
  const { messages, sending } = state.chat;

  $("chat-hint").style.display = disabled ? "" : "none";

  if (changed("chatMessages", `${messages.length}|${sending}`)) {
    setChildren($("chat-messages"),
      messages.length === 0 && el("div", { class: "chat-placeholder" },
        "輸入問題，我會根據目前顯示的電影資料回答，例如「推薦評分最高的電影」"),
      messages.map((message) => el("div", {
        class: `chat-msg chat-${message.role}`, text: message.content,
      })),
      sending && el("div", { class: "chat-msg chat-assistant chat-thinking", text: "思考中…" }));
    $("chat-messages").scrollTop = $("chat-messages").scrollHeight;
  }

  if (changed("chatQuick", `${disabled}|${sending}`)) {
    setChildren($("chat-quick"), ...QUICK_PROMPTS.map((prompt) => el("button", {
      type: "button", class: "quick-chip", text: prompt,
      disabled: sending || disabled,
      onClick: () => sendChat(prompt),
    })));
  }

  $("chat-input").disabled = sending;
  updateSendButton();
}

function updateSendButton() {
  $("chat-send").disabled = state.chat.sending || !$("chat-input").value.trim();
}


/* ---------- 詳細資料視窗 ---------- */
function renderModal() {
  const movie = state.selected;
  if (!changed("modal", movie ? String(movieId(movie)) : "")) return;

  const host = $("modal-host");
  setChildren(host);
  if (!movie) return;

  const meta = movie.meta;
  const rows = [
    ["片名 (title)", meta && meta.title],
    ["原始片名 (original_title)", meta && meta.original_title],
    ["是否成人片 (adult)", tick(meta && meta.adult)],
    ["是否為影片 (video)", tick(meta && meta.video)],
    ["類型 (genre_ids)", meta && meta.genre_ids && meta.genre_ids.length ? genreNames(meta.genre_ids) : "-"],
    ["原始語言 (original_language)", (meta && meta.original_language) || "-"],
    ["上映日期 (release_date)", (meta && meta.release_date) || "-"],
    ["評分 (vote_average)", meta && meta.vote_average != null ? `★ ${meta.vote_average.toFixed(1)}` : "-"],
    ["評分人數 (vote_count)", (meta && meta.vote_count) ?? "-"],
    ["熱門度 (popularity)", meta && meta.popularity != null ? meta.popularity.toFixed(2) : "-"],
  ];

  host.appendChild(el("div", { class: "modal-overlay", onClick: closeModal },
    el("div", { class: "modal-card", onClick: (event) => event.stopPropagation() },
      el("button", {
        type: "button", class: "modal-close", "aria-label": "關閉", text: "×", onClick: closeModal,
      }),

      el("div", { class: "modal-hero" },
        meta && meta.backdrop_path && el("img", {
          src: IMG_ORIGINAL + meta.backdrop_path, alt: "", class: "modal-backdrop",
        }),
        el("div", { class: "modal-hero-content" },
          meta && meta.poster_path
            ? el("img", { src: IMG_MEDIUM + meta.poster_path, alt: "", class: "modal-poster" })
            : el("div", { class: "modal-poster placeholder", text: "無海報" }),
          el("div", { class: "modal-hero-text" },
            el("h2", { class: "modal-title", text: movie.title }),
            meta && meta.title && meta.title !== movie.title
              && el("div", { class: "modal-subtitle" }, "TMDB 片名：", meta.title),
            el("div", { class: "modal-rating" },
              el("span", { class: "rating-star", text: "★" }), " ",
              meta && meta.vote_average != null ? meta.vote_average.toFixed(1) : "-",
              el("span", { class: "rating-count" },
                "(", String((meta && meta.vote_count) ?? 0), " 人評分)"))))),

      meta && meta.overview && el("div", { class: "modal-section" },
        el("h3", { class: "modal-section-title", text: "劇情簡介 (overview)" }),
        el("p", { class: "modal-overview", text: meta.overview })),

      el("div", { class: "modal-section" },
        el("h3", { class: "modal-section-title", text: "TMDB 資料" }),
        el("table", { class: "modal-fields" },
          el("tbody", {}, rows.map(([label, value]) => el("tr", {},
            el("td", { class: "modal-field-label", text: label }),
            el("td", { class: "modal-field-value", text: value == null ? "" : String(value) })))))),

      // 只有真的在那家影城上映才點得下去
      el("div", { class: "modal-footer" }, CINEMAS.map((cinema) => {
        const showing = (movie.sources || []).includes(cinema.key);
        return el("a", {
          href: showing ? cinema.url : null,
          target: "_blank", rel: "noopener noreferrer",
          class: `booking-btn${showing ? "" : " disabled"}`,
          "aria-disabled": String(!showing),
          onClick: (event) => { if (!showing) event.preventDefault(); },
        }, "前往", cinema.label, "訂票");
      })))));
}

function tick(value) {
  return value === true ? "是" : value === false ? "否" : "-";
}


/* --------------------------------------------------------------------------
 * 金鑰設定
 *
 * 教材附了一組共用金鑰，但共用金鑰的額度是大家一起分的 ——
 * 全班同時發問就會有人收到 429。這個視窗讓你換成自己申請的，
 * 存下去會寫進專案根目錄的 .env，伺服器立刻改用新的，不必重啟。
 *
 * 注意這裡從頭到尾沒有把金鑰讀回來過：/api/keys/ 只回「有沒有設定」。
 * 金鑰進得去、出不來，這是處理金鑰時該有的預設姿勢。
 * -------------------------------------------------------------------------- */
