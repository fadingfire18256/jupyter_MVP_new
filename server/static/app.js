// 由 notebooks/05_接成服務.ipynb 產生；請修改來源儲存格。
$("movie-search").addEventListener("input", (event) => {
  state.search = event.target.value;
  render();
});

$("chat-send").addEventListener("click", () => sendChat($("chat-input").value));

$("chat-input").addEventListener("input", updateSendButton);
$("chat-input").addEventListener("keydown", (event) => {
  // 中文輸入法選字時按的 Enter 是在組字，不是要送出（Firefox、Safari 會這樣回報）
  if (event.isComposing || event.keyCode === 229) return;
  if (event.key === "Enter") sendChat($("chat-input").value);
});

$("key-open").addEventListener("click", () => openKeyDialog());

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && state.selected) closeModal();
});

render();

// 先問後端金鑰齊不齊，缺的話按鈕會變成紅色的提醒
loadKeyStatus();

// 類型對照表和兩家影城同時開始抓，彼此不用等
loadGenres();
for (const cinema of CINEMAS) loadCinema(cinema);
