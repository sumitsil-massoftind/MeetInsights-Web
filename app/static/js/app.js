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

async function deleteJson(url) {
  return window.MiAuth.deleteJson(url);
}

let pendingDelete = null;

function hideModal(id) {
  const el = document.getElementById(id);
  if (el && window.bootstrap) {
    bootstrap.Modal.getOrCreateInstance(el).hide();
  }
  document.body.classList.remove("modal-open");
  document.body.style.removeProperty("overflow");
  document.body.style.removeProperty("padding-right");
  document.querySelectorAll(".modal-backdrop").forEach((node) => node.remove());
}

function showModal(id) {
  const el = document.getElementById(id);
  if (!el || !window.bootstrap) return;
  bootstrap.Modal.getOrCreateInstance(el).show();
}

function reloadAfterDelete(redirect) {
  const next = redirect || `${window.location.pathname}${window.location.search}`;
  if (window.MiNavigation && typeof window.MiNavigation.navigate === "function") {
    if (redirect) history.replaceState({ miSoftNavigation: true }, "", next);
    window.MiNavigation.navigate(next, { push: false });
    return;
  }
  window.location.assign(next);
}

function syncDeleteProjectConfirmLabel() {
  const btn = document.getElementById("confirm-delete-project-btn");
  const selected = document.querySelector('#delete-project-modal input[name="delete-project-meetings"]:checked');
  if (!btn) return;
  btn.textContent = selected && selected.value === "delete" ? "Delete project and meetings" : "Delete project";
}

function openDeleteMeetingModal(button) {
  pendingDelete = {
    kind: "meeting",
    id: button.getAttribute("data-meeting-id") || "",
    name: button.getAttribute("data-meeting-name") || "this meeting",
    redirect: button.getAttribute("data-redirect") || "",
  };
  const nameEl = document.getElementById("delete-meeting-name");
  if (nameEl) nameEl.textContent = pendingDelete.name;
  showModal("delete-meeting-modal");
}

function openDeleteProjectModal(button) {
  const count = Number(button.getAttribute("data-meeting-count") || "0") || 0;
  pendingDelete = {
    kind: "project",
    id: button.getAttribute("data-project-id") || "",
    name: button.getAttribute("data-project-name") || "this project",
    meetingCount: count,
    redirect: button.getAttribute("data-redirect") || "",
  };
  const nameEl = document.getElementById("delete-project-name");
  const choices = document.getElementById("delete-project-choices");
  const hint = document.getElementById("delete-project-count-hint");
  const keep = document.querySelector('#delete-project-modal input[name="delete-project-meetings"][value="keep"]');
  if (nameEl) nameEl.textContent = pendingDelete.name;
  if (keep) keep.checked = true;
  if (choices) {
    choices.hidden = count < 1;
  }
  if (hint) {
    hint.textContent =
      count === 1
        ? "This project has 1 meeting."
        : `This project has ${count} meetings.`;
  }
  syncDeleteProjectConfirmLabel();
  showModal("delete-project-modal");
}

