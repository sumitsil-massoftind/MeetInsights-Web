/* Chat UI — meeting and project chat via Socket.IO. */

function formatChatMarkdown(value) {
  let source = String(value || "").replace(/\r\n/g, "\n");
  if (!source.trim()) return "";

  // Close an in-progress **bold** marker so a partial reply can still render.
  if (((source.match(/\*\*/g) || []).length) % 2 === 1) {
    source += "**";
  }

  // Gemini often emits inline lists: "Intro: * Item one. * Item two"
  source = source.replace(/([.!?:])[ \t]+([*\-+])[ \t]+(?=\S)/g, "$1\n$2 ");
  source = source.replace(/([^\n])[ \t]+([*\-+])[ \t]+(?=\*\*|[A-Z])/g, "$1\n$2 ");
  source = source.replace(/^[ \t]+([*\-+])[ \t]+(?=\S)/gm, "$1 ");

  let text = escapeHtml(source.trim());
  text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  const html = [];
  let items = [];
  let ordered = false;

  function flushList() {
    if (!items.length) return;
    const tag = ordered ? "ol" : "ul";
    html.push(`<${tag}>${items.map((item) => `<li>${item}</li>`).join("")}</${tag}>`);
    items = [];
    ordered = false;
  }

  text.split("\n").forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line) {
      flushList();
      return;
    }

    const unordered = line.match(/^([*\-+]|•)\s+(.*)$/);
    if (unordered) {
      if (items.length && ordered) flushList();
      ordered = false;
      items.push(unordered[2]);
      return;
    }

    const numbered = line.match(/^(\d+)[.)]\s+(.*)$/);
    if (numbered) {
      if (items.length && !ordered) flushList();
      ordered = true;
      items.push(numbered[2]);
      return;
    }

    flushList();
    html.push(`<p>${line}</p>`);
  });
  flushList();
  return html.join("");
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function clearChatEmpty(container) {
  const empty = container && container.querySelector(".chat-empty");
  if (empty) empty.remove();
}

function scrollChat(container) {
  if (container) container.scrollTop = container.scrollHeight;
}

function appendUserBubble(container, userMessage) {
  if (!container) return;
  clearChatEmpty(container);
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble user";
  bubble.innerHTML = `<div class="chat-meta">You</div><div>${escapeHtml(userMessage)}</div>`;
  container.appendChild(bubble);
  scrollChat(container);
  return bubble;
}

function appendAssistantTyping(container) {
  if (!container) return null;
  clearChatEmpty(container);
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble assistant is-thinking";
  bubble.innerHTML = `
    <div class="chat-meta"><i class="bi bi-stars me-1"></i>Assistant</div>
    <div class="chat-thinking" aria-live="polite" aria-label="Assistant is thinking">
      <span class="chat-thinking-sparkle"><i class="bi bi-stars"></i></span>
      <span class="chat-thinking-copy">
        <span class="chat-thinking-label">Thinking</span>
        <span class="chat-thinking-dots" aria-hidden="true"><i></i><i></i><i></i></span>
      </span>
    </div>
  `;
  const labels = ["Thinking", "Reading the summary", "Writing a reply"];
  let labelIndex = 0;
  const labelEl = bubble.querySelector(".chat-thinking-label");
  bubble._thinkingTimer = window.setInterval(() => {
    labelIndex = (labelIndex + 1) % labels.length;
    if (labelEl) labelEl.textContent = labels[labelIndex];
  }, 1400);
  container.appendChild(bubble);
  scrollChat(container);
  return bubble;
}

function typeAssistantReply(bubble, text) {
  return new Promise((resolve) => {
    if (!bubble) {
      resolve();
      return;
    }
    if (bubble._thinkingTimer) {
      window.clearInterval(bubble._thinkingTimer);
      bubble._thinkingTimer = null;
    }
    if (bubble._typeTimer) {
      window.clearTimeout(bubble._typeTimer);
      bubble._typeTimer = null;
    }

    bubble.classList.remove("is-thinking");
    bubble.classList.add("is-typing");
    const body = document.createElement("div");
    body.className = "chat-assistant-text";
    const typing = bubble.querySelector(".chat-thinking, .chat-typing");
    if (typing) typing.replaceWith(body);
    else bubble.appendChild(body);

    const full = String(text || "");
    if (!full) {
      bubble.classList.remove("is-typing");
      resolve();
      return;
    }

    const container = bubble.closest(".chat-messages");
    const step = Math.max(4, Math.ceil(full.length / 120));
    let index = 0;

    function paint(done) {
      body.innerHTML = formatChatMarkdown(full.slice(0, index));
      scrollChat(container);
      if (done) {
        bubble.classList.remove("is-typing");
        body.innerHTML = formatChatMarkdown(full);
        scrollChat(container);
        resolve();
      }
    }

    function tick() {
      index = Math.min(full.length, index + step);
      const done = index >= full.length;
      paint(done);
      if (!done) {
        bubble._typeTimer = window.setTimeout(tick, 16);
      }
    }

    tick();
  });
}

