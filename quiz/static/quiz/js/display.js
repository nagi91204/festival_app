const gameId = document.body.dataset.gameId;
let state = null;
const audio = document.querySelector("#display-audio");
const quiz = createQuizSocket(gameId, render, (event) => { if (event.type === "play_audio" && state?.question?.audio_url) { audio.src = state.question.audio_url; audio.currentTime = 0; audio.play().catch(() => {}); } });
function rankingHtml(players) { return players.slice(0, 3).map((p, index) => `<li>${index + 1}位　${escapeHtml(p.nickname || p.player_name)} <strong>${p.score} pt</strong></li>`).join("") || "<li>参加者を待っています</li>"; }
function render(nextState) {
  state = nextState; const { game, question, players, rankings } = state;
  document.querySelector("#display-header-title").textContent = game.phase === "lobby" ? "文化祭クイズアプリ" : question?.type === "audio" ? "音当て問題" : ["buzzer_open", "buzzer_locked"].includes(game.phase) ? "早押し問題" : "2択・4択問題";
  document.querySelector("#display-header-status").textContent = game.phase === "lobby" ? "ゲーム開始まで" : game.phase === "finished" ? "FINAL RESULT" : "残り時間";
  document.querySelector("#display-lobby").classList.toggle("hidden", game.phase !== "lobby");
  document.querySelector("#display-game").classList.toggle("hidden", ["lobby", "finished"].includes(game.phase));
  document.querySelector("#display-finish").classList.toggle("hidden", game.phase !== "finished");
  document.querySelector("#lobby-ranking").innerHTML = rankingHtml(players);
  document.querySelector("#scoreboard").innerHTML = players.map((p) => `<span class="score-chip">${escapeHtml(p.nickname)} ${p.score}pt</span>`).join("");
  if (game.phase === "finished") {
    document.querySelector("#final-ranking").innerHTML = (rankings.length ? rankings : players.map((p, i) => ({ ...p, rank:i + 1 }))).map((p) => `<li>${p.rank}位　${escapeHtml(p.player_name || p.nickname)} <strong>${p.score} pt</strong></li>`).join("");
    document.querySelector("#new-record").classList.toggle("hidden", !state.is_new_record); return;
  }
  if (!question) return;
  document.querySelector("#question-meta").textContent = `QUESTION ${question.number} / ${question.total}　${question.category || ""}`;
  document.querySelector("#display-question").textContent = question.body;
  const image = document.querySelector("#question-image"); image.src = question.image_url || ""; image.classList.toggle("hidden", !question.image_url);
  document.querySelector("#display-choices").innerHTML = question.type === "choice" ? question.choices.map((text, i) => `<div class="display-choice">${i + 1}. ${escapeHtml(text)}</div>`).join("") : "";
  const buzzed = players.find((p) => p.id === game.buzzed_player_id); document.querySelector("#buzzed-name").textContent = buzzed ? `${buzzed.nickname} さんが早押し！` : "";
  const result = document.querySelector("#display-result"); result.classList.toggle("hidden", game.phase !== "result");
  document.querySelector("#correct-answer").textContent = game.phase === "result" ? `正解：${question.correct_text || ""}` : "";
  document.querySelector("#explanation").textContent = question.explanation || "";
}
setInterval(() => { const deadline = state?.game.deadline; document.querySelector("#timer").textContent = deadline && ["question", "buzzer_open", "buzzer_locked"].includes(state.game.phase) ? `${Math.max(0, Math.ceil((new Date(deadline) - Date.now()) / 1000))}` : "--"; }, 200);
setInterval(() => {
  const deadline = state?.game.deadline;
  if (deadline && ["question", "buzzer_open", "buzzer_locked"].includes(state.game.phase) && new Date(deadline) <= new Date()) quiz.send("expire_question");
}, 500);
