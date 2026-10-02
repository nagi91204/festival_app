const gameId = document.body.dataset.gameId;
const storageKey = `festival-quiz-player-${gameId}`;
let state = null;
let me = JSON.parse(localStorage.getItem(storageKey) || "null");
let rejoinSent = false;
const joinPanel = document.querySelector("#join-panel");
const playerPanel = document.querySelector("#player-panel");
const playerFooter = document.querySelector("#player-footer");
const joinError = document.querySelector("#join-error");
const status = document.querySelector("#player-status");
const question = document.querySelector("#player-question");
const choices = document.querySelector("#choices");
const buzzButton = document.querySelector("#buzz-button");
const audioButton = document.querySelector("#audio-play-button");
const audio = new Audio();
const quiz = createQuizSocket(gameId, render, handleEvent);

function handleEvent(event) {
  if (event.type === "joined") {
    me = { id: event.player_id, nickname: event.nickname }; rejoinSent = true;
    localStorage.setItem(storageKey, JSON.stringify(me));
    joinPanel.classList.add("hidden"); playerPanel.classList.remove("hidden"); playerFooter.classList.remove("hidden");
  }
  if (event.type === "play_audio") playAudio();
  if (event.type === "error") joinError.textContent = event.message;
}
document.querySelector("#join-form").addEventListener("submit", (event) => {
  event.preventDefault(); joinError.textContent = "";
  quiz.send("join_player", { nickname: document.querySelector("#nickname").value });
});
function render(nextState) {
  state = nextState;
  if (me && !rejoinSent) {
    rejoinSent = true; joinPanel.classList.add("hidden"); playerPanel.classList.remove("hidden"); playerFooter.classList.remove("hidden");
    quiz.send("join_player", { nickname: me.nickname, player_id: me.id });
  }
  const player = state.players.find((item) => item.id === me?.id);
  document.querySelector("#player-name").textContent = player?.nickname || me?.nickname || "ゲスト";
  document.querySelector("#player-score").textContent = `${player?.score ?? 0} pt`;
  const phase = state.game.phase; const q = state.question;
  document.querySelector("#player-header-status").textContent = phase === "lobby" ? "参加受付" : phase === "finished" ? "ゲーム終了" : "ゲーム進行中";
  document.querySelector("#player-number").textContent = q ? `問題 ${q.number} / ${q.total}` : "";
  question.textContent = q?.body || (phase === "finished" ? "ゲーム終了！" : "司会の開始を待っています");
  status.textContent = ({ lobby:"参加者を待っています", question:"答えを選んでください", answer_closed:"回答を締め切りました", buzzer_open:"早押しチャンス！", buzzer_locked:"司会が判定中です", result:"結果発表", finished:"おつかれさまでした！" })[phase] || "待機中";
  choices.replaceChildren(); buzzButton.classList.add("hidden"); audioButton.classList.add("hidden");
  if (q?.type === "choice" && phase === "question") q.choices.forEach((label, index) => {
    const button = document.createElement("button"); button.className = "choice"; button.textContent = `${index + 1}. ${label}`;
    button.disabled = Boolean(player?.answered); button.onclick = () => quiz.send("submit_answer", { choice:index + 1 }); choices.append(button);
  });
  if (q && ["buzzer_open", "buzzer_locked"].includes(phase)) {
    if (q.type === "audio") { audioButton.classList.remove("hidden"); audioButton.disabled = !q.audio_url; }
    buzzButton.classList.remove("hidden"); buzzButton.disabled = phase !== "buzzer_open";
  }
  document.querySelector("#player-result").textContent = phase === "result" && q ? `正解：${q.correct_text || ""}` : "";
}
function buzz() { if (state?.game.phase === "buzzer_open") quiz.send("buzz"); }
function playAudio() { const source = state?.question?.audio_url; if (!source) return; audio.src = source; audio.currentTime = 0; audio.play().catch(() => {}); }
buzzButton.addEventListener("click", buzz); audioButton.addEventListener("click", playAudio);
document.addEventListener("keydown", (event) => { if (event.code === "Space" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) { event.preventDefault(); buzz(); } });
setInterval(() => {
  const deadline = state?.game.deadline;
  if (deadline && ["question", "buzzer_open", "buzzer_locked"].includes(state.game.phase) && new Date(deadline) <= new Date()) quiz.send("expire_question");
}, 500);
