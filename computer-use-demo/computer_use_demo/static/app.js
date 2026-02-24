/**
 * Computer Use Demo — Frontend
 *
 * Architecture:
 *  - REST (fetch) for session CRUD and sending messages
 *  - EventSource (SSE) for receiving real-time agent events
 *  - noVNC iframe for the virtual desktop
 */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const state = {
  sessionId: null,
  eventSource: null,
  isRunning: false,
  apiLogCount: 0,
  pendingApiEntry: null,   // last api_request entry DOM node awaiting response
};

// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------
const $ = id => document.getElementById(id);
const dom = {
  sessionForm:     $("session-form"),
  providerSel:     $("provider"),
  apiKeyGroup:     $("api-key-group"),
  apiKeyInput:     $("api-key"),
  modelInput:      $("model"),
  toolVersionSel:  $("tool-version"),
  maxTokensInput:  $("max-tokens"),
  recentImgInput:  $("recent-images"),
  systemPromptTA:  $("system-prompt"),
  newSessionBtn:   $("new-session-btn"),

  sessionInfo:     $("session-info"),
  sessionIdDisp:   $("session-id-display"),
  sessionStatus:   $("session-status"),
  cancelBtn:       $("cancel-btn"),
  resetBtn:        $("reset-btn"),

  sessionsList:    $("sessions-ul"),

  emptyState:      $("empty-state"),
  messagesCtx:     $("messages-container"),
  typingIndicator: $("typing-indicator"),

  chatInput:       $("chat-input"),
  sendBtn:         $("send-btn"),

  vncFrame:        $("vnc-frame"),
  apiLogContainer: $("api-log-container"),
  apiLogEmpty:     $("api-log-empty"),

  lightbox:        $("lightbox"),
  lightboxImg:     $("lightbox-img"),
};

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(
      typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail)
    );
  }
  if (res.status === 204) return null;
  return res.json();
}

// ---------------------------------------------------------------------------
// Session management
// ---------------------------------------------------------------------------
async function createSession() {
  const body = {
    provider:                  dom.providerSel.value,
    api_key:                   dom.apiKeyInput.value,
    model:                     dom.modelInput.value,
    tool_version:              dom.toolVersionSel.value,
    max_tokens:                parseInt(dom.maxTokensInput.value, 10),
    only_n_most_recent_images: parseInt(dom.recentImgInput.value, 10),
    system_prompt_suffix:      dom.systemPromptTA.value,
  };
  return api("POST", "/sessions", body);
}

async function loadSessions() {
  try {
    const data = await api("GET", "/sessions");
    renderSessionList(data.sessions);
  } catch { /* ignore */ }
}

async function loadSession(sessionId) {
  const session = await api("GET", `/sessions/${sessionId}`);
  state.sessionId = sessionId;
  clearMessages();
  session.messages.forEach(renderMessageFromDB);
  updateSessionUI(session);
  connectSSE(sessionId);
  await loadSessions();
}

function renderSessionList(sessions) {
  dom.sessionsList.innerHTML = "";
  sessions.forEach(s => {
    const li = document.createElement("li");
    li.dataset.id = s.id;
    li.className = s.id === state.sessionId ? "active" : "";
    li.innerHTML = `
      <span class="session-item-model">${escHtml(s.model.split("-").slice(0,3).join("-"))}</span>
      <span class="session-item-id">${s.id.slice(0, 8)}…</span>
      <span class="session-item-status">${s.message_count} msgs · ${s.status}</span>
    `;
    li.addEventListener("click", () => loadSession(s.id));
    dom.sessionsList.appendChild(li);
  });
}

function updateSessionUI(session) {
  dom.sessionInfo.classList.remove("hidden");
  dom.sessionIdDisp.textContent = session.id;
  setStatus(session.status);

  dom.chatInput.disabled = false;
  dom.sendBtn.disabled = false;

  dom.emptyState.classList.add("hidden");

  // Show noVNC iframe
  dom.vncFrame.src = `http://${location.hostname}:6080/vnc.html?autoconnect=1&resize=scale&reconnect=1`;
}

// ---------------------------------------------------------------------------
// SSE
// ---------------------------------------------------------------------------
function connectSSE(sessionId) {
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
  const es = new EventSource(`/sessions/${sessionId}/stream`);
  state.eventSource = es;

  es.addEventListener("text", e => {
    const d = JSON.parse(e.data);
    appendAssistantText(d.text);
  });

  es.addEventListener("thinking", e => {
    const d = JSON.parse(e.data);
    appendThinking(d.thinking);
  });

  es.addEventListener("tool_use", e => {
    const d = JSON.parse(e.data);
    appendToolUse(d.tool_name, d.tool_input);
  });

  es.addEventListener("tool_result", e => {
    const d = JSON.parse(e.data);
    appendToolResult(d);
    hideTyping();
  });

  es.addEventListener("api_request", e => {
    const d = JSON.parse(e.data);
    addApiRequest(d);
    showTyping();
  });

  es.addEventListener("api_response", e => {
    const d = JSON.parse(e.data);
    updateApiResponse(d);
  });

  es.addEventListener("api_error", e => {
    const d = JSON.parse(e.data);
    appendSystemMessage(`API error: ${d.message}`, true);
    hideTyping();
  });

  es.addEventListener("done", e => {
    const d = JSON.parse(e.data);
    setRunning(false);
    hideTyping();
    if (d.final_status === "cancelled") {
      appendSystemMessage("Run cancelled.");
    } else if (d.final_status === "error") {
      appendSystemMessage("Run ended with an error.", true);
    }
    es.close();
    state.eventSource = null;
    loadSessions();
  });

  es.addEventListener("error", e => {
    if (e.data) {
      const d = JSON.parse(e.data);
      appendSystemMessage(`Error: ${d.message}`, true);
    }
    setRunning(false);
    hideTyping();
  });

  es.onerror = () => {
    // EventSource will auto-reconnect for transient failures
  };
}

