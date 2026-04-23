// Vanilla client for the Computer Use Demo FastAPI backend.

const state = {
  config: null,
  chats: [],
  currentId: null,
  ws: null,
  lastSeq: 0,
  blocks: new Map(),
  rawText: new Map(),
  currentTurn: null,
  stepCount: 0,
};

function renderMarkdown(text) {
  if (typeof marked !== "undefined") {
    return marked.parse(text, { breaks: true });
  }
  const escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return escaped.replace(/\n/g, "<br>");
}

const el = {
  chatList: document.getElementById("chat-list"),
  newForm: document.getElementById("new-chat-form"),
  newTitle: document.getElementById("new-title"),
  newModel: document.getElementById("new-model"),
  newProvider: document.getElementById("new-provider"),
  newToolVersion: document.getElementById("new-tool-version"),
  chatTitle: document.getElementById("chat-title"),
  chatStatus: document.getElementById("chat-status"),
  cancelBtn: document.getElementById("cancel-btn"),
  transcript: document.getElementById("transcript"),
  msgForm: document.getElementById("message-form"),
  msgInput: document.getElementById("message-input"),
  msgSend: document.querySelector("#message-form button"),
  apiKeyInput: document.getElementById("api-key-input"),
  saveApiKeyBtn: document.getElementById("save-api-key"),
  baseUrlInput: document.getElementById("base-url-input"),
  saveBaseUrlBtn: document.getElementById("save-base-url"),
  systemPromptInput: document.getElementById("system-prompt-input"),
  saveSystemPromptBtn: document.getElementById("save-system-prompt"),
  vncIframe: document.getElementById("vnc-iframe"),
  vncToggle: document.getElementById("vnc-toggle"),
};

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "content-type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  if (res.status === 204) return null;
  return await res.json();
}

function populateSelect(select, values, defaultValue) {
  select.innerHTML = "";
  for (const v of values) {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    if (v === defaultValue) opt.selected = true;
    select.appendChild(opt);
  }
}

function setVncUrl(viewOnly) {
  const base = state.config.novnc_url;
  const sep = base.includes("?") ? "&" : "?";
  el.vncIframe.src = `${base}${sep}resize=scale&autoconnect=1&reconnect=1&reconnect_delay=2000&view_only=${viewOnly ? 1 : 0}`;
  el.vncToggle.textContent = `Toggle screen control (${viewOnly ? "off" : "on"})`;
  el.vncToggle.dataset.viewOnly = viewOnly ? "1" : "0";
}

function renderChats() {
  el.chatList.innerHTML = "";
  for (const c of state.chats) {
    const li = document.createElement("li");
    if (c.id === state.currentId) li.classList.add("active");
    const title = document.createElement("span");
    title.textContent = c.title || c.model;
    title.title = c.id;
    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = `${c.status} · ${c.message_count || 0}`;
    li.append(title, meta);
    li.addEventListener("click", () => selectChat(c.id));
    const del = document.createElement("span");
    del.className = "meta";
    del.textContent = "×";
    del.title = "Delete";
    del.style.cursor = "pointer";
    del.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm("Delete chat?")) return;
      await api(`/api/chats/${c.id}`, { method: "DELETE" });
      if (state.currentId === c.id) {
        state.currentId = null;
        closeWs();
        el.transcript.innerHTML = "";
        el.chatTitle.textContent = "Pick or create a chat";
        setUrlChat(null);
      }
      await refreshChats();
    });
    li.append(del);
    el.chatList.appendChild(li);
  }
}

async function refreshChats() {
  state.chats = await api("/api/chats");
  renderChats();
}

function setUrlChat(chatId) {
  const url = new URL(location.href);
  if (chatId) {
    url.searchParams.set("chat", chatId);
  } else {
    url.searchParams.delete("chat");
  }
  history.replaceState(null, "", url.toString());
}

function setStatus(status) {
  el.chatStatus.textContent = status;
  el.chatStatus.className = `status ${status}`;
  const running = status === "running";
  el.cancelBtn.disabled = !running || !state.currentId;
  el.msgInput.disabled = running || !state.currentId;
  el.msgSend.disabled = running || !state.currentId;
}

