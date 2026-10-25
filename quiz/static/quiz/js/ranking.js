const gameId = document.body.dataset.gameId;
const fullscreenToggle = document.querySelector("#ranking-fullscreen-toggle");

function isFullscreen() {
  return Boolean(document.fullscreenElement || document.webkitFullscreenElement);
}

function updateFullscreenToggle() {
  const active = isFullscreen();
  fullscreenToggle.textContent = active ? "全画面を終了" : "全画面表示";
  fullscreenToggle.setAttribute("aria-pressed", String(active));
}

async function toggleFullscreen() {
  try {
    if (isFullscreen()) {
      if (document.exitFullscreen) await document.exitFullscreen();
      else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
    } else if (document.documentElement.requestFullscreen) {
      await document.documentElement.requestFullscreen();
    } else if (document.documentElement.webkitRequestFullscreen) {
      document.documentElement.webkitRequestFullscreen();
    }
  } catch (_) {
    // Browsers require this action to originate from the button click.
  }
  updateFullscreenToggle();
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function rankedPlayers(players) {
  let previousScore = null;
  let previousRank = 0;
  return players.map((player, index) => {
    const rank = player.score === previousScore ? previousRank : index + 1;
    previousScore = player.score;
    previousRank = rank;
    return { ...player, rank };
  });
}

function render(state) {
  const ranked = rankedPlayers(state.all_time_rankings.map((entry) => ({
    nickname: entry.player_name,
    score: entry.score,
  })));
  document.querySelector("#ranking-title").textContent = "全体ランキング TOP 5";
  document.querySelector("#ranking-status").textContent = "リアルタイム更新";
  document.querySelector("#ranking-note").textContent = ranked.length ? "全ゲームの記録を得点順に表示しています" : "まだランキング記録がありません";
  document.querySelector("#live-ranking-list").innerHTML = ranked.map((player) => `
    <li>
      <span>${player.rank}位　${escapeHtml(player.nickname)}</span>
      <strong>${player.score} pt</strong>
    </li>`).join("");
}

fullscreenToggle.addEventListener("click", toggleFullscreen);
document.addEventListener("fullscreenchange", updateFullscreenToggle);
document.addEventListener("webkitfullscreenchange", updateFullscreenToggle);
updateFullscreenToggle();
createQuizSocket(gameId, render);
