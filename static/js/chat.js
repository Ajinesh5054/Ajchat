const { roomId, username } = window.CHAT_CONFIG;
const socket = io();

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("message-form");
const inputEl = document.getElementById("message-input");
const onlineListEl = document.getElementById("online-list");
const typingEl = document.getElementById("typing-indicator");
const memberCountEl = document.getElementById("member-count");

messagesEl.scrollTop = messagesEl.scrollHeight;

socket.on("connect", () => {
  socket.emit("join", { room_id: roomId });
});

window.addEventListener("beforeunload", () => {
  socket.emit("leave", { room_id: roomId });
});

function appendMessage({ username: sender, content, timestamp }) {
  const div = document.createElement("div");
  div.className = "message" + (sender === username ? " self" : "");
  div.innerHTML = `
    <span class="msg-user">${escapeHtml(sender)}</span>
    <span class="msg-time">${escapeHtml(timestamp)}</span>
    <div class="msg-content"></div>
  `;
  div.querySelector(".msg-content").textContent = content;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function appendSystemMessage(text, timestamp) {
  const div = document.createElement("div");
  div.className = "message system";
  div.textContent = `${text} · ${timestamp}`;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

socket.on("new_message", appendMessage);

socket.on("system_message", (data) => {
  appendSystemMessage(data.text, data.timestamp);
});

socket.on("presence_update", (data) => {
  onlineListEl.innerHTML = "";
  data.users.forEach((u) => {
    const li = document.createElement("li");
    li.textContent = u;
    onlineListEl.appendChild(li);
  });
  if (memberCountEl) memberCountEl.textContent = data.users.length;
});

let typingTimeout;
socket.on("user_typing", (data) => {
  typingEl.textContent = `${data.username} is typing...`;
  clearTimeout(typingTimeout);
  typingTimeout = setTimeout(() => (typingEl.textContent = ""), 1500);
});

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const content = inputEl.value.trim();
  if (!content) return;
  socket.emit("send_message", { room_id: roomId, content });
  inputEl.value = "";
});

let typingSentAt = 0;
inputEl.addEventListener("input", () => {
  const now = Date.now();
  if (now - typingSentAt > 800) {
    socket.emit("typing", { room_id: roomId });
    typingSentAt = now;
  }
});

// Share link copy + toggle
const copyBtn = document.getElementById("copy-btn");
if (copyBtn) {
  copyBtn.addEventListener("click", () => {
    const shareInput = document.getElementById("share-link");
    shareInput.select();
    navigator.clipboard.writeText(shareInput.value).then(() => {
      copyBtn.textContent = "Copied!";
      setTimeout(() => (copyBtn.textContent = "Copy"), 1500);
    });
  });
}

const toggleShare = document.getElementById("toggle-share");
if (toggleShare) {
  toggleShare.addEventListener("click", () => {
    document.getElementById("share-row").classList.toggle("hidden");
  });
}
