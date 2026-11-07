const gameId = document.body.dataset.gameId;
const storageKey = `festival-quiz-player-${gameId}`;
let state = null;
let me = JSON.parse(localStorage.getItem(storageKey) || "null");
let rejoinSent = false;
let previousScore = null;
let renderedChoicesSignature = null;
const joinPanel = document.querySelector("#join-panel");
const playerPanel = document.querySelector("#player-panel");
const playerFooter = document.querySelector("#player-footer");
const joinError = document.querySelector("#join-error");
const status = document.querySelector("#player-status");
const question = document.querySelector("#player-question");
const choices = document.querySelector("#choices");
const buzzButton = document.querySelector("#buzz-button");
const audioButton = document.querySelector("#audio-play-button");
const videoButton = document.querySelector("#video-play-button");
const videoOverlay = document.querySelector("#video-overlay");
const playerVideo = document.querySelector("#player-video");
let videoQuestionSignature = null;
const audio = new Audio();
const quiz = createQuizSocket(gameId, render, handleEvent);
function rankingMarkup(entries, emptyMessage) {
  return entries.length
    ? entries.map((entry, index) => `<li><span>${entry.rank || index + 1}位　${escapeHtml(entry.player_name || entry.nickname)}</span><strong>${entry.score} pt</strong></li>`).join("")
    : `<li class="ranking-empty">${emptyMessage}</li>`;
}

function handleEvent(event) {
  if (event.type === "socket_open") {
    rejoinSent = false;
    return;
  }
  if (event.type === "game_reset") {
    resetPlayerSession();
    return;
  }
  if (event.type === "joined") {
    me = { id: event.player_id, nickname: event.nickname }; rejoinSent = true;
    localStorage.setItem(storageKey, JSON.stringify(me));
    joinPanel.classList.add("hidden"); playerPanel.classList.remove("hidden"); playerFooter.classList.remove("hidden");
  }
  if (event.type === "play_audio") playAudio();
  if (event.type === "play_video") playVideo();
  if (event.type === "error") joinError.textContent = event.message;
}
document.querySelector("#join-form").addEventListener("submit", (event) => {
  event.preventDefault(); joinError.textContent = "";
  quiz.send("join_player", { nickname: document.querySelector("#nickname").value });
});

