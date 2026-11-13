const gameId = document.body.dataset.gameId;
const adminToken = document.body.dataset.adminToken;
let state = null;
const error = document.querySelector("#control-error");
const quiz = createQuizSocket(gameId, render, (event) => { if (event.type === "error") { error.textContent = event.message; pendingModeRedirect = false; } }, { adminToken });
const playerUrl = document.body.dataset.playerUrl;
document.querySelector("#player-link").href = playerUrl;
document.querySelector("#copy-player-url").onclick = async () => {
  const button = document.querySelector("#copy-player-url");
  try {
    await navigator.clipboard.writeText(playerUrl);
    button.textContent = "コピーしました";
  } catch (_) {
    window.prompt("このURLをコピーしてください", playerUrl);
  }
  window.setTimeout(() => { button.textContent = "URLをコピー"; }, 1800);
};
document.querySelector("#progress-button").onclick = () => quiz.send("advance_game");
document.querySelector("#close-button").onclick = () => quiz.send("close_answers");
document.querySelector("#audio-button").onclick = () => quiz.send("play_audio");
document.querySelector("#video-button").onclick = () => quiz.send("play_video");
document.querySelector("#end-game-button").onclick = () => quiz.send("finish_game");
document.querySelector("#reset-game-button").onclick = () => quiz.send("reset_game");
let pendingModeRedirect = false;
document.querySelector("#reset-mode-button").onclick = () => {
  pendingModeRedirect = true;
  quiz.send("reset_game");
};
document.querySelector("#correct-button").onclick = () => quiz.send("judge_buzzer", { correct:true });
document.querySelector("#wrong-button").onclick = () => quiz.send("judge_buzzer", { correct:false });
document.querySelector("#minutes-button").onclick = () => quiz.send("set_game_minutes", { minutes:document.querySelector("#minutes-input").value });
function render(nextState) {
  state = nextState; error.textContent = ""; const { game, question, players } = state;
  const phaseLabel = ({ lobby:"待機中", intro:"次の問題を紹介中", question:"全員回答中", answer_closed:"回答締切", buzzer_open:"早押し問題", buzzer_locked:"司会判定中", result:"正解発表", finished:"ゲーム終了" })[game.phase];
  document.querySelector("#control-phase").textContent = phaseLabel;
  document.querySelector("#sidebar-current-status").textContent = game.deadline && question && Date.now() >= new Date(game.deadline).getTime() ? "時間終了・この問題が最終問題" : phaseLabel;
  document.querySelector("#control-number").textContent = question ? `問題 ${question.number}` : "";
  document.querySelector("#control-question").textContent = question ? question.body : "まだ開始していません";
  document.querySelector("#control-choices").innerHTML = question?.type === "choice" ? question.choices.map((choice, index) => `<span>${index + 1}. ${escapeHtml(choice)}</span>`).join("") : "";
  document.querySelector("#control-answer").textContent = question?.correct_text ? `正解：${question.correct_text}` : "";
  const minutesInput = document.querySelector("#minutes-input");
  // Keep the host's in-progress edit while websocket updates refresh the rest of the screen.
  if (document.activeElement !== minutesInput) minutesInput.value = game.minutes;
  const isFinished = game.phase === "finished";
  const isChoiceQuestion = ["choice", "image"].includes(question?.type);
  const isAudioQuestion = question?.type === "audio";
  const isVideoQuestion = question?.type === "video";
  const isAutoAdvancing = Boolean(game.result_advance_at);
  const progress = document.querySelector("#progress-button");
  progress.textContent = ({ lobby:"ゲームを開始する", intro:"今すぐ問題を出す", question:"答え合わせへ進む", answer_closed:"答え合わせへ進む", buzzer_open:"答え合わせへ進む", result:"次の問題へ" })[game.phase] || "次へ";
  setActionState(progress, !isFinished && !isAutoAdvancing && ["lobby", "intro", "question", "answer_closed", "buzzer_open", "result"].includes(game.phase));
  setActionState(document.querySelector("#close-button"), game.phase === "question" && isChoiceQuestion);
  setActionState(document.querySelector("#audio-button"), isAudioQuestion && ["buzzer_open", "buzzer_locked"].includes(game.phase));
  setActionState(document.querySelector("#video-button"), isVideoQuestion && ["buzzer_open", "buzzer_locked"].includes(game.phase));
  setActionState(document.querySelector("#end-game-button"), !isFinished);
  setActionState(document.querySelector("#reset-game-button"), isFinished);
  setActionState(document.querySelector("#reset-mode-button"), isFinished && !pendingModeRedirect);
  if (pendingModeRedirect && game.phase === "lobby") {
    pendingModeRedirect = false;
    window.location.href = document.querySelector("#edit-mode-link").href;
    return;
  }
  document.querySelector("#game-finished-note").classList.toggle("hidden", !isFinished);
  document.querySelector("#buzzer-judge-card").classList.toggle("hidden", game.phase !== "buzzer_locked" || !game.buzzed_player_id);
  document.querySelector("#host-settings").classList.toggle("hidden", game.phase !== "lobby");
  document.querySelector("#edit-mode-link").classList.toggle("hidden", game.phase !== "lobby");
  const buzzed = players.find((p) => p.id === game.buzzed_player_id); document.querySelector("#buzz-player").textContent = buzzed ? `${buzzed.nickname} さんの口頭回答を判定してください` : "まだ誰も押していません";
  document.querySelector("#control-players").innerHTML = players.map((p) => `<div class="control-player"><span>${escapeHtml(p.nickname)} ${p.connected ? "●" : "○"}</span><strong>${p.score}pt</strong><button class="button button-red score-adjust" data-id="${p.id}" data-delta="10" ${isFinished ? "disabled" : ""}>+10</button><button class="button button-outline score-adjust" data-id="${p.id}" data-delta="-10" ${isFinished ? "disabled" : ""}>-10</button></div>`).join("") || "参加者を待っています";
  document.querySelectorAll(".score-adjust").forEach((button) => button.onclick = () => quiz.send("adjust_score", { player_id:button.dataset.id, delta:button.dataset.delta }));
  const answerLines = state.answers.map((answer) => `<li>${escapeHtml(answer.player__nickname)}：${answer.selected_choice}番 ${answer.is_correct ? "○ 正解" : "× 不正解"}</li>`);
  const buzzLines = state.buzzer_attempts.map((attempt) => `<li>${escapeHtml(attempt.player__nickname)}：${attempt.is_correct === null ? "判定待ち" : attempt.is_correct ? `○ +${attempt.score_delta}pt` : "× 不正解"}</li>`);
  document.querySelector("#answer-history").innerHTML = [...answerLines, ...buzzLines].length ? `<ul>${[...answerLines, ...buzzLines].join("")}</ul>` : "回答・早押しはまだありません";
}
function setActionState(button, isAvailable) {
  button.disabled = !isAvailable;
  button.classList.toggle("hidden", !isAvailable);
}
setInterval(() => quiz.send("tick"), 1000);