let activeMeetingChatId = "";
const meetingChatHistory = [];
let activeProjectChatKey = "";
const projectChatHistory = [];

function resetMeetingChatHistory(meetingId) {
  if (activeMeetingChatId !== meetingId) {
    activeMeetingChatId = meetingId;
    meetingChatHistory.length = 0;
  }
}

function resetProjectChatHistory(meetingIds) {
  const key = meetingIds.slice().sort().join(",");
  if (activeProjectChatKey !== key) {
    activeProjectChatKey = key;
    projectChatHistory.length = 0;
  }
}

function selectedMeetingIdsWithSummary() {
  return Array.from(document.querySelectorAll(".meeting-select:checked"))
    .filter((el) => el.getAttribute("data-has-summary") === "true")
    .map((el) => el.value);
}

async function sendMeetingChat(form, message) {
  const panel = form.closest(".chat-panel");
  const meetingId = panel && panel.getAttribute("data-meeting-id");
  const socketUrl = panel && panel.getAttribute("data-socket-url");
  const hasSummary = panel && panel.getAttribute("data-has-summary") === "true";

  if (!meetingId || !socketUrl) {
    throw new Error("Chat service is not configured.");
  }
  if (!hasSummary) {
    throw new Error("Generate a summary before chatting about this meeting.");
  }
  if (!window.MiInsightSocket) {
    throw new Error("Chat client is not loaded.");
  }

  resetMeetingChatHistory(meetingId);
  await window.MiInsightSocket.connect(socketUrl);
  return window.MiInsightSocket.requestChat(meetingId, message, meetingChatHistory);
}

async function sendProjectChat(form, message, meetingIds) {
  const panel = form.closest(".chat-panel");
  const socketUrl = panel && panel.getAttribute("data-socket-url");
  if (!socketUrl) {
    throw new Error("Chat service is not configured.");
  }
  if (!window.MiInsightSocket) {
    throw new Error("Chat client is not loaded.");
  }
  if (!meetingIds.length) {
    throw new Error("Select at least one meeting that has an AI summary.");
  }

  resetProjectChatHistory(meetingIds);
  await window.MiInsightSocket.connect(socketUrl);
  return window.MiInsightSocket.requestChat(
    meetingIds[0],
    message,
    projectChatHistory,
    meetingIds
  );
}

