/* Socket.IO summary client: MeetInsight generates from the stored transcript. */
(function (global) {
  const GENERATE_TIMEOUT_MS = 120000;
  const CONNECT_TIMEOUT_MS = 8000;
  let socket = null;
  let socketUrl = "";
  let generatePromise = null;

  function escapeHtml(value) {
    if (typeof global.escapeHtml === "function") return global.escapeHtml(value);
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function renderList(title, items) {
    if (!items || !items.length) return "";
    const lis = items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    return `<h3 class="meeting-summary-subhead">${escapeHtml(title)}</h3><ul class="meeting-summary-list">${lis}</ul>`;
  }

  function patchSummaryCard(data) {
    const body = document.querySelector(".meeting-summary-body");
    if (!body) return;
    const overview = data.summary || "";
    body.innerHTML = [
      `<p class="meeting-summary-text">${escapeHtml(overview)}</p>`,
      renderList("Key points", data.summary_key_points),
      renderList("Decisions", data.summary_decisions),
      renderList("Action items", data.summary_action_items),
    ].join("");
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

  async function connect(url) {
    if (!global.io) throw new Error("Socket.IO is not loaded.");

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

  global.MiSummary = { connect, requestSummary, patchSummaryCard };
})(window);