function showLoader() {
  removeLoader();
  const node = document.createElement("div");
  node.className = "msg assistant loader-msg";
  const loader = document.createElement("div");
  loader.className = "loader";
  for (let i = 0; i < 3; i++) loader.appendChild(document.createElement("span"));
  node.appendChild(loader);
  el.transcript.appendChild(node);
  el.transcript.scrollTop = el.transcript.scrollHeight;
}

function removeLoader() {
  const existing = el.transcript.querySelector(".loader-msg");
  if (existing) existing.remove();
}

function isComputerScreenshot(name) {
  return name === "computer";
}

// --- Tool summary ---

function toolSummary(name, input) {
  if (name === "computer") {
    const action = input.action || "?";
    if (action === "screenshot") return "screenshot";
    if (action === "left_click" || action === "right_click" || action === "double_click") {
      const coord = input.coordinate ? `(${input.coordinate.join(", ")})` : "";
      return `${action} ${coord}`;
    }
    if (action === "type") return `type "${(input.text || "").slice(0, 40)}"`;
    if (action === "key") return `key ${input.key || ""}`;
    if (action === "scroll") {
      const coord = input.coordinate ? `(${input.coordinate.join(", ")})` : "";
      return `scroll ${input.direction || ""} ${coord}`;
    }
    return action;
  }
  if (name === "bash") {
    const cmd = (input.command || "").split("\n")[0].slice(0, 60);
    return cmd || "bash";
  }
  if (name === "str_replace_based_edit_tool") {
    const cmd = input.command || "?";
    const path = input.path || "";
    return `${cmd} ${path}`;
  }
  return name;
}

// --- Collapsible step structure ---

function ensureMsgNode(turnId, role) {
  const key = `${turnId}:${role}`;
  if (state.blocks.has(key)) return state.blocks.get(key);
  const node = document.createElement("div");
  node.className = `msg ${role}`;
  const roleEl = document.createElement("div");
  roleEl.className = "role";
  roleEl.textContent = role;
  node.appendChild(roleEl);

  if (role === "assistant") {
    const toggleTop = document.createElement("button");
    toggleTop.className = "steps-toggle";
    toggleTop.style.display = "none";
    node.appendChild(toggleTop);

    const hidden = document.createElement("div");
    hidden.className = "steps-hidden";
    node.appendChild(hidden);

    const toggleBottom = document.createElement("button");
    toggleBottom.className = "steps-toggle";
    toggleBottom.style.display = "none";
    node.appendChild(toggleBottom);

    function syncToggles() {
      const count = hidden.querySelectorAll(".step-group").length || hidden.childElementCount;
      const expanded = hidden.classList.contains("expanded");
      const label = expanded ? "Hide steps" : `Show ${count} steps`;
      toggleTop.textContent = label;
      toggleBottom.textContent = label;
      toggleTop.style.display = count > 0 ? "inline-block" : "none";
      toggleBottom.style.display = count > 0 && expanded ? "inline-block" : "none";
    }

    for (const btn of [toggleTop, toggleBottom]) {
      btn.addEventListener("click", () => {
        hidden.classList.toggle("expanded");
        syncToggles();
      });
    }
  }

  el.transcript.appendChild(node);
  state.blocks.set(key, node);
  return node;
}

function collapseCurrentStep(turnId) {
  const parent = state.blocks.get(`${turnId}:assistant`);
  if (!parent) return;
  const hidden = parent.querySelector(":scope > .steps-hidden");
  if (!hidden) return;
  const allNodes = [
    ...parent.querySelectorAll(
      ":scope > .thinking, :scope > .tool-use, :scope > .tool-result, :scope > .step-status, :scope > .text"
    ),
  ];
  // Text/thinking AFTER the last tool-related node belongs to the upcoming step.
  // Only collapse up to (and including) the last tool node.
  let lastToolIdx = -1;
  for (let i = 0; i < allNodes.length; i++) {
    const cl = allNodes[i].classList;
    if (cl.contains("tool-use") || cl.contains("tool-result") || cl.contains("step-status") || cl.contains("step-text")) {
      lastToolIdx = i;
    }
  }
  const toCollapse = lastToolIdx >= 0 ? allNodes.slice(0, lastToolIdx + 1) : [];
  if (toCollapse.length > 0) {
    const group = document.createElement("div");
    group.className = "step-group";
    for (const node of toCollapse) group.appendChild(node);
    hidden.appendChild(group);
    updateStepsToggle(parent);
  }

  // Always clear cached block refs so the next API call creates fresh DOM nodes
  // instead of overwriting text that belongs to the current step.
  const prefix = `${turnId}:assistant:`;
  for (const key of [...state.blocks.keys()]) {
    if (key.startsWith(prefix) && (key.endsWith(":text") || key.endsWith(":thinking"))) {
      state.blocks.delete(key);
    }
  }
  for (const key of [...state.rawText.keys()]) {
    if (key.startsWith(`${turnId}:`)) {
      state.rawText.delete(key);
    }
  }
}

