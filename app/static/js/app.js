/* Global UI helpers — application/json API client */

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function showToast(message) {
  const host = document.getElementById("toast-host");
  if (!host) return;
  host.innerHTML = `
    <div class="toast align-items-center text-bg-dark border-0 show" role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="3500">
      <div class="d-flex">
        <div class="toast-body">
          <i class="bi bi-info-circle me-2"></i>${escapeHtml(message)}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>
  `;
  const toastEl = host.querySelector(".toast");
  if (toastEl && window.bootstrap) {
    bootstrap.Toast.getOrCreateInstance(toastEl).show();
  }
}

async function postJson(url, body) {
  return window.MiAuth.postJson(url, body);
}

function initAppPage() {
  document.querySelectorAll(".meeting-source-switch").forEach((switchEl) => {
    switchEl.querySelectorAll('[data-bs-toggle="tab"]').forEach((btn) => {
      btn.addEventListener("shown.bs.tab", () => {
        switchEl.querySelectorAll(".meeting-source-switch-btn").forEach((other) => {
          const on = other === btn;
          other.classList.toggle("active", on);
          other.setAttribute("aria-selected", on ? "true" : "false");
        });
      });
    });
  });

  const platformPlaceholders = {
    google_meet: "https://meet.google.com/abc-defg-hij",
    zoom: "https://zoom.us/j/1234567890",
    teams: "https://teams.microsoft.com/l/meetup-join/…",
  };

  function syncJoinMeetingPlaceholder(form) {
    if (!form) return;
    const selected = form.querySelector('input[name="platform"]:checked');
    const urlInput = form.querySelector('input[name="meeting_url"]');
    if (!selected || !urlInput) return;
    urlInput.placeholder =
      platformPlaceholders[selected.value] || platformPlaceholders.google_meet;
  }

  document.querySelectorAll(".join-meeting-form").forEach((form) => {
    form.querySelectorAll('input[name="platform"]').forEach((radio) => {
      radio.addEventListener("change", () => syncJoinMeetingPlaceholder(form));
    });
    syncJoinMeetingPlaceholder(form);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const url = form.getAttribute("data-api-url") || "/api/meetings";
      const platform =
        (form.querySelector('input[name="platform"]:checked') || {}).value || "google_meet";
      const meetingUrl = (form.querySelector('input[name="meeting_url"]') || {}).value || "";
      const title = (form.querySelector('input[name="title"]') || {}).value || "";
      const submitBtn = form.querySelector('button[type="submit"]');

      if (!meetingUrl.trim()) {
        showToast("Please enter a meeting link.");
        return;
      }

      if (submitBtn) submitBtn.disabled = true;
      try {
        const projectSelect = form.querySelector('select[name="project_id"]');
        const projectId = projectSelect ? (projectSelect.value || "").trim() : "";
        const payload = {
          platform,
          meeting_url: meetingUrl.trim(),
          title: title.trim(),
        };
        if (projectId) payload.project_id = projectId;

        const result = await postJson(url, payload);
        const meeting = result.data || {};
        showToast(result.msg || `Bot invited to join “${meeting.title || "meeting"}”.`);
        form.reset();
        syncJoinMeetingPlaceholder(form);
      } catch (err) {
        showToast(err.message || "Unable to invite the bot. Please try again.");
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  });

  document.querySelectorAll(".create-project-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const url = form.getAttribute("data-api-url") || "/api/projects";
      const name = (form.querySelector('[name="name"]') || {}).value || "";
      const description = (form.querySelector('[name="description"]') || {}).value || "";
      const submitBtn = form.querySelector('button[type="submit"]');

      if (submitBtn) submitBtn.disabled = true;
      try {
        const result = await postJson(url, {
          name: name.trim(),
          description: description.trim(),
        });
        showToast(result.msg || "Project created.");
        form.reset();
        const modalEl = form.closest(".modal");
        if (modalEl && window.bootstrap) {
          bootstrap.Modal.getOrCreateInstance(modalEl).hide();
        }
      } catch (err) {
        showToast(err.message || "Unable to create project. Please try again.");
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  });

  document.querySelectorAll(".upload-recording-form").forEach((form) => {
    const dropzone = form.querySelector("[data-dropzone]");
    const fileInput = form.querySelector('input[type="file"][name="file"]');
    const fileLabel = form.querySelector("[data-file-label]");
    const allowedExt = [".mp4", ".webm", ".mov", ".mkv"];
    const maxBytes = Number(form.getAttribute("data-max-bytes")) || 2147483648;

    function formatBytes(bytes) {
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
      if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
      return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
    }

    function fileExtension(name) {
      const idx = String(name || "").lastIndexOf(".");
      return idx >= 0 ? String(name).slice(idx).toLowerCase() : "";
    }

    function syncFileLabel() {
      const file = fileInput && fileInput.files && fileInput.files[0];
      if (!dropzone) return;
      if (!file) {
        dropzone.classList.remove("has-file");
        if (fileLabel) {
          fileLabel.textContent = "";
          fileLabel.classList.add("d-none");
        }
        return;
      }
      dropzone.classList.add("has-file");
      if (fileLabel) {
        fileLabel.textContent = `${file.name} · ${formatBytes(file.size)}`;
        fileLabel.classList.remove("d-none");
      }
    }

    function validateFile(file) {
      if (!file) {
        showToast("Please choose a video file to upload.");
        return false;
      }
      if (!allowedExt.includes(fileExtension(file.name))) {
        showToast("Please upload an MP4, WebM, MOV, or MKV video file.");
        return false;
      }
      if (file.size > maxBytes) {
        showToast("This video is too large to upload. Please choose a smaller file.");
        return false;
      }
      return true;
    }

    if (dropzone && fileInput) {
      dropzone.addEventListener("dragover", (event) => {
        event.preventDefault();
        dropzone.classList.add("is-dragover");
      });
      dropzone.addEventListener("dragleave", () => dropzone.classList.remove("is-dragover"));
      dropzone.addEventListener("drop", (event) => {
        event.preventDefault();
        dropzone.classList.remove("is-dragover");
        const dropped = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
        if (!dropped) return;
        if (!validateFile(dropped)) return;
        const transfer = new DataTransfer();
        transfer.items.add(dropped);
        fileInput.files = transfer.files;
        syncFileLabel();
      });
      fileInput.addEventListener("change", () => {
        const file = fileInput.files && fileInput.files[0];
        if (file && !validateFile(file)) {
          fileInput.value = "";
        }
        syncFileLabel();
      });
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const url = form.getAttribute("data-api-url") || "/api/meetings/upload";
      const file = fileInput && fileInput.files && fileInput.files[0];
      const submitBtn = form.querySelector('button[type="submit"]');

      if (!validateFile(file)) return;

      const body = new FormData();
      body.append("file", file);
      const title = (form.querySelector('input[name="title"]') || {}).value || "";
      const platform = (form.querySelector('select[name="upload_platform"]') || {}).value || "";
      const projectSelect = form.querySelector('select[name="project_id"]');
      const projectId = projectSelect ? (projectSelect.value || "").trim() : "";
      if (title.trim()) body.append("title", title.trim());
      if (platform) body.append("platform", platform);
      if (projectId) body.append("project_id", projectId);

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.dataset.originalHtml = submitBtn.innerHTML;
        submitBtn.innerHTML =
          '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Uploading…';
      }

      try {
        const result = await window.MiAuth.postForm(url, body);
        const meeting = result.data || {};
        const msg = result.msg;
        showToast(msg || `Uploaded “${meeting.title || "recording"}”.`);
        form.reset();
        syncFileLabel();
      } catch (err) {
        showToast(err.message || "Unable to upload the recording. Please try again.");
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          if (submitBtn.dataset.originalHtml) {
            submitBtn.innerHTML = submitBtn.dataset.originalHtml;
          }
        }
      }
    });
  });

  document.querySelectorAll(".meeting-project-picker").forEach((select) => {
    select.addEventListener("change", async () => {
      const meetingId = select.getAttribute("data-meeting-id");
      if (!meetingId) return;

      const previous = select.getAttribute("data-previous-value") || "";
      const projectId = (select.value || "").trim();
      select.disabled = true;

      try {
        const result = await postJson(`/api/meetings/${meetingId}/project`, {
          project_id: projectId || null,
        });
        const data = result.data || {};
        select.setAttribute("data-previous-value", data.project_id || "");
        showToast(result.msg || "Project assignment updated.");

        const link = document.getElementById("meeting-project-link");
        if (link) {
          if (data.project_id) {
            link.href = `/projects/${data.project_id}`;
            link.classList.remove("d-none");
          } else {
            link.href = "#";
            link.classList.add("d-none");
          }
        }
      } catch (err) {
        select.value = previous;
        showToast(err.message || "Unable to update project assignment.");
      } finally {
        select.disabled = false;
      }
    });
  });

  document.querySelectorAll("[data-recording-fullscreen]").forEach((button) => {
    button.addEventListener("click", () => {
      const player = button.closest(".recording-card")?.querySelector(".recording-player");
      if (!player) return;
      if (player.requestFullscreen) {
        player.requestFullscreen().catch(() => showToast("Full screen is unavailable."));
      } else if (player.webkitEnterFullscreen) {
        player.webkitEnterFullscreen();
      }
    });
  });

  document.querySelectorAll(".regenerate-transcript-btn").forEach((button) => {
    if (button.dataset.miBound === "true") return;
    button.dataset.miBound = "true";
    button.addEventListener("click", async () => {
      const url = button.getAttribute("data-api-url");
      if (!url || button.disabled) return;

      button.disabled = true;
      const originalHtml = button.innerHTML;
      button.innerHTML =
        '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Queuing…';

      try {
        const result = await postJson(url, {});
        showToast(result.msg || "Recording queued to regenerate the transcript.");
        button.innerHTML = '<i class="bi bi-hourglass-split me-1"></i> Transcript queued';
        button.title = "Transcription is queued";
      } catch (err) {
        button.disabled = false;
        button.innerHTML = originalHtml;
        showToast(err.message || "Unable to regenerate the transcript. Please try again.");
      }
    });
  });

  document.querySelectorAll(".share-meeting-btn").forEach((button) => {
    if (button.dataset.miBound === "true") return;
    button.dataset.miBound = "true";
    button.addEventListener("click", async () => {
      const meetingId = button.getAttribute("data-meeting-id");
      const modalEl = document.getElementById("share-meeting-modal");
      const input = document.getElementById("share-meeting-link");
      if (!meetingId || !modalEl || !input) return;

      button.disabled = true;
      try {
        const result = await postJson(`/api/meetings/${meetingId}/share`, {});
        const url = (result.data && result.data.url) || "";
        input.value = url;
        if (window.bootstrap) {
          bootstrap.Modal.getOrCreateInstance(modalEl).show();
        }
      } catch (err) {
        showToast(err.message || "Unable to create a share link. Please try again.");
      } finally {
        button.disabled = false;
      }
    });
  });

  const copyShareBtn = document.getElementById("copy-share-link-btn");
  if (copyShareBtn && copyShareBtn.dataset.miBound !== "true") {
    copyShareBtn.dataset.miBound = "true";
    copyShareBtn.addEventListener("click", async () => {
      const input = document.getElementById("share-meeting-link");
      const url = input && input.value;
      if (!url) return;
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(url);
        } else {
          input.select();
          document.execCommand("copy");
        }
        showToast("Share link copied.");
      } catch {
        showToast("Copy the link from the box.");
      }
    });
  }

  const params = new URLSearchParams(window.location.search);
  if (params.get("shared") === "1") {
    showToast("This shared meeting was added to your workspace.");
    params.delete("shared");
    const next = `${window.location.pathname}${params.toString() ? `?${params}` : ""}${window.location.hash || ""}`;
    window.history.replaceState({}, "", next);
  }
}

document.addEventListener("DOMContentLoaded", initAppPage);
document.addEventListener("mi:page-loaded", initAppPage);
