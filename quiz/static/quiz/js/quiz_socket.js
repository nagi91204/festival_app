function createQuizSocket(gameId, onState, onEvent, options = {}) {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const adminPath = options.adminToken ? "admin/" : "";
  const query = options.adminToken ? `?key=${encodeURIComponent(options.adminToken)}` : "";
  let socket;
  let retryDelay = 500;
  let retryTimer;
  const connect = () => {
    socket = new WebSocket(`${protocol}://${location.host}/ws/quiz/${gameId}/${adminPath}${query}`);
    socket.addEventListener("open", () => { retryDelay = 500; onEvent?.({ type: "socket_open" }); });
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.type === "state") onState(message.state);
      else onEvent?.(message);
    });
    socket.addEventListener("close", () => {
      onEvent?.({ type: "error", message: "通信を再接続しています…" });
      window.clearTimeout(retryTimer);
      retryTimer = window.setTimeout(connect, retryDelay);
      retryDelay = Math.min(retryDelay * 2, 5000);
    });
  };
  connect();
  return { send(action, extra = {}) { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ action, ...extra })); } };
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}