async function confirmDeleteMeeting(button) {
  if (!pendingDelete || pendingDelete.kind !== "meeting" || !pendingDelete.id) return;
  button.disabled = true;
  const original = button.textContent;
  button.innerHTML =
    '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Deleting…';
  try {
    const result = await deleteJson(`/api/meetings/${pendingDelete.id}`);
    const redirect = pendingDelete.redirect;
    hideModal("delete-meeting-modal");
    showToast(result.msg || "Meeting deleted.");
    pendingDelete = null;
    reloadAfterDelete(redirect);
  } catch (err) {
    showToast(err.message || "Unable to delete the meeting. Please try again.");
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function confirmDeleteProject(button) {
  if (!pendingDelete || pendingDelete.kind !== "project" || !pendingDelete.id) return;
  const selected = document.querySelector('#delete-project-modal input[name="delete-project-meetings"]:checked');
  const deleteMeetings = pendingDelete.meetingCount > 0 && selected && selected.value === "delete";
  button.disabled = true;
  const original = button.textContent;
  button.innerHTML =
    '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Deleting…';
  try {
    const qs = deleteMeetings ? "?delete_meetings=true" : "?delete_meetings=false";
    const result = await deleteJson(`/api/projects/${pendingDelete.id}${qs}`);
    const redirect = pendingDelete.redirect;
    hideModal("delete-project-modal");
    showToast(result.msg || "Project deleted.");
    pendingDelete = null;
    reloadAfterDelete(redirect);
  } catch (err) {
    showToast(err.message || "Unable to delete the project. Please try again.");
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

if (!window.__miDeleteListeners) {
  window.__miDeleteListeners = true;
  document.addEventListener("click", (event) => {
    const meetingBtn = event.target.closest("[data-delete-meeting]");
    if (meetingBtn) {
      event.preventDefault();
      openDeleteMeetingModal(meetingBtn);
      return;
    }
    const projectBtn = event.target.closest("[data-delete-project]");
    if (projectBtn) {
      event.preventDefault();
      openDeleteProjectModal(projectBtn);
    }
  });
  document.addEventListener("change", (event) => {
    if (event.target && event.target.name === "delete-project-meetings") {
      syncDeleteProjectConfirmLabel();
    }
  });
  document.addEventListener("click", (event) => {
    if (event.target.closest("#confirm-delete-meeting-btn")) {
      confirmDeleteMeeting(event.target.closest("#confirm-delete-meeting-btn"));
    }
    if (event.target.closest("#confirm-delete-project-btn")) {
      confirmDeleteProject(event.target.closest("#confirm-delete-project-btn"));
    }
  });
}

function closeTitleEditor(editor, restore) {
  if (!editor) return;
  const form = editor.querySelector(".meeting-title-form");
  const view = editor.querySelector(".meeting-title-view");
  const input = editor.querySelector(".meeting-title-input");
  if (restore && input) input.value = editor.getAttribute("data-meeting-title") || "";
  if (form) form.hidden = true;
  if (view) view.hidden = false;
}

function openTitleEditor(editor) {
  document.querySelectorAll(".meeting-title-editor").forEach((other) => {
    if (other !== editor) closeTitleEditor(other, true);
  });
  const form = editor.querySelector(".meeting-title-form");
  const view = editor.querySelector(".meeting-title-view");
  const input = editor.querySelector(".meeting-title-input");
  if (view) view.hidden = true;
  if (form) form.hidden = false;
  if (input) {
    input.value = editor.getAttribute("data-meeting-title") || "";
    input.focus();
    input.select();
  }
}

function applyMeetingTitle(editor, title) {
  const meetingId = editor.getAttribute("data-meeting-id") || "";
  editor.setAttribute("data-meeting-title", title);
  const text = editor.querySelector(".meeting-title-text");
  if (text) text.textContent = title;
  const input = editor.querySelector(".meeting-title-input");
  if (input) input.value = title;
  const editBtn = editor.querySelector(".meeting-title-edit-btn");
  if (editBtn) editBtn.setAttribute("aria-label", `Rename ${title}`);

  document.querySelectorAll(`[data-delete-meeting][data-meeting-id="${meetingId}"]`).forEach((btn) => {
    btn.setAttribute("data-meeting-name", title);
    const aria = btn.getAttribute("aria-label");
    if (aria) btn.setAttribute("aria-label", `Delete ${title}`);
  });

  const crumb = document.querySelector(".meeting-detail-header .breadcrumb-item.active");
  if (crumb) crumb.textContent = title;
  const recordingTitle = document.querySelector(".recording-title");
  if (recordingTitle) recordingTitle.textContent = title;
  if (document.querySelector(".meeting-detail") && title) {
    document.title = `${title} · Meet Insights`;
  }
}

async function saveMeetingTitle(editor) {
  const meetingId = editor.getAttribute("data-meeting-id");
  const input = editor.querySelector(".meeting-title-input");
  const submitBtn = editor.querySelector('.meeting-title-form button[type="submit"]');
  if (!meetingId || !input) return;

  const title = (input.value || "").trim();
  const previous = editor.getAttribute("data-meeting-title") || "";
  if (!title) {
    showToast("Please enter a meeting name.");
    input.focus();
    return;
  }
  if (title === previous) {
    closeTitleEditor(editor, false);
    return;
  }

  input.disabled = true;
  if (submitBtn) submitBtn.disabled = true;
  try {
    const result = await postJson(`/api/meetings/${meetingId}/title`, { title });
    const next = (result.data && result.data.title) || title;
    applyMeetingTitle(editor, next);
    closeTitleEditor(editor, false);
    showToast(result.msg || "Meeting name updated.");
  } catch (err) {
    input.value = previous;
    showToast(err.message || "Unable to rename the meeting. Please try again.");
  } finally {
    input.disabled = false;
    if (submitBtn) submitBtn.disabled = false;
  }
}

if (!window.__miTitleEditListeners) {
  window.__miTitleEditListeners = true;
  document.addEventListener("click", (event) => {
    const editBtn = event.target.closest(".meeting-title-edit-btn");
    if (editBtn) {
      event.preventDefault();
      const editor = editBtn.closest(".meeting-title-editor");
      if (editor) openTitleEditor(editor);
      return;
    }
    const cancelBtn = event.target.closest(".meeting-title-cancel");
    if (cancelBtn) {
      event.preventDefault();
      const editor = cancelBtn.closest(".meeting-title-editor");
      closeTitleEditor(editor, true);
    }
  });
  document.addEventListener("submit", (event) => {
    const form = event.target.closest(".meeting-title-form");
    if (!form) return;
    event.preventDefault();
    const editor = form.closest(".meeting-title-editor");
    if (editor) saveMeetingTitle(editor);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const editor = event.target.closest && event.target.closest(".meeting-title-editor");
    if (editor) closeTitleEditor(editor, true);
  });
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
