function createQuizSocket(gameId, onState, onEvent, options = {}) {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const adminPath = options.adminToken ? "admin/" : "";
  const query = options.adminToken ? `?key=${encodeURIComponent(options.adminToken)}` : "";
  const socket = new WebSocket(`${protocol}://${location.host}/ws/quiz/${gameId}/${adminPath}${query}`);
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "state") onState(message.state);
    else onEvent?.(message);
  });
  socket.addEventListener("close", () => onEvent?.({ type: "error", message: "通信が切れました。画面を再読み込みしてください。" }));
  return { send(action, extra = {}) { if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ action, ...extra })); } };
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}
