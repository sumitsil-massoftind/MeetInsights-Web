/* On-demand English transcript translation + original/English toggle. */
(function (global) {
  const transcriptState = {
    original: [],
    translated: [],
    originalText: "",
    translatedText: "",
    view: "original",
    hasTranslation: false,
    isSegmentMode: true,
  };

  function escapeHtml(value) {
    if (typeof global.escapeHtml === "function") return global.escapeHtml(value);
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function readTranscriptData() {
    const node = document.getElementById("meeting-transcript-data");
    if (!node) return null;
    try {
      return JSON.parse(node.textContent || "{}");
    } catch (_err) {
      return null;
    }
  }

  function getSegmentContainers() {
    return Array.from(document.querySelectorAll("[data-transcript-segments]"));
  }

  function getPlainTranscriptBlocks() {
    return Array.from(document.querySelectorAll("[data-transcript-plain]"));
  }

  function renderSegmentMarkup(segment) {
    const speaker = escapeHtml(segment.speaker || "Unknown");
    const start = escapeHtml(segment.start || "");
    const end = escapeHtml(segment.end || "");
    const text = escapeHtml(segment.text || "");
    const stamp = start && end ? `${start} – ${end}` : start || end;
    const seekAttrs = start
      ? `data-transcript-start="${start}"${end ? ` data-transcript-end="${end}"` : ""} tabindex="0" role="button" aria-label="Jump to ${start}"`
      : "";
    const timeButton = stamp
      ? `<button
            type="button"
            class="transcript-time transcript-seek-btn"
            data-transcript-seek="${start}"
            title="Jump to ${start}"
          >
            ${stamp}
          </button>`
      : "";
    return `
      <article
        class="transcript-segment"
        ${seekAttrs}
      >
        <div class="transcript-segment-meta">
          <span class="transcript-speaker">${speaker}</span>
          ${timeButton}
        </div>
        <p class="transcript-segment-text mb-0">${text}</p>
      </article>
    `;
  }

  function renderSegments(segments) {
    return (segments || []).map((segment) => renderSegmentMarkup(segment)).join("");
  }

  function activeSegments() {
    if (transcriptState.view === "english" && transcriptState.hasTranslation) {
      return transcriptState.translated.length
        ? transcriptState.translated
        : transcriptState.original;
    }
    return transcriptState.original;
  }

  function activePlainText() {
    if (transcriptState.view === "english" && transcriptState.hasTranslation) {
      return transcriptState.translatedText || transcriptState.originalText;
    }
    return transcriptState.originalText;
  }

  function paintTranscriptView() {
    if (transcriptState.isSegmentMode) {
      const html = renderSegments(activeSegments());
      getSegmentContainers().forEach((container) => {
        container.innerHTML = html;
      });
      const root = typeof getTranscriptSyncRoot === "function" ? getTranscriptSyncRoot() : null;
      if (root) {
        root.querySelectorAll("[data-transcript-seek], .transcript-segment[data-transcript-start]").forEach((node) => {
          delete node.dataset.miBound;
        });
      }
      if (typeof initTranscriptSync === "function") {
        initTranscriptSync();
      }
      return;
    }

    const text = activePlainText();
    getPlainTranscriptBlocks().forEach((block) => {
      block.textContent = text;
    });
  }

  function setTranscriptView(view) {
    transcriptState.view = view === "english" ? "english" : "original";
    document.querySelectorAll("[data-transcript-view-toggle]").forEach((group) => {
      group.querySelectorAll("[data-transcript-view]").forEach((button) => {
        const isActive = button.getAttribute("data-transcript-view") === transcriptState.view;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
      });
    });
    paintTranscriptView();
  }

  function revealTranslationControls() {
    document.querySelectorAll("[data-transcript-tools]").forEach((tools) => {
      tools.setAttribute("data-has-translation", "true");
      const toggle = tools.querySelector("[data-transcript-view-toggle]");
      const button = tools.querySelector("[data-translate-transcript-btn]");
      if (toggle) toggle.classList.remove("d-none");
      if (button) button.classList.add("d-none");
    });
  }

  function applyTranslationPayload(payload) {
    const segments = Array.isArray(payload.transcript_segments_translated)
      ? payload.transcript_segments_translated
      : [];
    const translatedText = String(payload.transcript_translated || "").trim();

    if (segments.length) {
      transcriptState.isSegmentMode = true;
      transcriptState.translated = segments;
    } else if (translatedText) {
      transcriptState.isSegmentMode = false;
      transcriptState.translatedText = translatedText;
    } else {
      return;
    }

    transcriptState.hasTranslation = true;
    const dataNode = document.getElementById("meeting-transcript-data");
    if (dataNode) {
      try {
        const current = JSON.parse(dataNode.textContent || "{}");
        if (segments.length) current.translated = segments;
        if (translatedText) current.translated_text = translatedText;
        dataNode.textContent = JSON.stringify(current);
      } catch (_err) {
        /* ignore */
      }
    }

    revealTranslationControls();
    setTranscriptView("english");
  }

  function bindTranscriptToggles() {
    document.querySelectorAll("[data-transcript-view]").forEach((button) => {
      if (button.dataset.miTranscriptToggleBound === "true") return;
      button.dataset.miTranscriptToggleBound = "true";
      button.addEventListener("click", () => {
        if (!transcriptState.hasTranslation) return;
        setTranscriptView(button.getAttribute("data-transcript-view") || "original");
      });
    });
  }

  function bindTranslateButtons() {
    document.querySelectorAll("[data-translate-transcript-btn]").forEach((button) => {
      if (button.dataset.miTranslateBound === "true") return;
      button.dataset.miTranslateBound = "true";

      button.addEventListener("click", async () => {
        if (button.disabled) return;

        const tools = button.closest("[data-transcript-tools]");
        const meetingId = tools && tools.getAttribute("data-meeting-id");
        const url = tools && tools.getAttribute("data-socket-url");
        if (!meetingId) return;
        if (!url) {
          if (typeof showToast === "function") {
            showToast("Translation service is not configured.");
          }
          return;
        }
        if (!global.MiInsightSocket || typeof global.MiInsightSocket.connect !== "function") {
          if (typeof showToast === "function") {
            showToast("Translation client is not loaded.");
          }
          return;
        }

        button.disabled = true;
        const originalHtml = button.innerHTML;
        button.innerHTML =
          '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Translating…';

        try {
          await global.MiInsightSocket.connect(url);
          const result = await global.MiInsightSocket.requestTranslation(meetingId);
          applyTranslationPayload(result);
          if (typeof showToast === "function") showToast("English translation ready.");
        } catch (err) {
          if (typeof showToast === "function") {
            showToast(err.message || "Unable to translate the transcript. Please try again.");
          }
        } finally {
          button.disabled = false;
          button.innerHTML = originalHtml;
        }
      });
    });
  }

  function initTranscriptTranslation() {
    const data = readTranscriptData();
    if (!data) return;

    if (Array.isArray(data.original)) {
      transcriptState.isSegmentMode = true;
      transcriptState.original = data.original;
      transcriptState.translated = Array.isArray(data.translated) ? data.translated : [];
      transcriptState.hasTranslation = transcriptState.translated.length > 0;
    } else if (data.original_text) {
      transcriptState.isSegmentMode = false;
      transcriptState.originalText = String(data.original_text || "");
      transcriptState.translatedText = String(data.translated_text || "");
      transcriptState.hasTranslation = Boolean(transcriptState.translatedText);
    } else {
      return;
    }

    bindTranscriptToggles();
    bindTranslateButtons();

    if (transcriptState.hasTranslation) {
      revealTranslationControls();
    }
  }

  document.addEventListener("DOMContentLoaded", initTranscriptTranslation);
  document.addEventListener("mi:page-loaded", initTranscriptTranslation);
})(window);