function collapseFinalStep(turnId) {
  if (state.stepCount === 0) return;
  const parent = state.blocks.get(`${turnId}:assistant`);
  if (!parent) return;
  const hidden = parent.querySelector(":scope > .steps-hidden");
  if (!hidden) return;

  // Collapse everything up to and including the last tool-related node.
  // Text/thinking before tool nodes = reasoning for that step (collapse with it).
  // Text after all tool nodes = final output (keep outside).
  const allNodes = [
    ...parent.querySelectorAll(
      ":scope > .thinking, :scope > .tool-use, :scope > .tool-result, :scope > .step-status, :scope > .text"
    ),
  ];
  let lastToolIdx = -1;
  for (let i = 0; i < allNodes.length; i++) {
    const cl = allNodes[i].classList;
    if (cl.contains("tool-use") || cl.contains("tool-result") || cl.contains("step-status")) {
      lastToolIdx = i;
    }
  }
  const toCollapse = lastToolIdx >= 0 ? allNodes.slice(0, lastToolIdx + 1) : [];
  if (toCollapse.length > 0) {
    const group = document.createElement("div");
    group.className = "step-group";
    for (const node of toCollapse) group.appendChild(node);
    hidden.appendChild(group);
  }
  updateStepsToggle(parent);

  // Move remaining text (the final output) into a separate card
  const textNodes = parent.querySelectorAll(":scope > .text");
  if (textNodes.length > 0) {
    const card = document.createElement("div");
    card.className = "msg assistant";
    const roleEl = document.createElement("div");
    roleEl.className = "role";
    roleEl.textContent = "assistant";
    card.appendChild(roleEl);
    for (const node of textNodes) card.appendChild(node);
    parent.after(card);
  }
}

function updateStepsToggle(parent) {
  const hidden = parent.querySelector(":scope > .steps-hidden");
  const toggles = parent.querySelectorAll(":scope > .steps-toggle");
  if (!hidden || toggles.length === 0) return;
  const count = hidden.querySelectorAll(".step-group").length || hidden.childElementCount;
  const expanded = hidden.classList.contains("expanded");
  const label = expanded ? "Hide steps" : `Show ${count} steps`;
  for (const t of toggles) {
    t.textContent = label;
    // Top toggle: visible when there are steps. Bottom toggle: only when expanded.
    t.style.display = count > 0 ? "inline-block" : "none";
  }
  // Bottom toggle hidden when collapsed
  if (toggles.length > 1 && !expanded) {
    toggles[toggles.length - 1].style.display = "none";
  }
}

function ensureBlockNode(turnId, blockIndex, kind) {
  const key = `${turnId}:assistant:${blockIndex}:${kind}`;
  if (state.blocks.has(key)) return state.blocks.get(key);
  const parent = ensureMsgNode(turnId, "assistant");
  const node = document.createElement("div");
  node.className = kind;
  parent.appendChild(node);
  state.blocks.set(key, node);
  return node;
}

// --- History rendering ---

function isStepMessage(m) {
  if (!Array.isArray(m.content)) return false;
  if (m.role === "assistant") return m.content.some((b) => b.type === "tool_use");
  if (m.role === "user") return m.content.every((b) => b.type === "tool_result");
  return false;
}

function renderHistory(messages) {
  el.transcript.innerHTML = "";
  state.blocks.clear();
  state.rawText.clear();

  let i = 0;
  while (i < messages.length) {
    if (isStepMessage(messages[i])) {
      const start = i;
      while (i < messages.length && isStepMessage(messages[i])) i++;
      renderCollapsedSteps(messages.slice(start, i));
    } else {
      renderSingleMessage(messages[i]);
      i++;
    }
  }
  el.transcript.scrollTop = el.transcript.scrollHeight;
}

