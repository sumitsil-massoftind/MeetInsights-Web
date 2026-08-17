/* Chat UI — JSON APIs only (application/json) */

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function appendChatExchange(container, userMessage, assistantMessage) {
  if (!container) return;
  const empty = container.querySelector(".chat-empty");
  if (empty) empty.remove();

  const wrap = document.createElement("div");
  wrap.innerHTML = `
    <div class="chat-bubble user">
      <div class="chat-meta">You</div>
      <div>${escapeHtml(userMessage)}</div>
    </div>
    <div class="chat-bubble assistant">
      <div class="chat-meta"><i class="bi bi-stars me-1"></i>Assistant</div>
      <div>${escapeHtml(assistantMessage)}</div>
    </div>
  `;
  while (wrap.firstChild) {
    container.appendChild(wrap.firstChild);
  }
  container.scrollTop = container.scrollHeight;
}

async function postJson(url, body) {
  return window.MiAuth.postJson(url, body);
}

function initChatPage() {
  document.querySelectorAll(".chat-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      const selectedInput = form.querySelector("#selected-meeting-ids");
      if (selectedInput && !selectedInput.value.trim()) {
        return;
      }

      const url = form.getAttribute("data-api-url");
      const input = form.querySelector('input[name="message"], textarea[name="message"]');
      if (!url || !input) return;

      const message = (input.value || "").trim();
      if (!message) return;

      const submitBtn = form.querySelector('button[type="submit"]');
      const body = { message };

      if (form.getAttribute("data-chat-kind") === "project") {
        body.meeting_ids = selectedInput
          ? selectedInput.value.split(",").map((s) => s.trim()).filter(Boolean)
          : [];
      }

      if (submitBtn) submitBtn.disabled = true;
      try {
        const result = await postJson(url, body);
        const chat = result.data || {};
        const panel = form.closest(".chat-panel") || document;
        const messages = panel.querySelector("#chat-messages") || document.getElementById("chat-messages");
        appendChatExchange(
          messages,
          chat.user_message || message,
          chat.assistant_message || ""
        );
        input.value = "";
        input.focus();
      } catch (err) {
        if (typeof showToast === "function") {
          showToast(err.message || "Unable to send message.");
        }
      } finally {
        if (submitBtn && form.getAttribute("data-chat-kind") !== "project") {
          submitBtn.disabled = false;
        } else if (submitBtn && form.getAttribute("data-chat-kind") === "project") {
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
    if (form.getAttribute("data-chat-kind") === "project" && selectedInput && !selectedInput.value.trim()) {
      return;
    }

    const input = form.querySelector('input[name="message"]');
    if (!input) return;
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
    if (selectedInput) selectedInput.value = ids.join(",");
    if (selectionHint) {
      selectionHint.textContent =
        ids.length === 0
          ? "Select one or more meetings to chat about"
          : `${ids.length} meeting${ids.length === 1 ? "" : "s"} selected`;
    }
    const enabled = ids.length > 0;
    if (projectChatSend) projectChatSend.disabled = !enabled;
    if (projectChatInput) {
      projectChatInput.disabled = !enabled;
      projectChatInput.placeholder = enabled
        ? "Ask about selected meetings…"
        : "Select meetings to start chatting…";
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
