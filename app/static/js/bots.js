/* Live bot status table — polls /api/bots. Re-inits on soft navigation. */

(function () {
  let pollTimer = null;
  let clickHandler = null;

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatTime(iso) {
    if (!iso) return "—";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return escapeHtml(iso);
    return date.toLocaleString();
  }

  function setStat(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = String(value ?? 0);
  }

  function render(status) {
    const body = document.getElementById("bots-table-body");
    if (!body || !status) return;

    const unreachable = document.getElementById("bots-unreachable");
    const unreachableMsg = document.getElementById("bots-unreachable-msg");
    const updatedLabel = document.getElementById("bots-updated-label");

    const reachable = Boolean(status.reachable);
    if (unreachable) {
      unreachable.classList.toggle("d-none", reachable);
      if (!reachable && unreachableMsg) {
        unreachableMsg.textContent =
          status.error || "Start the MeetRecorder worker to see live bot status.";
      }
    }

    setStat("bots-stat-total", status.max_concurrent);
    setStat("bots-stat-used", status.used);
    setStat("bots-stat-free", status.free);
    setStat("bots-stat-waiting", status.waiting);

    const bots = Array.isArray(status.bots) ? status.bots : [];
    if (!bots.length) {
      body.innerHTML = `
        <tr>
          <td colspan="4">
            <div class="empty-state">
              <span class="empty-state-icon"><i class="bi bi-robot"></i></span>
              <p class="empty-state-title">No bot slots reported yet</p>
              <p class="text-muted-mi small mb-0">Start the MeetRecorder worker with Docker bots enabled.</p>
            </div>
          </td>
        </tr>`;
      return;
    }

    body.innerHTML = bots
      .map((bot) => {
        const inUse = bot.status === "in_use";
        const statusBadge = inUse
          ? `<span class="badge-status recording"><span class="dot"></span> In use</span>`
          : `<span class="badge-status completed"><span class="dot"></span> Free</span>`;
        const meeting = bot.meeting_id
          ? `<a href="/meetings/${escapeHtml(bot.meeting_id)}" class="fw-semibold text-decoration-none mi-link">${escapeHtml(bot.meeting_title || "Untitled meeting")}</a>`
          : `<span class="text-muted-mi">—</span>`;
        return `
          <tr data-bot-id="${escapeHtml(bot.id)}">
            <td>
              <div class="fw-semibold">${escapeHtml(bot.bot_name || bot.id)}</div>
              <div class="small text-muted-mi">${escapeHtml(bot.id)}</div>
            </td>
            <td>${statusBadge}</td>
            <td>${meeting}</td>
            <td class="text-muted-mi small">${formatTime(bot.acquired_at)}</td>
          </tr>`;
      })
      .join("");

    if (updatedLabel && status._fromPoll) {
      updatedLabel.textContent = `Updated ${new Date().toLocaleTimeString()}`;
    }
  }

  async function refresh() {
    if (!document.getElementById("bots-table-body")) return;
    try {
      const response = window.MiAuth
        ? await window.MiAuth.apiFetch("/api/bots")
        : await fetch("/api/bots", {
            headers: { Accept: "application/json" },
            credentials: "same-origin",
          });
      const payload = await response.json();
      const data = payload?.response?.data || {};
      data._fromPoll = true;
      render(data);
    } catch (_err) {
      render({
        reachable: false,
        max_concurrent: 0,
        used: 0,
        free: 0,
        waiting: 0,
        bots: [],
        error: "Could not refresh bot status.",
        _fromPoll: true,
      });
    }
  }

  function teardown() {
    if (pollTimer) {
      window.clearInterval(pollTimer);
      pollTimer = null;
    }
    const refreshBtn = document.getElementById("bots-refresh-btn");
    if (refreshBtn && clickHandler) {
      refreshBtn.removeEventListener("click", clickHandler);
    }
    clickHandler = null;
  }

  function initBotsPage() {
    teardown();
    const body = document.getElementById("bots-table-body");
    if (!body) return;

    const initialEl = document.getElementById("bots-initial-data");
    try {
      const initial = initialEl ? JSON.parse(initialEl.textContent || "{}") : null;
      if (initial) render(initial);
    } catch {
      /* ignore */
    }

    const refreshBtn = document.getElementById("bots-refresh-btn");
    clickHandler = () => {
      void refresh();
    };
    refreshBtn?.addEventListener("click", clickHandler);

    pollTimer = window.setInterval(() => {
      void refresh();
    }, 5000);
  }

  document.addEventListener("DOMContentLoaded", initBotsPage);
  document.addEventListener("mi:page-loaded", initBotsPage);
})();
