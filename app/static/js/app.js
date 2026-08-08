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

  // OTP focus hopping
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
