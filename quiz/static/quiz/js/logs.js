const gameId = document.body.dataset.gameId;
const adminToken = document.body.dataset.adminToken;
let state = null;
const quiz = createQuizSocket(gameId, render, () => {}, { adminToken });
setInterval(() => quiz.send("tick"), 1000);

function render(nextState) {
  state = nextState;
  renderLogs();
  renderPlayerPreview();
}

function renderLogs() {
  const list = document.querySelector("#full-log-list");
  const knownIds = new Set([...list.querySelectorAll("[data-log-id]")].map((item) => item.dataset.logId));
  if (state.logs.length) list.querySelector(".empty-list")?.remove();
  [...state.logs].reverse().forEach((log) => {
    if (knownIds.has(String(log.id))) return;
    const item = document.createElement("li");
    item.dataset.logId = log.id;
    item.innerHTML = `<time>${escapeHtml(log.created_at)}</time><span>${escapeHtml(log.message)}</span>`;
    list.prepend(item);
  });
}

function renderPlayerPreview() {
  const { game, question, players, answers } = state;
  const select = document.querySelector("#preview-player");
  const previous = select.value;
  select.innerHTML = `<option value="">回答者を選択</option>${players.map((player) => `<option value="${player.id}">${escapeHtml(player.nickname)}（${player.connected ? "接続中" : "切断中"}）</option>`).join("")}`;
  select.value = players.some((player) => player.id === previous) ? previous : players[0]?.id || "";
  const refresh = () => {
    const player = players.find((item) => item.id === select.value);
    const screen = document.querySelector("#preview-screen");
    if (!player) { screen.innerHTML = `<div class="preview-device-header"><strong>参加者画面</strong><span>LIVE PREVIEW</span></div><div class="preview-device-body">参加者を選ぶと、回答者画面のプレビューが表示されます。</div><div class="preview-device-footer"><span>参加者</span><strong>0 pt</strong></div>`; return; }
    const phaseText = ({ lobby:"参加受付中", intro:"まもなく問題が表示されます", question:"答えを1つ選んでください", answer_closed:"回答を締め切りました", buzzer_open:"早押しチャンス！", buzzer_locked:"司会が判定中です", result:"結果発表", finished:"おつかれさまでした！" })[game.phase] || "待機中";
    const answer = answers.find((item) => String(item.player_id) === String(player.id));
    const answerStatus = answer ? `この問題の回答：${answer.selected_choice}番を送信済み` : player.answered ? "この問題に回答済み" : game.phase === "question" ? "この問題はまだ未回答" : "回答待ち・または該当なし";
    const typeName = ({ choice:"2択・4択問題", buzzer:"早押し問題", audio:"音当て問題", video:"動画当て問題", image:"画像予想問題" })[question?.type] || "次の問題";
    const questionText = game.phase === "intro" ? `次は「${typeName}」です！` : question?.body || (game.phase === "finished" ? "ゲーム終了！" : "司会の開始を待っています");
    const choices = question?.type === "choice" && game.phase === "question" ? `<div class="preview-choices">${question.choices.map((choice, index) => `<div class="choice ${answer?.selected_choice === index + 1 ? "choice-selected" : ""}">${index + 1}. ${escapeHtml(choice)}</div>`).join("")}</div>` : "";
    const result = game.phase === "result" && question ? `正解：${escapeHtml(question.correct_text || "")}` : answer ? `「${answer.selected_choice}番」に決めました！` : "";
    const interaction = game.phase === "buzzer_open" || game.phase === "buzzer_locked" ? `<div class="preview-buzz ${game.phase === "buzzer_locked" ? "locked" : ""}">PUSH</div>` : question?.type === "audio" && game.phase === "question" ? `<div class="preview-audio">▶</div>` : "";
    screen.innerHTML = `<div class="preview-device-header"><strong>参加者画面</strong><span class="${player.connected ? "online" : "offline"}">● ${player.connected ? "接続中" : "切断中"}　•　LIVE PREVIEW</span></div><div class="preview-device-body"><p class="preview-status">${phaseText}</p><p class="preview-number">${question ? `問題 ${question.number}` : ""}</p><h3>${escapeHtml(questionText)}</h3>${question?.image_url && game.phase !== "intro" ? `<img class="preview-question-image" src="${escapeHtml(question.image_url)}" alt="問題画像" />` : ""}${choices}${interaction}<p class="preview-answer">${escapeHtml(result || (answerStatus === "回答待ち・または該当なし" ? "" : answerStatus))}</p></div><div class="preview-device-footer"><span>${escapeHtml(player.nickname)} さん</span><strong>${player.score} pt</strong></div>`;
  };
  select.onchange = refresh;
  refresh();
}