function render(nextState) {
  state = nextState;
  const phase = state.game.phase;
  if (me && phase === "lobby" && !state.players.some((item) => item.id === me.id)) resetPlayerSession();
  if (me && !rejoinSent) {
    rejoinSent = true; joinPanel.classList.add("hidden"); playerPanel.classList.remove("hidden"); playerFooter.classList.remove("hidden");
    quiz.send("join_player", { nickname: me.nickname, player_id: me.id });
  }
  const player = state.players.find((item) => item.id === me?.id);
  const score = player?.score ?? 0;
  document.querySelector("#player-name").textContent = player?.nickname || me?.nickname || "ゲスト";
  document.querySelector("#player-score").textContent = `${score} pt`;
  if (previousScore !== null && score > previousScore) showScoreGain(score - previousScore);
  previousScore = score;
  const q = state.question; const myAnswer = state.my_answer;
  document.querySelector("#player-header-status").textContent = phase === "lobby" ? "参加受付" : phase === "finished" ? "ゲーム終了" : "ゲーム進行中";
  document.querySelector("#player-number").textContent = q ? `問題 ${q.number} / ${q.total}` : "";
  const typeName = ({ choice:"2択・4択問題", buzzer:"早押し問題", audio:"音当て問題", video:"動画当て問題", image:"画像予想問題" })[q?.type] || "次の問題";
  question.textContent = phase === "intro" ? `次は「${typeName}」です！` : q?.body || (phase === "finished" ? "ゲーム終了！" : "司会の開始を待っています");
  status.textContent = ({ lobby:"参加者を待っています", intro:"まもなく問題が表示されます", question:myAnswer ? "回答を受け付けました" : "答えを1つ選んでください", answer_closed:"回答を締め切りました", buzzer_open:"早押しチャンス！", buzzer_locked:"司会が判定中です", result:"結果発表", finished:"おつかれさまでした！" })[phase] || "待機中";
  renderChoices(q, phase, myAnswer);
  const questionSignature = q ? `${q.number}/${q.total}` : "";
  if (questionSignature !== videoQuestionSignature) { videoQuestionSignature = questionSignature; closeVideoOverlay(); }
  if (!["buzzer_open", "buzzer_locked"].includes(phase)) closeVideoOverlay();
  buzzButton.classList.add("hidden"); audioButton.classList.add("hidden"); videoButton.classList.add("hidden");
  if (q && ["buzzer_open", "buzzer_locked"].includes(phase)) {
    if (q.type === "audio") { audioButton.classList.remove("hidden"); audioButton.disabled = !q.audio_url; }
    if (q.type === "video") { videoButton.classList.remove("hidden"); videoButton.disabled = !q.video_url; }
    buzzButton.classList.remove("hidden"); buzzButton.disabled = phase !== "buzzer_open";
  }
  const result = document.querySelector("#player-result");
  result.classList.toggle("choice-confirm", phase === "question" && Boolean(myAnswer));
  result.textContent = phase === "result" && q ? `正解：${q.correct_text || ""}` : myAnswer && ["choice", "image"].includes(q?.type) ? `「${myAnswer.selected_choice}. ${q.choices[myAnswer.selected_choice - 1]}」に決めました！` : "";
  const finalRankings = document.querySelector("#player-final-rankings");
  finalRankings.classList.toggle("hidden", phase !== "finished");
  if (phase === "finished") {
    document.querySelector("#player-current-ranking").innerHTML = rankingMarkup(state.rankings || [], "今回のランキングはありません");
    document.querySelector("#player-all-time-ranking").innerHTML = rankingMarkup(state.all_time_rankings || [], "まだ記録がありません");
  }
}
function renderChoices(q, phase, myAnswer) {
  const canAnswer = ["choice", "image"].includes(q?.type) && phase === "question";
  const signature = canAnswer ? JSON.stringify([q.number, q.total, q.choices, myAnswer?.selected_choice ?? null]) : "";
  if (signature === renderedChoicesSignature) return;
  renderedChoicesSignature = signature;
  choices.replaceChildren();
  if (!canAnswer) return;
  q.choices.forEach((label, index) => {
    const button = document.createElement("button");
    button.className = `choice ${myAnswer?.selected_choice === index + 1 ? "choice-selected" : ""}`;
    button.textContent = `${index + 1}. ${label}`;
    button.disabled = Boolean(myAnswer);
    button.onclick = () => chooseAnswer(index + 1, label);
    choices.append(button);
  });
}
function resetPlayerSession() {
  localStorage.removeItem(storageKey);
  me = null;
  rejoinSent = false;
  previousScore = null;
  audio.pause();
  closeVideoOverlay();
  playerVideo.src = "";
  document.querySelector("#join-form").reset();
  joinError.textContent = "";
  joinPanel.classList.remove("hidden");
  playerPanel.classList.add("hidden");
  playerFooter.classList.add("hidden");
}
function chooseAnswer(choice, label) {
  if (state?.my_answer || state?.game.phase !== "question") return;
  document.querySelectorAll(".choice").forEach((button, index) => { button.disabled = true; button.classList.toggle("choice-selected", index + 1 === choice); });
  const result = document.querySelector("#player-result"); result.classList.add("choice-confirm"); result.textContent = `「${choice}. ${label}」に決めました！`;
  quiz.send("submit_answer", { choice });
}
function showScoreGain(delta) {
  const gain = document.querySelector("#player-score-gain"); gain.textContent = `+${delta} pt!`; gain.classList.remove("hidden");
  window.clearTimeout(showScoreGain.timer); showScoreGain.timer = window.setTimeout(() => gain.classList.add("hidden"), 2600);
}
function buzz() { if (state?.game.phase === "buzzer_open") quiz.send("buzz"); }
function playAudio() { const source = state?.question?.audio_url; if (!source) return; audio.src = source; audio.currentTime = 0; audio.play().catch(() => {}); }
function playVideo() { const source = state?.question?.video_url; if (!source) return; playerVideo.src = source; playerVideo.currentTime = 0; videoOverlay.classList.remove("hidden"); playerVideo.play().catch(() => {}); }
function closeVideoOverlay() { playerVideo.pause(); videoOverlay.classList.add("hidden"); }
buzzButton.addEventListener("click", buzz); audioButton.addEventListener("click", playAudio); videoButton.addEventListener("click", playVideo);
videoOverlay.addEventListener("click", (event) => { if (event.target !== playerVideo) closeVideoOverlay(); });
document.addEventListener("keydown", (event) => { if (event.code === "Enter" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) { event.preventDefault(); buzz(); } });
setInterval(() => quiz.send("tick"), 1000);