// ---------------------------------------------------------------------------
// Sending messages
// ---------------------------------------------------------------------------
async function sendMessage() {
  const content = dom.chatInput.value.trim();
  if (!content || !state.sessionId) return;

  dom.chatInput.value = "";
  appendUserMessage(content);
  setRunning(true);
  showTyping();

  try {
    await api("POST", `/sessions/${state.sessionId}/messages`, { content });
    // SSE will start delivering events; re-subscribe if needed
    if (!state.eventSource || state.eventSource.readyState === 2 /* CLOSED */) {
      connectSSE(state.sessionId);
    }
  } catch (err) {
    appendSystemMessage(`Failed to send: ${err.message}`, true);
    setRunning(false);
    hideTyping();
  }
}

// ---------------------------------------------------------------------------
// DOM rendering helpers
// ---------------------------------------------------------------------------
function appendUserMessage(text) {
  const el = msgEl("user");
  el.textContent = text;
  insertMsg(el);
}

function appendAssistantText(text) {
  // Merge consecutive assistant text chunks into one bubble
  const last = dom.messagesCtx.querySelector(".message.assistant:last-of-type");
  if (last && !last.querySelector(".msg-label")) {
    last.textContent += text;
    scrollBottom();
    return;
  }
  const el = msgEl("assistant");
  el.textContent = text;
  insertMsg(el);
}

function appendThinking(text) {
  const el = msgEl("thinking");
  const label = document.createElement("div");
  label.className = "msg-label";
  label.textContent = "Thinking";
  el.appendChild(label);
  const body = document.createElement("div");
  body.textContent = text;
  el.appendChild(body);
  insertMsg(el);
}

function appendToolUse(name, input) {
  const el = msgEl("tool-use");
  const label = document.createElement("div");
  label.className = "msg-label";
  label.textContent = `Tool: ${name}`;
  el.appendChild(label);
  const pre = document.createElement("pre");
  pre.className = "tool-output";
  pre.textContent = JSON.stringify(input, null, 2);
  el.appendChild(pre);
  insertMsg(el);
}

function appendToolResult(data) {
  const el = msgEl("tool-result");
  const label = document.createElement("div");
  label.className = "msg-label";
  label.textContent = data.is_error ? "Tool Error" : "Tool Result";
  el.appendChild(label);

  if (data.screenshot_base64) {
    const img = document.createElement("img");
    img.className = "screenshot";
    img.src = `data:image/png;base64,${data.screenshot_base64}`;
    img.alt = "Screenshot";
    img.addEventListener("click", () => openLightbox(img.src));
    el.appendChild(img);
  }
  if (data.output) {
    const pre = document.createElement("pre");
    pre.className = "tool-output";
    pre.textContent = data.output;
    el.appendChild(pre);
  }
  if (data.error) {
    const err = document.createElement("div");
    err.className = "error-text";
    err.textContent = data.error;
    el.appendChild(err);
  }
  insertMsg(el);
}

function appendSystemMessage(text, isError = false) {
  const el = msgEl("system-msg");
  el.textContent = text;
  if (isError) el.style.color = "var(--red)";
  insertMsg(el);
}

function renderMessageFromDB(msg) {
  // Reconstruct display from persisted DB messages
  const dr = msg.display_role;
  const content = msg.content_json;

  if (dr === "user") {
    const text = Array.isArray(content)
      ? content.filter(b => b.type === "text").map(b => b.text).join("")
      : String(content);
    if (text) appendUserMessage(text);
    return;
  }

  if (dr === "assistant" && Array.isArray(content)) {
    content.forEach(block => {
      if (block.type === "text" && block.text) appendAssistantText(block.text);
      else if (block.type === "thinking" && block.thinking) appendThinking(block.thinking);
      else if (block.type === "tool_use") appendToolUse(block.name, block.input);
    });
    return;
  }

  if (dr === "tool" && Array.isArray(content)) {
    content.forEach(block => {
      if (block.type === "tool_result") {
        const inner = block.content;
        const text = Array.isArray(inner)
          ? inner.filter(b => b.type === "text").map(b => b.text).join("")
          : String(inner ?? "");
        appendToolResult({
          output: text || null,
          error: block.is_error ? text : null,
          screenshot_base64: null,
          is_error: !!block.is_error,
        });
      }
    });
  }
}

