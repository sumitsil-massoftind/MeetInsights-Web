/* Project scope generation on meeting detail (stored in MongoDB). */
(function (global) {
  function escapeHtml(value) {
    if (typeof global.escapeHtml === "function") return global.escapeHtml(value);
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function contextStorageKey(meetingId) {
    return `mi_scope_context_${meetingId}`;
  }

  function renderList(title, items) {
    if (!items || !items.length) return "";
    const lis = items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    return `<h3 class="meeting-summary-subhead">${escapeHtml(title)}</h3><ul class="meeting-summary-list">${lis}</ul>`;
  }

  function renderOverview(text) {
    const value = String(text || "").trim();
    if (!value) return "";
    return `<h3 class="meeting-summary-subhead">Project Overview</h3><p class="meeting-summary-text">${escapeHtml(value)}</p>`;
  }

  function renderScopeResult(data) {
    return [
      renderOverview(data.project_overview),
      renderList("Scope Changes", data.scope_changes),
      renderList("Objectives", data.objectives),
      renderList("In Scope", data.in_scope),
      renderList("Functional Requirements", data.functional_requirements),
      renderList("Business Rules", data.business_rules),
      renderList("Technical Requirements", data.technical_requirements),
      renderList("Dependencies", data.dependencies),
      renderList("Out of Scope", data.out_of_scope),
      renderList("Open Items", data.open_items),
    ]
      .filter(Boolean)
      .join("");
  }

  function getScopeCard() {
    return document.querySelector(".meeting-scope-card");
  }

  function setScopeError(message) {
    const errorEl = document.getElementById("project-scope-error");
    if (!errorEl) return;
    if (!message) {
      errorEl.classList.add("d-none");
      errorEl.textContent = "";
      return;
    }
    errorEl.textContent = message;
    errorEl.classList.remove("d-none");
  }

  function setScopeLoading(active) {
    const loadingEl = document.getElementById("project-scope-loading");
    const generateBtn = document.getElementById("generate-scope-btn");
    const regenerateBtn = document.getElementById("regenerate-scope-btn");
    const contextInput = document.getElementById("project-scope-context");
    const card = getScopeCard();
    const hasTranscript = card && card.getAttribute("data-has-transcript") === "true";
    if (loadingEl) loadingEl.classList.toggle("d-none", !active);
    if (generateBtn) generateBtn.disabled = active || !hasTranscript;
    if (regenerateBtn) regenerateBtn.disabled = active;
    if (contextInput) contextInput.disabled = active || !hasTranscript;
  }

  function showScopeResult(html) {
    const resultEl = document.getElementById("project-scope-result");
    const regenerateBtn = document.getElementById("regenerate-scope-btn");
    const copyBtn = document.getElementById("copy-scope-btn");
    if (!resultEl) return;
    resultEl.innerHTML = html || '<p class="meeting-summary-text mb-0">No scope details were returned.</p>';
    resultEl.classList.remove("d-none");
    if (regenerateBtn) regenerateBtn.classList.remove("d-none");
    if (copyBtn) copyBtn.classList.remove("d-none");
  }

  function persistScopeData(data) {
    let el = document.getElementById("meeting-scope-data");
    if (!el) {
      el = document.createElement("script");
      el.type = "application/json";
      el.id = "meeting-scope-data";
      const card = getScopeCard();
      if (card) card.appendChild(el);
    }
    el.textContent = JSON.stringify(data);
  }

  function scopeAlreadyRendered() {
    const resultEl = document.getElementById("project-scope-result");
    return Boolean(resultEl && resultEl.getAttribute("data-mi-scope-rendered") === "server");
  }

  function markScopeRendered() {
    const resultEl = document.getElementById("project-scope-result");
    if (resultEl) resultEl.setAttribute("data-mi-scope-rendered", "client");
  }

  function loadStoredScope() {
    const el = document.getElementById("meeting-scope-data");
    if (!el) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (_err) {
      return null;
    }
  }

  async function generateScope({ regenerate = false } = {}) {
    const card = getScopeCard();
    if (!card) return;

    const meetingId = card.getAttribute("data-meeting-id");
    const url = card.getAttribute("data-socket-url");
    const hasTranscript = card.getAttribute("data-has-transcript") === "true";
    const contextInput = document.getElementById("project-scope-context");
    if (!meetingId || !hasTranscript) {
      setScopeError("Generate a transcript before creating project scope.");
      return;
    }
    if (!url || !global.MiInsightSocket) {
      setScopeError("Scope service is not configured.");
      return;
    }

    const projectContext = contextInput ? contextInput.value || "" : "";
    window.sessionStorage.setItem(contextStorageKey(meetingId), projectContext);

    setScopeError("");
    setScopeLoading(true);
    if (!regenerate) {
      const resultEl = document.getElementById("project-scope-result");
      if (resultEl) resultEl.classList.add("d-none");
    }

    try {
      await global.MiInsightSocket.connect(url);
      const result = await global.MiInsightSocket.requestScope(meetingId, projectContext);
      showScopeResult(renderScopeResult(result));
      persistScopeData(result);
      markScopeRendered();
      if (typeof showToast === "function") {
        showToast(regenerate ? "Project scope updated." : "Project scope generated.");
      }
    } catch (err) {
      setScopeError(err.message || "Unable to generate project scope. Please try again.");
    } finally {
      setScopeLoading(false);
    }
  }

  function restoreContext() {
    const card = getScopeCard();
    const contextInput = document.getElementById("project-scope-context");
    if (!card || !contextInput) return;
    const meetingId = card.getAttribute("data-meeting-id");
    if (!meetingId) return;
    if (contextInput.value.trim()) return;
    const saved = window.sessionStorage.getItem(contextStorageKey(meetingId));
    if (saved != null) {
      contextInput.value = saved;
    }
  }

  function hydrateStoredScope() {
    const card = getScopeCard();
    const contextInput = document.getElementById("project-scope-context");
    const stored = loadStoredScope();
    const meetingId = card && card.getAttribute("data-meeting-id");

    if (stored && contextInput && stored.project_context && !contextInput.value.trim()) {
      contextInput.value = stored.project_context;
      if (meetingId) {
        window.sessionStorage.setItem(contextStorageKey(meetingId), stored.project_context);
      }
    } else if (!scopeAlreadyRendered()) {
      restoreContext();
    }

    if (stored && !scopeAlreadyRendered()) {
      showScopeResult(renderScopeResult(stored));
      markScopeRendered();
    }
  }

  function bindScopeButtons() {
    const card = getScopeCard();
    if (!card || card.dataset.miScopeBound === "true") return;
    card.dataset.miScopeBound = "true";

    hydrateStoredScope();

    const generateBtn = document.getElementById("generate-scope-btn");
    const regenerateBtn = document.getElementById("regenerate-scope-btn");
    const contextInput = document.getElementById("project-scope-context");

    if (contextInput) {
      contextInput.addEventListener("input", () => {
        const meetingId = card.getAttribute("data-meeting-id");
        if (meetingId) {
          window.sessionStorage.setItem(contextStorageKey(meetingId), contextInput.value || "");
        }
      });
    }

    if (generateBtn) {
      generateBtn.addEventListener("click", () => generateScope({ regenerate: false }));
    }
    if (regenerateBtn) {
      regenerateBtn.addEventListener("click", () => generateScope({ regenerate: true }));
    }
  }

  document.addEventListener("DOMContentLoaded", bindScopeButtons);
  document.addEventListener("mi:page-loaded", bindScopeButtons);
})(window);
