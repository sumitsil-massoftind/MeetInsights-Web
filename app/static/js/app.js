/* Global UI helpers — no business logic */

document.addEventListener("DOMContentLoaded", () => {
  // Auto-dismiss toasts injected by HTMX
  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (event.target && event.target.id === "toast-host") {
      setTimeout(() => {
        const toastEl = event.target.querySelector(".toast");
        if (toastEl && window.bootstrap) {
          const toast = bootstrap.Toast.getOrCreateInstance(toastEl);
          toast.show();
        }
      }, 10);
    }
  });

  // Reset join-meeting form after successful mock submit
  document.body.addEventListener("htmx:afterRequest", (event) => {
    const form = event.target;
    if (
      form &&
      form.matches &&
      form.matches(".join-meeting-form") &&
      event.detail &&
      event.detail.successful
    ) {
      form.reset();
      syncJoinMeetingPlaceholder(form);
    }
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
  });

  // OTP focus hopping (legacy)
  const otpInputs = document.querySelectorAll(".otp-inputs input");
  otpInputs.forEach((input, index) => {
    input.addEventListener("input", () => {
      input.value = input.value.replace(/\D/g, "").slice(0, 1);
      if (input.value && otpInputs[index + 1]) {
        otpInputs[index + 1].focus();
      }
      syncOtpHidden();
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Backspace" && !input.value && otpInputs[index - 1]) {
        otpInputs[index - 1].focus();
      }
    });
  });

  function syncOtpHidden() {
    const hidden = document.getElementById("otp-value");
    if (!hidden) return;
    hidden.value = Array.from(otpInputs)
      .map((i) => i.value)
      .join("");
  }
});
