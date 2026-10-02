const gameId = document.body.dataset.gameId;
const adminToken = document.body.dataset.adminToken;
let state = null;
const error = document.querySelector("#control-error");
const quiz = createQuizSocket(gameId, render, (event) => { if (event.type === "error") error.textContent = event.message; }, { adminToken });
const playerUrl = `${location.origin}/player/${gameId}/`;
document.querySelector("#player-url").textContent = playerUrl;
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
document.querySelector("#next-button").onclick = () => quiz.send("start_next_question");
document.querySelector("#close-button").onclick = () => quiz.send("close_answers");
document.querySelector("#reveal-button").onclick = () => quiz.send("reveal_result");
document.querySelector("#open-buzzer-button").onclick = () => quiz.send("open_buzzer");
document.querySelector("#audio-button").onclick = () => quiz.send("play_audio");
document.querySelector("#correct-button").onclick = () => quiz.send("judge_buzzer", { correct:true });
document.querySelector("#wrong-button").onclick = () => quiz.send("judge_buzzer", { correct:false });
document.querySelector("#seconds-button").onclick = () => quiz.send("set_seconds", { seconds:document.querySelector("#seconds-input").value });
function render(nextState) {
  state = nextState; error.textContent = ""; const { game, question, players } = state;
  const phaseLabel = ({ lobby:"待機中", question:"2択・4択問題", answer_closed:"回答締切", buzzer_open:"早押し問題", buzzer_locked:"早押し問題", result:"結果発表", finished:"ゲーム終了" })[game.phase];
  document.querySelector("#control-phase").textContent = phaseLabel;
  document.querySelector("#sidebar-current-status").textContent = phaseLabel;
  document.querySelector("#control-number").textContent = question ? `問題 ${question.number} / ${question.total}` : "";
  document.querySelector("#control-question").textContent = question ? question.body : "まだ開始していません";
  document.querySelector("#control-choices").innerHTML = question?.type === "choice" ? question.choices.map((choice, index) => `<span>${index + 1}. ${escapeHtml(choice)}</span>`).join("") : "";
  document.querySelector("#control-answer").textContent = question?.correct_text ? `正解：${question.correct_text}` : "";
  document.querySelector("#seconds-input").value = game.seconds;
  const buzzed = players.find((p) => p.id === game.buzzed_player_id); document.querySelector("#buzz-player").textContent = buzzed ? `${buzzed.nickname} さんの口頭回答を判定してください` : "まだ誰も押していません";
  document.querySelector("#control-players").innerHTML = players.map((p) => `<div class="control-player"><span>${escapeHtml(p.nickname)} ${p.connected ? "●" : "○"}</span><strong>${p.score}pt</strong><button class="button button-red score-adjust" data-id="${p.id}" data-delta="10">+10</button><button class="button button-outline score-adjust" data-id="${p.id}" data-delta="-10">-10</button></div>`).join("") || "参加者を待っています";
  document.querySelectorAll(".score-adjust").forEach((button) => button.onclick = () => quiz.send("adjust_score", { player_id:button.dataset.id, delta:button.dataset.delta }));
  const answerLines = state.answers.map((answer) => `<li>${escapeHtml(answer.player__nickname)}：${answer.selected_choice}番 ${answer.is_correct ? "○ 正解" : "× 不正解"}</li>`);
  const buzzLines = state.buzzer_attempts.map((attempt) => `<li>${escapeHtml(attempt.player__nickname)}：${attempt.is_correct === null ? "判定待ち" : attempt.is_correct ? `○ +${attempt.score_delta}pt` : "× 不正解"}</li>`);
  document.querySelector("#answer-history").innerHTML = [...answerLines, ...buzzLines].length ? `<ul>${[...answerLines, ...buzzLines].join("")}</ul>` : "回答・早押しはまだありません";
  document.querySelector("#game-log").innerHTML = state.logs.length ? `<ul>${state.logs.map((log) => `<li><time>${log.created_at}</time> ${escapeHtml(log.message)}</li>`).join("")}</ul>` : "まだログはありません";
  renderPlayerPreview(game, question, players);
}

function renderPlayerPreview(game, question, players) {
  const select = document.querySelector("#preview-player");
  const previous = select.value;
  select.innerHTML = `<option value="">回答者を選択</option>${players.map((player) => `<option value="${player.id}">${escapeHtml(player.nickname)}（${player.connected ? "接続中" : "切断中"}）</option>`).join("")}`;
  const selected = players.some((player) => player.id === previous) ? previous : players[0]?.id || "";
  select.value = selected;
  const refresh = () => {
    const player = players.find((item) => item.id === select.value);
    const screen = document.querySelector("#preview-screen");
    if (!player) { screen.textContent = "参加者を選ぶと、その人に配信中の画面と回答状況を確認できます。"; return; }
    const phaseText = ({ lobby:"参加受付中", question:"答えを選ぶ画面", answer_closed:"回答締切", buzzer_open:"早押し画面", buzzer_locked:"司会が判定中", result:"結果発表", finished:"ゲーム終了" })[game.phase] || "待機中";
    const answer = state.answers.find((item) => String(item.player_id) === String(player.id));
    const answerStatus = answer ? `この問題の回答：${answer.selected_choice}番を送信済み` : player.answered ? "この問題に回答済み" : game.phase === "question" ? "この問題はまだ未回答" : "回答待ち・または該当なし";
    screen.innerHTML = `<div class="preview-top"><strong>${escapeHtml(player.nickname)} さん</strong><span class="${player.connected ? "online" : "offline"}">${player.connected ? "接続中" : "切断中"}</span></div><p class="preview-status">${phaseText}</p><h3>${question ? escapeHtml(question.body) : game.phase === "finished" ? "ゲーム終了！" : "司会の開始を待っています"}</h3>${question?.type === "choice" && game.phase === "question" ? `<div class="preview-choices">${question.choices.map((choice, index) => `<span class="${answer?.selected_choice === index + 1 ? "selected" : ""}">${index + 1}. ${escapeHtml(choice)}</span>`).join("")}</div>` : ""}<p class="preview-answer">${answerStatus}</p><strong class="preview-score">${player.score} pt</strong>`;
  };
  select.onchange = refresh;
  refresh();
}