function renderSingleMessage(m) {
  const node = document.createElement("div");
  node.className = `msg ${m.role}`;
  const role = document.createElement("div");
  role.className = "role";
  role.textContent = m.role;
  node.appendChild(role);
  const content = m.content;
  if (typeof content === "string") {
    const t = document.createElement("div");
    t.className = "text";
    t.textContent = content;
    node.appendChild(t);
  } else if (Array.isArray(content)) {
    for (const block of content) {
      const el_ = renderBlock(block);
      if (el_) node.appendChild(el_);
    }
  }
  el.transcript.appendChild(node);
}

function renderCollapsedSteps(stepMessages) {
  const wrapper = document.createElement("div");
  wrapper.className = "msg assistant";

  const roleEl = document.createElement("div");
  roleEl.className = "role";
  roleEl.textContent = "assistant";
  wrapper.appendChild(roleEl);

  const hidden = document.createElement("div");
  hidden.className = "steps-hidden";

  let stepCount = 0;
  let currentGroup = null;
  let currentToolName = null;
  let currentToolInput = null;
  let pendingNodes = [];

  for (const m of stepMessages) {
    if (!Array.isArray(m.content)) continue;
    for (const block of m.content) {
      if (block.type === "tool_use") {
        stepCount++;
        currentGroup = document.createElement("div");
        currentGroup.className = "step-group";
        currentToolName = block.name;
        currentToolInput = block.input || {};
        for (const p of pendingNodes) currentGroup.appendChild(p);
        pendingNodes = [];
        const status = document.createElement("div");
        status.className = "step-status";
        status.textContent = `Step ${stepCount}: ${toolSummary(block.name, currentToolInput)}`;
        currentGroup.appendChild(status);
        const toolEl = renderBlock(block);
        if (toolEl) currentGroup.appendChild(toolEl);
        hidden.appendChild(currentGroup);
      } else if (block.type === "tool_result") {
        const resEl = renderBlock(block, { toolName: currentToolName, toolInput: currentToolInput });
        if (resEl && currentGroup) currentGroup.appendChild(resEl);
      } else {
        const otherEl = renderBlock(block);
        if (!otherEl) continue;
        if (currentGroup) {
          currentGroup.appendChild(otherEl);
        } else {
          pendingNodes.push(otherEl);
        }
      }
    }
  }

  const toggleTop = document.createElement("button");
  toggleTop.className = "steps-toggle";
  toggleTop.style.display = "inline-block";
  toggleTop.textContent = `Show ${stepCount} steps`;

  const toggleBottom = document.createElement("button");
  toggleBottom.className = "steps-toggle";

  function syncToggles() {
    const expanded = hidden.classList.contains("expanded");
    const label = expanded ? "Hide steps" : `Show ${stepCount} steps`;
    toggleTop.textContent = label;
    toggleBottom.textContent = label;
    toggleBottom.style.display = expanded ? "inline-block" : "none";
  }

  for (const btn of [toggleTop, toggleBottom]) {
    btn.addEventListener("click", () => {
      hidden.classList.toggle("expanded");
      syncToggles();
    });
  }

  wrapper.appendChild(toggleTop);
  wrapper.appendChild(hidden);
  wrapper.appendChild(toggleBottom);
  el.transcript.appendChild(wrapper);
}

