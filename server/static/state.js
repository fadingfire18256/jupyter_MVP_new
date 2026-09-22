// 由 notebooks/05_接成服務.ipynb 產生；請修改來源儲存格。
/* --------------------------------------------------------------------------
 * 前端。這組檔案負責畫面互動，資料查詢與聊天提示由後端處理：
 * 抓片單、查 TMDB、挑最佳比對結果全都在 movieapp/ 裡，
 * 這裡只負責「跟 /api/ 要資料、畫出來、把問題轉給 /api/chat/」。
 *
 * 篩選、排序、去重放在瀏覽器做，因為那要即時反應 ——
 * 每按一次按鈕就往伺服器跑一趟太慢，而且那些資料早就在手上了。
 * -------------------------------------------------------------------------- */


/** 首頁由 Django 設定 CSRF cookie；POST 必須帶回同一個 token。 */
function jsonHeaders() {
  const pair = document.cookie.split("; ").find((item) => item.startsWith("csrftoken="));
  return { "Content-Type": "application/json", "X-CSRFToken": pair ? decodeURIComponent(pair.slice(10)) : "" };
}

const API = "/api";
const IMG_SMALL = "https://image.tmdb.org/t/p/w92";
const IMG_MEDIUM = "https://image.tmdb.org/t/p/w300";
const IMG_ORIGINAL = "https://image.tmdb.org/t/p/original";

// 兩家影城：key 同時是 /api/<key>/ 的路徑、來源代號、訂票連結的識別
const CINEMAS = [
  { key: "showtimes", label: "秀泰影城", url: "https://www.showtimes.com.tw/" },
  { key: "miramar", label: "美麗華影城", url: "https://www.miramarcinemas.tw/" },
];

// 篩選列上的五顆按鈕
const FILTER_BUTTONS = [
  { key: "adult", label: "是否成人片", type: "bool" },
  { key: "genre_ids", label: "類型", type: "genre" },
  { key: "popularity", label: "熱門度", type: "slider" },
  { key: "releaseDate", label: "上映日期", type: "slider" },
  { key: "voteAverage", label: "評分", type: "slider" },
];

const SORT_KEYS = ["popularity", "releaseDate", "voteAverage"];

const QUICK_PROMPTS = [
  "推薦一部高分電影",
  "推薦黑暗風格的電影",
  "推薦喜劇片",
  "哪部電影評分最高？",
  "推薦今天上映的電影",
  "推薦動作片",
];

// 同時發出幾個 TMDB 查詢。
//
// 一部一部排隊查，六十幾部片乘上每次約半秒的來回，要等三十秒以上；
// 全部一次射出去又會撞到 TMDB 的速率限制（429）。
// 開一個固定大小的池子，兩家合計維持最多八個請求在路上，是這兩者之間的折衷。
const TMDB_CONCURRENCY = 4; // 每家 4 個，兩家同時載入時最多 8 個


/* --------------------------------------------------------------------------
 * 狀態
 * -------------------------------------------------------------------------- */
const state = {
  // 每家影城各自一份：片名、補完 TMDB 的電影、載入中、錯誤
  dataMode: null,
  cinemas: {},
  genres: {},
  genreError: "",
  filters: {
    adult: "off",
    genreId: null,
    popularity: { mode: "off", threshold: null },
    releaseDate: { mode: "off", threshold: null },
    voteAverage: { mode: "off", threshold: null },
  },
  genrePanelOpen: false,
  search: "",
  watchlist: loadWatchlist(),
  recent: [],
  selected: null,
  chat: { messages: [], sending: false, sessionId: newSessionId() },
  // null = 還沒問過後端，true/false = 已知
  keyStatus: { tmdb: null, gemini: null },
  keyMissing: { tmdb: false, gemini: false },
  // 每重新載入一次就加一。還在跑的舊載入比對到編號不同，就知道自己作廢了
  loadGeneration: 0,
};

for (const cinema of CINEMAS) {
  state.cinemas[cinema.key] = {
    titles: [], movies: [], loading: true, error: "", enriching: false, tmdbError: "",
  };
}

function loadWatchlist() {
  try {
    return JSON.parse(localStorage.getItem("watchlist") || "[]") || [];
  } catch {
    return [];
  }
}

function saveWatchlist() {
  try {
    localStorage.setItem("watchlist", JSON.stringify(state.watchlist));
  } catch {
    /* 無痕視窗或關掉儲存空間時會丟例外，不影響其他功能 */
  }
}

function newSessionId() {
  return (typeof crypto !== "undefined" && crypto.randomUUID)
    ? crypto.randomUUID()
    : String(Math.random()).slice(2);
}


/* --------------------------------------------------------------------------
 * 小工具
 * -------------------------------------------------------------------------- */
const $ = (id) => document.getElementById(id);

/** 建立元素。attrs 裡的 class/text 是捷徑，on* 會掛成事件。 */
function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  let text = null;
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") text = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2).toLowerCase(), value);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  setChildren(node, text, ...children);
  return node;
}

/** 把 children 換掉。跟 el() 一樣會攤平陣列、略過 null/false，
 *  所以 `條件 && el(...)` 這種寫法在這裡也安全。
 *  （原生的 replaceChildren 不會過濾，會把 false 直接印成 "false"。） */
function setChildren(node, ...children) {
  node.replaceChildren();
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false || child === "") continue;
    node.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

/** 一部電影的唯一身分：有 TMDB id 就用 id，沒有就退回片名。
 *  和後端 merge.movie_key() 是同一個想法。 */
function movieId(movie) {
  const id = movie.meta && movie.meta.id;
  return id != null ? id : movie.title;
}

function sameMovie(a, b) {
  return movieId(a) === movieId(b);
}

function inWatchlist(movie) {
  return state.watchlist.some((item) => sameMovie(item, movie));
}

/** "2026-08-07" -> 可以直接比大小的月份序號。和後端 merge._release_month() 一致。 */
function releaseMonth(value) {
  if (!value) return null;
  const match = /^(\d{4})-(\d{1,2})/.exec(String(value).trim());
  return match ? Number(match[1]) * 12 + Number(match[2]) : null;
}

/** 月份序號 -> "2026年8月" */
function monthLabel(value) {
  if (value == null) return "";
  return `${Math.floor((value - 1) / 12)}年${((value - 1) % 12) + 1}月`;
}

function modeLabel(mode) {
  return mode === "desc" ? "高→低" : "低→高";
}

function genreNames(ids) {
  return (ids || []).map((id) => state.genres[id] || id).join("、");
}


/* --------------------------------------------------------------------------
 * 抓資料
 *
 * 流程和第 01~02 章一模一樣，只是換到瀏覽器這一側跑：
 *     /api/<影城>/          -> 一串片名
 *     /api/tmdb/search/     -> 每個片名補上 TMDB 資料
 *
 * 為什麼不做成一支「一次回傳全部」的 API？因為那樣畫面會整整空白十幾秒。
 * 分開之後，片單一到就先畫出來，TMDB 的海報和評分再一批一批補上去。
 * -------------------------------------------------------------------------- */