function initChatPage() {
  document.querySelectorAll(".chat-form").forEach((form) => {
    if (form.dataset.miChatBound === "true") return;
    form.dataset.miChatBound = "true";

    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      const selectedInput = form.querySelector("#selected-meeting-ids");
      const summarizedIds =
        form.getAttribute("data-chat-kind") === "project" ? selectedMeetingIdsWithSummary() : [];
      if (form.getAttribute("data-chat-kind") === "project" && !summarizedIds.length) {
        if (typeof showToast === "function") {
          showToast("Select at least one meeting that has an AI summary.");
        }
        return;
      }

      const input = form.querySelector('input[name="message"], textarea[name="message"]');
      if (!input) return;

      const message = (input.value || "").trim();
      if (!message) return;

      const submitBtn = form.querySelector('button[type="submit"]');
      const chatKind = form.getAttribute("data-chat-kind") || "meeting";
      const panel = form.closest(".chat-panel") || document;
      const messages =
        panel.querySelector("#chat-messages") || document.getElementById("chat-messages");

      if (submitBtn) submitBtn.disabled = true;
      input.value = "";
      input.focus();
      const userBubble = appendUserBubble(messages, message);
      const typingBubble = appendAssistantTyping(messages);

      try {
        let assistantMessage = "";
        if (chatKind === "project") {
          const result = await sendProjectChat(form, message, summarizedIds);
          assistantMessage = result.assistant_message || "";
          projectChatHistory.push({ role: "user", content: message });
          projectChatHistory.push({ role: "assistant", content: assistantMessage });
        } else {
          const result = await sendMeetingChat(form, message);
          assistantMessage = result.assistant_message || "";
          meetingChatHistory.push({ role: "user", content: message });
          meetingChatHistory.push({ role: "assistant", content: assistantMessage });
        }
        await typeAssistantReply(typingBubble, assistantMessage);
      } catch (err) {
        if (typingBubble) {
          if (typingBubble._thinkingTimer) window.clearInterval(typingBubble._thinkingTimer);
          typingBubble.remove();
        }
        if (userBubble) userBubble.remove();
        input.value = message;
        input.focus();
        if (typeof showToast === "function") {
          showToast(err.message || "Unable to send message.");
        }
      } finally {
        if (submitBtn && chatKind !== "project") {
          submitBtn.disabled = false;
        } else if (submitBtn && chatKind === "project") {
          const hasSelection = selectedInput && selectedInput.value.trim();
          submitBtn.disabled = !hasSelection;
        }
      }
    });
  });

  if (!document.body.dataset.miChatSuggestionsBound) {
    document.body.dataset.miChatSuggestionsBound = "true";
    document.body.addEventListener("click", (event) => {
      const suggestion = event.target.closest(".chat-suggestion");
      if (!suggestion) return;
      const prompt = suggestion.getAttribute("data-chat-prompt");
      if (!prompt) return;

      const form =
        suggestion.closest(".chat-panel")?.querySelector(".chat-form") ||
        document.querySelector(".chat-panel .chat-form");
      if (!form) return;

      const selectedInput = document.getElementById("selected-meeting-ids");
      if (form.getAttribute("data-chat-kind") === "project") {
        if (!selectedMeetingIdsWithSummary().length) {
          if (typeof showToast === "function") {
            showToast("Select at least one meeting that has an AI summary.");
          }
          return;
        }
      }

      const panel = form.closest(".chat-panel");
      if (form.getAttribute("data-chat-kind") === "meeting" && panel) {
        if (panel.getAttribute("data-has-summary") !== "true") {
          if (typeof showToast === "function") {
            showToast("Generate a summary before chatting about this meeting.");
          }
          return;
        }
      }

      const input = form.querySelector('input[name="message"]');
      if (!input || input.disabled) return;
      input.value = prompt;
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
      }
    });
  }

  const selectedInput = document.getElementById("selected-meeting-ids");
  const selectionHint = document.getElementById("selection-hint");
  const projectChatSend = document.getElementById("project-chat-send");
  const projectChatInput = document.getElementById("project-chat-input");

  function getSelectedMeetingIds() {
    return Array.from(document.querySelectorAll(".meeting-select:checked")).map((el) => el.value);
  }

  function updateSelectionUI() {
    const ids = getSelectedMeetingIds();
    const summarizedIds = selectedMeetingIdsWithSummary();
    if (selectedInput) selectedInput.value = summarizedIds.join(",");
    if (selectionHint) {
      if (ids.length === 0) {
        selectionHint.textContent = "Select one or more meetings with an AI summary";
      } else if (!summarizedIds.length) {
        selectionHint.textContent = "Selected meetings do not have a summary yet";
      } else if (summarizedIds.length < ids.length) {
        selectionHint.textContent = `${summarizedIds.length} of ${ids.length} selected meetings have a summary`;
      } else {
        selectionHint.textContent = `${summarizedIds.length} meeting${summarizedIds.length === 1 ? "" : "s"} selected`;
      }
    }
    const enabled = summarizedIds.length > 0;
    if (projectChatSend) projectChatSend.disabled = !enabled;
    if (projectChatInput) {
      projectChatInput.disabled = !enabled;
      projectChatInput.placeholder = enabled
        ? "Ask about selected meetings…"
        : "Select meetings with a summary to chat…";
    }
  }

  document.querySelectorAll(".meeting-select").forEach((cb) => {
    cb.addEventListener("change", updateSelectionUI);
  });

  const selectAll = document.getElementById("select-all-meetings");
  if (selectAll) {
    selectAll.addEventListener("change", () => {
      document.querySelectorAll(".meeting-select").forEach((cb) => {
        cb.checked = selectAll.checked;
      });
      updateSelectionUI();
    });
  }

  updateSelectionUI();
}

document.addEventListener("DOMContentLoaded", initChatPage);
document.addEventListener("mi:page-loaded", initChatPage);