function renderBlock(block, { toolName, toolInput } = {}) {
  if (!block || typeof block !== "object") {
    const div = document.createElement("div");
    div.className = "text";
    div.textContent = String(block);
    return div;
  }
  if (block.type === "text") {
    const div = document.createElement("div");
    div.className = "text md";
    div.innerHTML = renderMarkdown(block.text || "");
    return div;
  }
  if (block.type === "thinking") {
    const div = document.createElement("div");
    div.className = "thinking";
    div.textContent = block.thinking || "";
    return div;
  }
  if (block.type === "tool_use") {
    const div = document.createElement("div");
    div.className = "tool-use";
    const label = document.createElement("span");
    label.className = "label";
    label.textContent = `tool: ${block.name}`;
    div.appendChild(label);
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(block.input || {}, null, 2);
    div.appendChild(pre);
    return div;
  }
  if (block.type === "tool_result") {
    const div = document.createElement("div");
    div.className = "tool-result";
    if (block.is_error) div.classList.add("error");
    const content = block.content || [];
    if (Array.isArray(content)) {
      const skipImg = isComputerScreenshot(toolName);
      for (const c of content) {
        if (c.type === "text") {
          const pre = document.createElement("pre");
          pre.textContent = c.text;
          div.appendChild(pre);
        } else if (c.type === "image" && c.source?.data && !skipImg) {
          const img = document.createElement("img");
          img.src = `data:${c.source.media_type};base64,${c.source.data}`;
          div.appendChild(img);
        }
      }
    } else if (typeof content === "string") {
      const pre = document.createElement("pre");
      pre.textContent = content;
      div.appendChild(pre);
    }
    if (div.childElementCount === 0) return null;
    return div;
  }
  const div = document.createElement("div");
  div.className = "text";
  div.textContent = JSON.stringify(block);
  return div;
}

// --- Event handling ---

function handleEvent(env) {
  state.lastSeq = Math.max(state.lastSeq, env.seq || 0);
  const turnId = env.turn_id;
  switch (env.type) {
    case "turn_started":
      state.currentTurn = turnId;
      state.stepCount = 0;
      setStatus("running");
      showLoader();
      break;
    case "text_delta": {
      removeLoader();
      const rawKey = `${turnId}:${env.data.block_index}:text`;
      const prev = state.rawText.get(rawKey) || "";
      const updated = prev + (env.data.text || "");
      state.rawText.set(rawKey, updated);
      const node = ensureBlockNode(turnId, env.data.block_index, "text");
      node.classList.add("md");
      node.innerHTML = renderMarkdown(updated);
      break;
    }
    case "thinking_delta": {
      removeLoader();
      const node = ensureBlockNode(turnId, env.data.block_index, "thinking");
      node.textContent += env.data.text || "";
      break;
    }
    case "assistant_block": {
      removeLoader();
      const block = env.data.block;
      if (block && block.type === "tool_use") {
        state.stepCount++;
        collapseCurrentStep(turnId);

        const parent = ensureMsgNode(turnId, "assistant");
        const status = document.createElement("div");
        status.className = "step-status";
        status.textContent = `Step ${state.stepCount}: ${toolSummary(block.name, block.input || {})}`;
        parent.appendChild(status);

        const node = ensureBlockNode(turnId, env.data.block_index, "tool-use");
        node.innerHTML = "";
        const label = document.createElement("span");
        label.className = "label";
        label.textContent = `tool: ${block.name}`;
        node.appendChild(label);
        const pre = document.createElement("pre");
        pre.textContent = JSON.stringify(block.input || {}, null, 2);
        node.appendChild(pre);
      }
      break;
    }
    case "tool_result": {
      removeLoader();
      const parent = ensureMsgNode(turnId, "assistant");
      const div = document.createElement("div");
      div.className = "tool-result" + (env.data.error ? " error" : "");
      if (env.data.output) {
        const pre = document.createElement("pre");
        pre.textContent = env.data.output;
        div.appendChild(pre);
      }
      if (env.data.error) {
        const pre = document.createElement("pre");
        pre.textContent = env.data.error;
        div.appendChild(pre);
      }
      if (env.data.image_url) {
        if (!isComputerScreenshot(env.data.tool_name)) {
          const img = document.createElement("img");
          img.src = env.data.image_url;
          div.appendChild(img);
        }
      }
      if (div.childElementCount > 0) {
        parent.appendChild(div);
      }
      break;
    }
    case "turn_complete": {
      removeLoader();
      collapseFinalStep(turnId);
      setStatus("idle");
      refreshChats();
      break;
    }
    case "cancelled":
      removeLoader();
      setStatus("idle");
      break;
    case "error": {
      removeLoader();
      setStatus("error");
      const node = document.createElement("div");
      node.className = "msg assistant";
      const role = document.createElement("div");
      role.className = "role";
      role.textContent = "error";
      const body = document.createElement("div");
      body.className = "tool-result error";
      const pre = document.createElement("pre");
      pre.textContent = env.data.message || "unknown error";
      body.appendChild(pre);
      node.append(role, body);
      el.transcript.appendChild(node);
      break;
    }
  }
  el.transcript.scrollTop = el.transcript.scrollHeight;
}

