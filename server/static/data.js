// 由 notebooks/05_接成服務.ipynb 產生；請修改來源儲存格。
async function loadCinema(cinema) {
  const generation = state.loadGeneration;   // 記住這是第幾輪載入
  const store = state.cinemas[cinema.key];

  // 第一步：片名
  try {
    const response = await fetch(`${API}/${cinema.key}/`);
    const data = await response.json();
    if (generation !== state.loadGeneration) return;
    if (response.ok) store.titles = data.movies || [];
    else store.error = data.error || "載入失敗";
  } catch {
    if (generation !== state.loadGeneration) return;
    store.error = "無法連線到後端伺服器";
  }
  store.loading = false;
  render();

  if (store.error || store.titles.length === 0) return;

  // 第二步：逐部補 TMDB 資料
  if (generation !== state.loadGeneration) return;   // 中途換過金鑰，這一輪作廢
  await enrichTitles(cinema, store, generation);
}

async function enrichTitles(cinema, store, generation = state.loadGeneration) {
  if (generation !== state.loadGeneration) return;
  const titles = store.titles;

  // 結果先寫進固定位置再過濾，這樣不管誰先回來，
  // 畫面上的順序永遠跟影城給的片單順序一致。
  const slots = new Array(titles.length).fill(null);
  let cursor = 0;

  store.enriching = true;
  render();

  async function worker() {
    while (cursor < titles.length) {
      // 金鑰沒設定、或使用者中途換了金鑰（reloadEverything 已另起新的一輪），都不必再查
      if (state.keyMissing.tmdb || generation !== state.loadGeneration) return;
      const index = cursor++;
      const title = titles[index];
      try {
        const url = `${API}/tmdb/search/?query=${encodeURIComponent(title)}&language=zh-TW`;
        const response = await fetch(url);
        const data = await response.json();
        // 等待回應期間可能已重新載入，401 也不能污染新一輪的金鑰狀態。
        if (generation !== state.loadGeneration) return;
        if (response.ok) {
          // 只取第一筆 —— 後端已經把最像的那部排到最前面了（第 02 章的陷阱）
          const meta = (data.results || [])[0] || null;
          if (meta) slots[index] = { title, meta, source: cinema.key };
        } else if (noteMissingKey(data)) {
          // 金鑰沒設定的話，剩下六十幾次查詢也只會拿到同一個 401
          store.tmdbError = "尚未設定 TMDB 金鑰";
          return;
        } else if (!store.tmdbError) {
          store.tmdbError = data.error || "TMDB 查詢失敗";
        }
      } catch {
        if (generation !== state.loadGeneration) return;
        if (!store.tmdbError) store.tmdbError = "無法連線到 TMDB";
      }
      store.movies = slots.filter(Boolean);
      scheduleRender();
    }
  }

  const size = Math.min(TMDB_CONCURRENCY, titles.length);
  await Promise.all(Array.from({ length: size }, worker));

  if (generation !== state.loadGeneration) return;
  store.enriching = false;
  render();
}

async function loadGenres() {
  const generation = state.loadGeneration;
  try {
    const response = await fetch(`${API}/tmdb/genres/?language=zh-TW`);
    const data = await response.json();
    if (generation !== state.loadGeneration) return;   // 舊的一輪，結果不要寫進新狀態
    if (!response.ok) {
      noteMissingKey(data);
      state.genreError = data.error || "類型載入失敗";
    } else {
      const names = {};
      for (const genre of data.genres || []) names[genre.id] = genre.name;
      state.genres = names;
    }
  } catch {
    if (generation !== state.loadGeneration) return;
    state.genreError = "無法載入類型";
  }
  render();
}


/* --------------------------------------------------------------------------
 * 整合、篩選、排序
 *
 * 這一段是第 03 章 merge.py 的瀏覽器版本，規則完全一樣：
 * 用 TMDB id 當共同身分證跨影城去重，查不到 id 的才退回用片名。
 * -------------------------------------------------------------------------- */
function mergedMovies() {
  const merged = new Map();
  for (const cinema of CINEMAS) {
    for (const movie of state.cinemas[cinema.key].movies) {
      const id = movie.meta && movie.meta.id;
      const key = id != null ? `tmdb:${id}` : `title:${movie.title}`;
      const existing = merged.get(key);
      if (existing) {
        if (!existing.sources.includes(movie.source)) existing.sources.push(movie.source);
        existing.titles[movie.source] = movie.title;
      } else {
        merged.set(key, { ...movie, sources: [movie.source], titles: { [movie.source]: movie.title } });
      }
    }
  }
  return Array.from(merged.values());
}

/** 滑桿的刻度要跟著實際資料走，不能寫死。 */
function bounds(movies) {
  const populars = movies.map((m) => (m.meta && m.meta.popularity) || 0);
  const years = movies
    .map((m) => Number.parseInt(m.meta && m.meta.release_date, 10))
    .filter(Boolean);
  return {
    popularityMax: Math.max(10, ...populars),
    yearMin: years.length ? Math.min(...years) : 1990,
    yearMax: Math.max(new Date().getFullYear(), ...years),
  };
}

function applyFilters(movies, filters) {
  const kept = movies.filter((movie) => {
    const meta = movie.meta;
    if (filters.adult === "true" && !(meta && meta.adult)) return false;
    if (filters.adult === "false" && meta && meta.adult) return false;
    if (filters.genreId && !((meta && meta.genre_ids) || []).includes(filters.genreId)) return false;
    if (filters.popularity.threshold != null
        && ((meta && meta.popularity) ?? 0) < filters.popularity.threshold) return false;
    if (filters.voteAverage.threshold != null
        && ((meta && meta.vote_average) ?? 0) < filters.voteAverage.threshold) return false;
    if (filters.releaseDate.threshold != null) {
      const month = releaseMonth(meta && meta.release_date);
      if (month == null || month < filters.releaseDate.threshold) return false;
    }
    return true;
  });

  // 三個排序鍵一次只會有一個生效
  const active = SORT_KEYS.find((key) => filters[key].mode !== "off");
  if (!active) return kept;

  const field = active === "releaseDate" ? "release_date"
    : active === "voteAverage" ? "vote_average" : "popularity";
  const direction = filters[active].mode === "asc" ? 1 : -1;

  return [...kept].sort((a, b) => {
    const left = a.meta && a.meta[field];
    const right = b.meta && b.meta[field];
    // 沒有值的一律沉到最後，不管是升冪還是降冪
    const invalid = (value) => value == null || value === "" || (field === "release_date" && !Number.isFinite(Date.parse(value)));
    if (invalid(left) && invalid(right)) return 0;
    if (invalid(left)) return 1;
    if (invalid(right)) return -1;
    return typeof left === "number"
      ? (left - right) * direction
      : (Date.parse(left) - Date.parse(right)) * direction;
  });
}

function searchMovies(movies, keyword) {
  const query = keyword.trim().toLowerCase();
  if (!query) return movies;
  return movies.filter((movie) =>
    movie.title.toLowerCase().includes(query)
    || ((movie.meta && movie.meta.title) || "").toLowerCase().includes(query));
}

/** 目前畫面上實際看得到的電影 —— 聊天的 prompt 也是拿這一份。 */
function visibleMovies() {
  return searchMovies(applyFilters(mergedMovies(), state.filters), state.search);
}

// 聊天提示由後端 gemini.build_system_prompt() 統一建立。
