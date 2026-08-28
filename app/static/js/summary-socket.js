/* MeetInsight Socket.IO client: summary + ephemeral meeting chat. */
(function (global) {
  const GENERATE_TIMEOUT_MS = 120000;
  const CHAT_TIMEOUT_MS = 60000;
  const CONNECT_TIMEOUT_MS = 8000;
  let socket = null;
  let socketUrl = "";
  let generatePromise = null;
  let chatPromise = null;

  function escapeHtml(value) {
    if (typeof global.escapeHtml === "function") return global.escapeHtml(value);
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function renderTopics(topics) {
    if (!topics || !topics.length) return "";
    return topics
      .map((topic) => {
        const title = escapeHtml((topic && topic.topic) || "Topic");
        const details = Array.isArray(topic && topic.details) ? topic.details : [];
        const list = details.length
          ? `<ul class="meeting-summary-list">${details
              .map((item) => `<li>${escapeHtml(item)}</li>`)
              .join("")}</ul>`
          : "";
        return `<h3 class="meeting-summary-topic-title">${title}</h3>${list}`;
      })
      .join("");
  }

  function renderList(title, items) {
    if (!items || !items.length) return "";
    const lis = items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    return `<h3 class="meeting-summary-subhead">${escapeHtml(title)}</h3><ul class="meeting-summary-list">${lis}</ul>`;
  }

  function renderActionItems(items) {
    if (!items || !items.length) return "";
    const lis = items
      .map((item) => {
        if (item && typeof item === "object") {
          const task = escapeHtml(item.task || "");
          const extras = [item.owner, item.deadline, item.timestamp]
            .filter(Boolean)
            .map((part) => escapeHtml(part))
            .join(" · ");
          const meta = extras ? ` <span class="text-muted-mi"> · ${extras}</span>` : "";
          return `<li>${task}${meta}</li>`;
        }
        return `<li>${escapeHtml(item)}</li>`;
      })
      .join("");
    return `<h3 class="meeting-summary-subhead">Action items</h3><ul class="meeting-summary-list">${lis}</ul>`;
  }

  function enableMeetingChat() {
    const panel = document.querySelector(".chat-panel[data-meeting-id]");
    if (!panel) return;
    panel.setAttribute("data-has-summary", "true");
    const badge = panel.querySelector(".chat-panel-badge");
    if (badge) {
      badge.hidden = false;
      badge.textContent = "Ready";
    }
    const input = panel.querySelector('input[name="message"]');
    const sendBtn = panel.querySelector(".chat-send-btn");
    if (input) {
      input.disabled = false;
      input.required = true;
      input.placeholder = "Ask anything about this meeting…";
    }
    if (sendBtn) sendBtn.disabled = false;
  }

  function renderText(title, value) {
    const text = String(value || "").trim();
    if (!text) return "";
    return `<h3 class="meeting-summary-subhead">${escapeHtml(title)}</h3><p class="meeting-summary-text">${escapeHtml(text)}</p>`;
  }

  function patchSummaryCard(data) {
    const body = document.querySelector(".meeting-summary-body");
    if (!body) return;
    const overview = data.summary || "";
    body.innerHTML = [
      `<p class="meeting-summary-text">${escapeHtml(overview)}</p>`,
      renderText("Objective", data.summary_objective || data.summary_meeting_objective),
      renderList("Key decisions", data.summary_decisions),
      renderList("Requirements", data.summary_requirements),
      renderList("Business rules & pricing", data.summary_business_rules),
      renderList("Technical considerations", data.summary_technical),
      renderTopics(data.summary_topics),
      renderActionItems(data.summary_action_items),
      renderList("Open questions", data.summary_open_questions),
      renderList("Risks and concerns", data.summary_risks),
      renderList("Contradictions / ambiguities", data.summary_contradictions),
      renderList("Important timestamps", data.summary_timestamps),
      renderText("Final outcome", data.summary_outcome),
    ].join("");
    enableMeetingChat();
    if (typeof enableCopySummaryButton === "function") enableCopySummaryButton();
  }

  function openSocket(url, token) {
    return new Promise((resolve, reject) => {
      const next = global.io(url, {
        auth: { token },
        transports: ["websocket", "polling"],
        withCredentials: false,
        reconnection: false,
      });
      const timer = window.setTimeout(() => {
        next.removeAllListeners();
        next.disconnect();
        reject(new Error("Could not connect to the summary service."));
      }, CONNECT_TIMEOUT_MS);

      next.once("connect", () => {
        window.clearTimeout(timer);
        resolve(next);
      });
      next.once("connect_error", () => {
        window.clearTimeout(timer);
        next.removeAllListeners();
        next.disconnect();
        const error = new Error("Could not connect to the summary service.");
        error.retryable = true;
        reject(error);
      });
    });
  }

  async function currentToken() {
    if (!window.MiAuth) throw new Error("Please sign in to continue.");
    let token = window.MiAuth.getAccessToken();
    if (!token) {
      await window.MiAuth.refreshAccessToken();
      token = window.MiAuth.getAccessToken();
    }
    if (!token) throw new Error("Please sign in to continue.");
    return token;
  }

  function socketIoSrc() {
    const current = document.querySelector('script[src*="summary-socket.js"]');
    if (current && current.src) {
      return current.src.replace(/summary-socket\.js.*$/, "vendor/socket.io.min.js");
    }
    return "/static/js/vendor/socket.io.min.js";
  }

  function ensureIo() {
    if (typeof global.io === "function") return Promise.resolve();
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = socketIoSrc();
      script.onload = () => {
        if (typeof global.io === "function") resolve();
        else reject(new Error("Socket.IO is not loaded."));
      };
      script.onerror = () => reject(new Error("Socket.IO is not loaded."));
      document.head.appendChild(script);
    });
  }

  async function connect(url) {
    await ensureIo();

    if (socket && socketUrl === url && socket.connected) return socket;
    if (socket) {
      socket.removeAllListeners();
      socket.disconnect();
      socket = null;
    }

    socketUrl = url;
    try {
      socket = await openSocket(url, await currentToken());
      return socket;
    } catch (err) {
      if (!err.retryable) throw err;
      const refreshed = await window.MiAuth.refreshAccessToken();
      if (!refreshed) throw new Error("Session expired. Please sign in again.");
      socket = await openSocket(url, window.MiAuth.getAccessToken());
      return socket;
    }
  }

  function requestSummary(meetingId) {
    if (generatePromise) return generatePromise;
    if (!socket || !socket.connected) {
      return Promise.reject(new Error("Summary service is not connected."));
    }

    generatePromise = new Promise((resolve, reject) => {
      const timer = window.setTimeout(() => {
        cleanup();
        reject(new Error("Summary generation timed out. Please try again."));
      }, GENERATE_TIMEOUT_MS);

      function matches(payload) {
        return !payload || !payload.meeting_id || payload.meeting_id === meetingId;
      }

      function cleanup() {
        window.clearTimeout(timer);
        socket.off("summary:ready", onReady);
        socket.off("summary:error", onError);
        generatePromise = null;
      }

      function onReady(payload) {
        if (!matches(payload)) return;
        cleanup();
        resolve(payload || {});
      }

      function onError(payload) {
        if (!matches(payload)) return;
        cleanup();
        reject(new Error((payload && payload.msg) || "Unable to generate the summary."));
      }

      socket.on("summary:ready", onReady);
      socket.on("summary:error", onError);
      socket.emit("summary:generate", { meeting_id: meetingId });
    });

    return generatePromise;
  }

  function requestChat(meetingId, message, history, meetingIds) {
    if (chatPromise) return chatPromise;
    if (!socket || !socket.connected) {
      return Promise.reject(new Error("Chat service is not connected."));
    }

    const ids = Array.isArray(meetingIds) && meetingIds.length
      ? meetingIds.map((id) => String(id || "").trim()).filter(Boolean)
      : [meetingId].filter(Boolean);

    chatPromise = new Promise((resolve, reject) => {
      const timer = window.setTimeout(() => {
        cleanup();
        reject(new Error("Chat timed out. Please try again."));
      }, CHAT_TIMEOUT_MS);

      function matches(payload) {
        if (!payload) return true;
        if (payload.meeting_id && ids.includes(payload.meeting_id)) return true;
        const replyIds = Array.isArray(payload.meeting_ids) ? payload.meeting_ids : [];
        return !payload.meeting_id || replyIds.some((id) => ids.includes(id));
      }

      function cleanup() {
        window.clearTimeout(timer);
        socket.off("chat:reply", onReply);
        socket.off("chat:error", onError);
        chatPromise = null;
      }

      function onReply(payload) {
        if (!matches(payload)) return;
        cleanup();
        resolve(payload || {});
      }

      function onError(payload) {
        if (!matches(payload)) return;
        cleanup();
        reject(new Error((payload && payload.msg) || "Unable to send message."));
      }

      socket.on("chat:reply", onReply);
      socket.on("chat:error", onError);
      socket.emit("chat:message", {
        meeting_id: ids[0] || meetingId,
        meeting_ids: ids,
        message,
        history: Array.isArray(history) ? history : [],
      });
    });

    return chatPromise;
  }

  function bindButtons() {
    const card = document.querySelector(".meeting-summary-card");
    document.querySelectorAll(".regenerate-summary-btn").forEach((button) => {
      if (button.dataset.miSummaryBound === "true") return;
      button.dataset.miSummaryBound = "true";
      button.addEventListener("click", async () => {
        if (button.disabled) return;
        const meetingId =
          button.getAttribute("data-meeting-id") ||
          (card && card.getAttribute("data-meeting-id"));
        const url = card && card.getAttribute("data-socket-url");
        if (!meetingId) return;
        if (!url) {
          if (typeof showToast === "function") showToast("Summary service is not configured.");
          return;
        }

        button.disabled = true;
        const originalHtml = button.innerHTML;
        button.innerHTML =
          '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Generating…';

        try {
          await connect(url);
          const result = await requestSummary(meetingId);
          patchSummaryCard(result);
          if (typeof showToast === "function") showToast("Summary updated.");
        } catch (err) {
          if (typeof showToast === "function") {
            showToast(err.message || "Unable to regenerate the summary. Please try again.");
          }
        } finally {
          button.disabled = false;
          button.innerHTML = originalHtml;
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", bindButtons);
  document.addEventListener("mi:page-loaded", bindButtons);

  global.MiInsightSocket = {
    connect,
    requestSummary,
    requestChat,
    patchSummaryCard,
  };
  global.MiSummary = global.MiInsightSocket;
})(window);