function closeWs() {
  if (state.ws) {
    state.ws.onclose = null;
    state.ws.close();
    state.ws = null;
  }
}

function openWs(chatId) {
  closeWs();
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${location.host}/api/chats/${chatId}/ws?since_seq=${state.lastSeq}`;
  const ws = new WebSocket(url);
  ws.onmessage = (evt) => {
    try {
      const env = JSON.parse(evt.data);
      if (env.type === "pong") return;
      handleEvent(env);
    } catch (err) {
      console.error("bad WS message", err);
    }
  };
  ws.onclose = () => {
    if (state.currentId !== chatId) return;
    setTimeout(() => openWs(chatId), 1000);
  };
  ws.onerror = () => ws.close();
  state.ws = ws;
}

async function selectChat(chatId) {
  state.currentId = chatId;
  state.blocks.clear();
  state.rawText.clear();
  const detail = await api(`/api/chats/${chatId}`);
  state.lastSeq = detail.last_event_seq || 0;
  el.chatTitle.textContent = detail.title || detail.model;
  setStatus(detail.status);
  renderHistory(detail.messages || []);
  renderChats();
  openWs(chatId);
  setUrlChat(chatId);
}

el.newForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    title: el.newTitle.value || null,
    model: el.newModel.value,
    provider: el.newProvider.value,
    tool_version: el.newToolVersion.value,
  };
  const created = await api("/api/chats", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  el.newTitle.value = "";
  await refreshChats();
  await selectChat(created.id);
});

el.msgInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    el.msgForm.requestSubmit();
  }
});

el.msgForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!state.currentId) return;
  const content = el.msgInput.value.trim();
  if (!content) return;
  const node = document.createElement("div");
  node.className = "msg user";
  const role = document.createElement("div");
  role.className = "role";
  role.textContent = "user";
  const text = document.createElement("div");
  text.className = "text";
  text.textContent = content;
  node.append(role, text);
  el.transcript.appendChild(node);
  el.msgInput.value = "";
  setStatus("running");
  try {
    await api(`/api/chats/${state.currentId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
  } catch (err) {
    setStatus("error");
    alert(err.message);
  }
});

el.cancelBtn.addEventListener("click", async () => {
  if (!state.currentId) return;
  try {
    await api(`/api/chats/${state.currentId}/cancel`, { method: "POST" });
  } catch (err) {
    console.error(err);
  }
});

el.saveApiKeyBtn.addEventListener("click", async () => {
  await api("/api/system/api-key", {
    method: "PUT",
    body: JSON.stringify({ api_key: el.apiKeyInput.value }),
  });
  el.apiKeyInput.value = "";
  alert("API key saved.");
});

el.saveBaseUrlBtn.addEventListener("click", async () => {
  await api("/api/system/base-url", {
    method: "PUT",
    body: JSON.stringify({ base_url: el.baseUrlInput.value }),
  });
  alert("Base URL saved.");
});

el.saveSystemPromptBtn.addEventListener("click", async () => {
  await api("/api/system/system-prompt", {
    method: "PUT",
    body: JSON.stringify({ suffix: el.systemPromptInput.value }),
  });
  alert("System prompt saved.");
});

el.vncToggle.addEventListener("click", () => {
  const viewOnly = el.vncToggle.dataset.viewOnly !== "1";
  setVncUrl(viewOnly);
});

async function bootstrap() {
  state.config = await api("/api/system");
  populateSelect(el.newModel, state.config.models, state.config.default_model);
  populateSelect(el.newProvider, state.config.providers, state.config.default_provider);
  populateSelect(
    el.newToolVersion,
    state.config.tool_versions,
    state.config.default_tool_version,
  );
  el.baseUrlInput.value = state.config.base_url || "";
  el.systemPromptInput.value = state.config.system_prompt_suffix || "";
  setVncUrl(true);
  setStatus("idle");
  await refreshChats();

  const requested = new URL(location.href).searchParams.get("chat");
  if (requested && state.chats.some((c) => c.id === requested)) {
    await selectChat(requested);
  } else if (requested) {
    setUrlChat(null);
  }
}

bootstrap().catch((err) => {
  console.error(err);
  alert(`Failed to load: ${err.message}`);
});
