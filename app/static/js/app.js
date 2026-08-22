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

let openMiSelect = null;

function closeMiSelect(widget) {
  const target = widget || openMiSelect;
  if (!target) return;
  target.classList.remove("is-open");
  const toggle = target.querySelector(".mi-select-toggle");
  const menu = target.querySelector(".mi-select-menu");
  if (toggle) toggle.setAttribute("aria-expanded", "false");
  if (menu) menu.hidden = true;
  if (openMiSelect === target) openMiSelect = null;
}

function closeAllMiSelects() {
  closeMiSelect();
}

function enhanceSelect(select) {
  if (!select || select.dataset.miSelectReady === "true") return;
  select.dataset.miSelectReady = "true";

  const widget = document.createElement("div");
  widget.className = "mi-select";
  if (select.classList.contains("form-select-sm")) widget.classList.add("mi-select-sm");
  if (select.classList.contains("meeting-project-picker")) widget.classList.add("mi-select-inline");

  select.parentNode.insertBefore(widget, select);
  widget.appendChild(select);

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "mi-select-toggle";
  toggle.setAttribute("aria-haspopup", "listbox");
  toggle.setAttribute("aria-expanded", "false");
  const ariaLabel = select.getAttribute("aria-label");
  if (ariaLabel) toggle.setAttribute("aria-label", ariaLabel);
  toggle.innerHTML = `<span class="mi-select-label"></span><i class="bi bi-chevron-down" aria-hidden="true"></i>`;

  const menu = document.createElement("ul");
  menu.className = "mi-select-menu";
  menu.setAttribute("role", "listbox");
  menu.hidden = true;

  widget.appendChild(toggle);
  widget.appendChild(menu);

  const labelEl = toggle.querySelector(".mi-select-label");

  function selectedText() {
    const option = select.options[select.selectedIndex];
    return option ? option.text : "";
  }

  function renderOptions() {
    menu.innerHTML = "";
    Array.from(select.options).forEach((option, index) => {
      const item = document.createElement("li");
      item.className = "mi-select-option";
      item.setAttribute("role", "option");
      item.dataset.value = option.value;
      item.dataset.index = String(index);
      if (option.disabled) item.classList.add("is-disabled");
      if (option.selected) item.classList.add("is-selected");
      item.innerHTML = `<span>${escapeHtml(option.text)}</span>${option.selected ? '<i class="bi bi-check2" aria-hidden="true"></i>' : ""}`;
      menu.appendChild(item);
    });
    labelEl.textContent = selectedText();
    toggle.disabled = select.disabled;
    widget.classList.toggle("is-disabled", select.disabled);
  }

  function positionMenu() {
    const rect = toggle.getBoundingClientRect();
    const menuHeight = Math.min(menu.scrollHeight || 240, 280);
    const spaceBelow = window.innerHeight - rect.bottom - 12;
    const openUp = spaceBelow < menuHeight && rect.top > spaceBelow;
    menu.style.position = "fixed";
    menu.style.left = `${Math.max(8, rect.left)}px`;
    menu.style.width = `${Math.max(rect.width, 168)}px`;
    menu.style.right = "auto";
    if (openUp) {
      menu.style.top = "auto";
      menu.style.bottom = `${window.innerHeight - rect.top + 6}px`;
    } else {
      menu.style.top = `${rect.bottom + 6}px`;
      menu.style.bottom = "auto";
    }
  }

  function openMenu() {
    if (select.disabled) return;
    closeAllMiSelects();
    renderOptions();
    menu.hidden = false;
    widget.classList.add("is-open");
    toggle.setAttribute("aria-expanded", "true");
    positionMenu();
    openMiSelect = widget;
  }

  function choose(value) {
    if (select.value !== value) {
      select.value = value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }
    renderOptions();
    closeMiSelect(widget);
    toggle.focus();
  }

  toggle.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (widget.classList.contains("is-open")) closeMiSelect(widget);
    else openMenu();
  });

  menu.addEventListener("click", (event) => {
    const item = event.target.closest(".mi-select-option");
    if (!item || item.classList.contains("is-disabled")) return;
    event.preventDefault();
    event.stopPropagation();
    choose(item.dataset.value);
  });

  toggle.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (!widget.classList.contains("is-open")) openMenu();
    } else if (event.key === "Escape") {
      closeMiSelect(widget);
    }
  });

  select.tabIndex = -1;
  select.addEventListener("focus", () => toggle.focus());
  select.addEventListener("change", renderOptions);
  const form = select.closest("form");
  if (form) {
    form.addEventListener("reset", () => window.setTimeout(renderOptions, 0));
  }
  new MutationObserver(renderOptions).observe(select, {
    attributes: true,
    attributeFilter: ["disabled"],
  });

  renderOptions();
}

function initCustomSelects() {
  document.querySelectorAll("select.form-select").forEach((select) => enhanceSelect(select));
}

if (!window.__miSelectListeners) {
  window.__miSelectListeners = true;
  document.addEventListener("click", (event) => {
    if (!openMiSelect) return;
    if (!openMiSelect.contains(event.target)) closeAllMiSelects();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeAllMiSelects();
  });
  window.addEventListener("resize", closeAllMiSelects);
  document.addEventListener("scroll", (event) => {
    if (openMiSelect && openMiSelect.querySelector(".mi-select-menu") === event.target) return;
    closeAllMiSelects();
  }, true);
}

function initAppPage() {
  initCustomSelects();

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
    if (select.dataset.miBound === "true") return;
    select.dataset.miBound = "true";
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