// ---------------------------------------------------------------------------
// API log panel
// ---------------------------------------------------------------------------
function addApiRequest(data) {
  if (dom.apiLogEmpty) dom.apiLogEmpty.style.display = "none";

  state.apiLogCount++;
  const entry = document.createElement("details");
  entry.className = "api-log-entry";
  entry.id = `api-log-${state.apiLogCount}`;

  const url = new URL(data.url);
  entry.innerHTML = `
    <summary>
      <span class="log-method">${escHtml(data.method)}</span>
      <span>${escHtml(url.pathname)}</span>
    </summary>
    <pre>${escHtml(JSON.stringify(data.body, null, 2))}</pre>
  `;
  dom.apiLogContainer.appendChild(entry);
  state.pendingApiEntry = entry;
}

function updateApiResponse(data) {
  if (!state.pendingApiEntry) return;
  const summary = state.pendingApiEntry.querySelector("summary");
  const statusEl = document.createElement("span");
  statusEl.className = `log-status ${data.status_code < 400 ? "ok" : "err"}`;
  statusEl.textContent = ` → ${data.status_code}`;
  summary.appendChild(statusEl);

  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(data.body, null, 2);
  state.pendingApiEntry.appendChild(pre);
  state.pendingApiEntry = null;
}

// ---------------------------------------------------------------------------
// UI state helpers
// ---------------------------------------------------------------------------
function setRunning(running) {
  state.isRunning = running;
  dom.sendBtn.disabled = running;
  dom.chatInput.disabled = running;
  if (running) {
    dom.cancelBtn.classList.remove("hidden");
    setStatus("running");
  } else {
    dom.cancelBtn.classList.add("hidden");
    setStatus("idle");
  }
}

function setStatus(status) {
  dom.sessionStatus.textContent = status;
  dom.sessionStatus.className = `status-badge ${status}`;
}

function showTyping() {
  dom.typingIndicator.classList.add("visible");
  scrollBottom();
}

function hideTyping() {
  dom.typingIndicator.classList.remove("visible");
}

function clearMessages() {
  // Remove all message elements but keep empty-state and typing indicator
  [...dom.messagesCtx.children].forEach(el => {
    if (el.id !== "empty-state" && el.id !== "typing-indicator") el.remove();
  });
  dom.apiLogContainer.innerHTML = '<div id="api-log-empty">API requests will appear here during a run.</div>';
  state.apiLogCount = 0;
  state.pendingApiEntry = null;
}

function msgEl(className) {
  const el = document.createElement("div");
  el.className = `message ${className}`;
  return el;
}

function insertMsg(el) {
  // Insert before the typing indicator
  dom.messagesCtx.insertBefore(el, dom.typingIndicator);
  scrollBottom();
}

function scrollBottom() {
  dom.messagesCtx.scrollTop = dom.messagesCtx.scrollHeight;
}

function openLightbox(src) {
  dom.lightboxImg.src = src;
  dom.lightbox.classList.add("visible");
}

function escHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------

// Provider toggle: hide API key for Bedrock/Vertex
dom.providerSel.addEventListener("change", () => {
  const needsKey = dom.providerSel.value === "anthropic";
  dom.apiKeyGroup.style.display = needsKey ? "" : "none";
});

// Create session
dom.sessionForm.addEventListener("submit", async e => {
  e.preventDefault();
  dom.newSessionBtn.disabled = true;
  dom.newSessionBtn.textContent = "Creating…";
  try {
    const session = await createSession();
    state.sessionId = session.id;
    clearMessages();
    updateSessionUI(session);
    connectSSE(session.id);
    await loadSessions();
  } catch (err) {
    alert(`Failed to create session: ${err.message}`);
  } finally {
    dom.newSessionBtn.disabled = false;
    dom.newSessionBtn.textContent = "Create Session";
  }
});

// New session button in info bar
dom.resetBtn.addEventListener("click", () => {
  if (state.eventSource) { state.eventSource.close(); state.eventSource = null; }
  state.sessionId = null;
  state.isRunning = false;
  dom.sessionInfo.classList.add("hidden");
  dom.chatInput.disabled = true;
  dom.sendBtn.disabled = true;
  clearMessages();
  dom.emptyState.classList.remove("hidden");
  dom.vncFrame.src = "about:blank";
});

// Cancel run
dom.cancelBtn.addEventListener("click", async () => {
  if (!state.sessionId) return;
  try {
    await api("DELETE", `/sessions/${state.sessionId}/run`);
  } catch { /* ignore — maybe already stopped */ }
});

// Send message
dom.sendBtn.addEventListener("click", sendMessage);
dom.chatInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Lightbox close
dom.lightbox.addEventListener("click", () => dom.lightbox.classList.remove("visible"));

// Tab switching
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    $(`tab-${tab.dataset.tab}`).classList.add("active");
  });
});

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
async function init() {
  await loadSessions();
  try {
    const cfg = await api("GET", "/config");
    if (cfg.anthropic_api_key && !dom.apiKeyInput.value) {
      dom.apiKeyInput.value = cfg.anthropic_api_key;
    }
  } catch { /* ignore — config endpoint optional */ }
}

init();
