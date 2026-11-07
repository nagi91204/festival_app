const gameId = document.body.dataset.gameId;
let state = null;
let previousScores = new Map();
const audio = document.querySelector("#display-audio");
const video = document.querySelector("#display-video");
const fullscreenToggle = document.querySelector("#display-fullscreen-toggle");

function isFullscreen() {
  return Boolean(document.fullscreenElement || document.webkitFullscreenElement);
}

function updateFullscreenToggle() {
  const active = isFullscreen();
  fullscreenToggle.textContent = active ? "全画面を終了" : "全画面表示";
  fullscreenToggle.setAttribute("aria-pressed", String(active));
}

async function enterFullscreen() {
  const target = document.documentElement;
  try {
    if (target.requestFullscreen) await target.requestFullscreen();
    else if (target.webkitRequestFullscreen) target.webkitRequestFullscreen();
  } catch (_) {
    // Browsers only allow this from a user gesture; the toggle remains available.
  }
  updateFullscreenToggle();
}

async function toggleFullscreen() {
  try {
    if (isFullscreen()) {
      if (document.exitFullscreen) await document.exitFullscreen();
      else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
    } else {
      await enterFullscreen();
    }
  } finally {
    updateFullscreenToggle();
  }
}

fullscreenToggle.addEventListener("click", toggleFullscreen);
document.addEventListener("fullscreenchange", updateFullscreenToggle);
document.addEventListener("webkitfullscreenchange", updateFullscreenToggle);
updateFullscreenToggle();
const quiz = createQuizSocket(gameId, render, (event) => {
  if (event.type === "play_audio" && state?.question?.audio_url) { audio.src = state.question.audio_url; audio.currentTime = 0; audio.play().catch(() => {}); }
  if (event.type === "play_video" && state?.question?.video_url) { video.src = state.question.video_url; video.currentTime = 0; video.play().catch(() => {}); }
});
function rankingHtml(players) { return players.slice(0, 3).map((p, index) => `<li>${index + 1}位　${escapeHtml(p.nickname || p.player_name)} <strong>${p.score} pt</strong></li>`).join("") || "<li>参加者を待っています</li>"; }
function historicalRankingHtml(entries) { return entries.map((entry, index) => `<li><span>${index + 1}位　${escapeHtml(entry.player_name)}</span><strong>${entry.score} pt</strong></li>`).join("") || "<li>最初の記録を作ろう！</li>"; }
function render(nextState) {
  state = nextState; const { game, question, players, rankings, past_rankings: pastRankings = [] } = state;
  document.querySelector("#display-header-title").textContent = game.phase === "lobby" ? "文化祭クイズアプリ" : game.phase === "intro" ? "NEXT QUESTION" : question?.type === "audio" ? "音当て問題" : question?.type === "video" ? "動画当て問題" : ["buzzer_open", "buzzer_locked"].includes(game.phase) ? "早押し問題" : "2択・4択問題";
  const isFinalOvertime = game.phase !== "finished" && question && game.deadline && Date.now() >= new Date(game.deadline).getTime();
  document.querySelector("#display-header-status").textContent = game.phase === "lobby" ? "ゲーム開始まで" : game.phase === "finished" ? "FINAL RESULT" : isFinalOvertime ? "この問題が最終問題です" : "ゲーム終了まで";
  document.querySelector("#display-lobby").classList.toggle("hidden", game.phase !== "lobby");
  document.querySelector("#display-game").classList.toggle("hidden", ["lobby", "finished"].includes(game.phase));
  document.querySelector("#display-finish").classList.toggle("hidden", game.phase !== "finished");
  document.querySelector("#lobby-ranking").innerHTML = historicalRankingHtml(pastRankings);
  document.querySelector("#ranking-challenge").textContent = pastRankings.length ? `歴代最高 ${pastRankings[0].score} pt を超えよう！` : "次の記録を作るのは、あなたたちだ！";
  document.querySelector("#scoreboard").innerHTML = players.map((p) => {
    const previous = previousScores.get(p.id); const gain = previous !== undefined && p.score > previous ? `<em class="score-gain">+${p.score - previous} pt!</em>` : "";
    return `<span class="score-chip">${escapeHtml(p.nickname)} ${p.score}pt${gain}</span>`;
  }).join("");
  previousScores = new Map(players.map((p) => [p.id, p.score]));
  if (game.phase === "finished") {
    document.querySelector("#final-ranking").innerHTML = (rankings.length ? rankings : players.map((p, i) => ({ ...p, rank:i + 1 }))).map((p) => `<li>${p.rank}位　${escapeHtml(p.player_name || p.nickname)} <strong>${p.score} pt</strong></li>`).join("");
    document.querySelector("#new-record").classList.toggle("hidden", !state.is_new_record); return;
  }
  if (!question) return;
  document.querySelector("#question-meta").textContent = `QUESTION ${question.number} / ${question.total}　${question.category || ""}`;
  const typeName = ({ choice:"2択・4択問題", buzzer:"早押し問題", audio:"音当て問題", video:"動画当て問題", image:"画像予想問題" })[question.type] || "クイズ";
  document.querySelector("#display-question").textContent = game.phase === "intro" ? `次は「${typeName}」！` : question.body;
  const videoUrl = game.phase === "intro" ? "" : question.video_url || "";
  if (video.getAttribute("src") !== videoUrl) video.src = videoUrl;
  video.classList.toggle("hidden", !videoUrl);
  const image = document.querySelector("#question-image"); image.src = question.image_url || ""; image.classList.toggle("hidden", !question.image_url || game.phase === "intro" || Boolean(videoUrl));
  document.querySelector("#display-choices").innerHTML = question.type === "choice" && game.phase !== "intro" ? question.choices.map((text, i) => `<div class="display-choice ${game.phase === "result" && question.correct_choice === i + 1 ? "display-choice-correct" : ""}">${i + 1}. ${escapeHtml(text)}</div>`).join("") : "";
  const buzzed = players.find((p) => p.id === game.buzzed_player_id); document.querySelector("#buzzed-name").textContent = buzzed ? `${buzzed.nickname} さんが早押し！` : game.phase === "intro" ? "まもなく問題スタート！" : "";
  const result = document.querySelector("#display-result"); result.classList.toggle("hidden", game.phase !== "result");
  document.querySelector("#correct-answer").textContent = game.phase === "result" ? `正解：${question.correct_text || ""}` : "";
  document.querySelector("#explanation").textContent = question.explanation || "";
}
function formatTimer(seconds) { return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`; }
setInterval(() => { const deadline = state?.game.deadline; document.querySelector("#timer").textContent = deadline && state.game.status === "running" ? formatTimer(Math.max(0, Math.ceil((new Date(deadline) - Date.now()) / 1000))) : "--"; }, 200);
setInterval(() => quiz.send("tick"), 1000);
