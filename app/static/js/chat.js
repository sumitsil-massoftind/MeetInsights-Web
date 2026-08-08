/* Client-side chat helpers (UI only — no persistence) */

document.addEventListener("DOMContentLoaded", () => {
  // Clear chat empty state when first messages arrive
  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (event.target && event.target.id === "chat-messages") {
      const empty = event.target.querySelector(".chat-empty");
      if (empty) empty.remove();
      event.target.scrollTop = event.target.scrollHeight;
    }
  });

  // After submit, clear the message input
  document.body.addEventListener("htmx:afterRequest", (event) => {
    const form = event.target;
    if (form && form.matches && form.matches(".chat-form")) {
      const input = form.querySelector('input[name="message"], textarea[name="message"]');
      if (input) {
        input.value = "";
        input.focus();
      }
    }
  });

  // Guard project chat submits when nothing selected
  document.body.addEventListener(
    "submit",
    (event) => {
      const form = event.target;
      if (!form || !form.matches || !form.matches(".chat-form")) return;
      const selectedInput = form.querySelector("#selected-meeting-ids");
      if (selectedInput && !selectedInput.value.trim()) {
        event.preventDefault();
        event.stopPropagation();
      }
    },
    true
  );

  // Suggested prompts fill chat input and send
  document.body.addEventListener("click", (event) => {
    const suggestion = event.target.closest(".chat-suggestion");
    if (!suggestion) return;
    const prompt = suggestion.getAttribute("data-chat-prompt");
    if (!prompt) return;

    // Prefer active panel form (meeting or project)
    const form =
      suggestion.closest(".chat-panel")?.querySelector(".chat-form") ||
      document.querySelector(".chat-panel .chat-form");
    if (!form) return;

    const input = form.querySelector('input[name="message"]');
    if (!input) return;

    // On project page, require a selection before sending
    const selectedInput = document.getElementById("selected-meeting-ids");
    if (selectedInput && !selectedInput.value.trim()) {
      return;
    }

    input.value = prompt;
    if (typeof form.requestSubmit === "function") {
      form.requestSubmit();
    } else {
      form.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
    }
  });

  // Project multi-meeting selection
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
});
