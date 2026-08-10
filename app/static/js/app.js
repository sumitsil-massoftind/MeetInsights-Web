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
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    credentials: "same-origin",
    body: JSON.stringify(body),
  });

  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  const envelope = payload && payload.response ? payload.response : null;
  const status = envelope && envelope.status ? envelope.status : null;
  const data = envelope && envelope.data != null ? envelope.data : {};
  const msg =
    (status && status.msg) ||
    (payload && (payload.detail || payload.message)) ||
    "Something went wrong. Please try again.";
  const ok =
    response.ok &&
    (status ? status.action_status !== false : true);

  if (!ok) {
    const err = new Error(typeof msg === "string" ? msg : "Request failed.");
    err.status = response.status;
    err.data = data;
    err.payload = payload;
    throw err;
  }

  return { data, msg, status, payload };
}

document.addEventListener("DOMContentLoaded", () => {
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
        if (window.location.pathname === "/meetings" || window.location.pathname === "/dashboard") {
          window.setTimeout(() => window.location.reload(), 600);
        }
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
        window.setTimeout(() => window.location.reload(), 400);
      } catch (err) {
        showToast(err.message || "Unable to create project. Please try again.");
      } finally {
        if (submitBtn) submitBtn.disabled = false;
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
});
