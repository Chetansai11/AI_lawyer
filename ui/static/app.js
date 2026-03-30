/**
 * AI Intake Auditor — web client (calls same-origin /chat).
 */

const SESSION_KEY = "ai_intake_auditor_session_id";

const messagesEl = document.getElementById("messages");
const briefEl = document.getElementById("brief");
const logsEl = document.getElementById("logs");
const composer = document.getElementById("composer");
const inputEl = document.getElementById("user-input");
const btnSend = document.getElementById("btn-send");
const btnNew = document.getElementById("btn-new");
const sessionBadge = document.getElementById("session-badge");
const toastEl = document.getElementById("toast");

function getSessionId() {
  return sessionStorage.getItem(SESSION_KEY) || null;
}

function setSessionId(id) {
  if (id) sessionStorage.setItem(SESSION_KEY, id);
  else sessionStorage.removeItem(SESSION_KEY);
  sessionBadge.textContent = id ? `···${id.slice(-8)}` : "New";
}

function showToast(message, isError = false) {
  toastEl.textContent = message;
  toastEl.hidden = false;
  toastEl.classList.toggle("error", isError);
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => {
    toastEl.hidden = true;
  }, 4200);
}

function appendMessage(role, text) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const meta = document.createElement("div");
  meta.className = "msg-meta";
  meta.textContent = role === "user" ? "You" : "AI Intake Auditor";
  const body = document.createElement("div");
  body.className = "msg-body";
  body.textContent = text;
  wrap.append(meta, body);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderBrief(markdown) {
  const ph = briefEl.querySelector(".brief-placeholder");
  if (ph) ph.remove();

  if (typeof marked === "undefined" || typeof DOMPurify === "undefined") {
    briefEl.textContent = markdown;
    return;
  }
  const html = marked.parse(markdown, { mangle: false, headerIds: false });
  briefEl.innerHTML = DOMPurify.sanitize(html);
}

function renderLogs(lines) {
  logsEl.textContent = Array.isArray(lines) ? lines.join("\n") : String(lines || "");
}

async function sendMessage(text) {
  const payload = {
    message: text,
    session_id: getSessionId(),
  };

  btnSend.disabled = true;
  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      let detail = err.detail;
      if (Array.isArray(detail)) {
        detail = detail.map((x) => x.msg || JSON.stringify(x)).join("; ");
      }
      throw new Error(detail || `${res.status} ${res.statusText}`);
    }

    const data = await res.json();
    setSessionId(data.session_id);
    appendMessage("assistant", data.reply);
    renderBrief(data.brief);
    renderLogs(data.logs);
  } catch (e) {
    showToast(e.message || "Request failed", true);
  } finally {
    btnSend.disabled = false;
  }
}

composer.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;

  appendMessage("user", text);
  inputEl.value = "";
  await sendMessage(text);
});

btnNew.addEventListener("click", () => {
  setSessionId(null);
  messagesEl.innerHTML = "";
  briefEl.innerHTML = '<p class="brief-placeholder">Your structured brief will appear here after you send the first message.</p>';
  logsEl.textContent = "";
  inputEl.focus();
  showToast("New session — start with your intake message.");
});

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    composer.requestSubmit();
  }
});

setSessionId(getSessionId());
