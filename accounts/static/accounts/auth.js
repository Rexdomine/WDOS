"use strict";

// Recovery secrets move only from the URL fragment into the CSRF-protected POST body.
// They never enter a query string, response markup, browser storage, or logs.
const resetPanel = document.querySelector("[data-reset-form]");
const resetMissing = document.querySelector("[data-reset-missing]");
const proof = document.getElementById("id_proof");
const fragment = location.hash.length > 1 ? location.hash.slice(1) : "";
if (resetPanel && proof && fragment) {
  const csrf = resetPanel.querySelector('input[name="csrfmiddlewaretoken"]');
  const preserveFragment = async () => {
    if (!csrf) return false;
    const body = new URLSearchParams({
      csrfmiddlewaretoken: csrf.value,
      preserve_fragment: "1",
      proof: fragment,
    });
    const response = await fetch(location.pathname, {
      method: "POST",
      credentials: "same-origin",
      headers: {"X-Requested-With": "XMLHttpRequest"},
      body,
    });
    if (!response.ok) {
      const error = new Error("Could not preserve reset proof");
      error.status = response.status;
      throw error;
    }
    return true;
  };
  preserveFragment().then(() => {
    proof.value = fragment;
    resetPanel.hidden = false;
    if (resetMissing) resetMissing.hidden = true;
    history.replaceState(null, "", location.pathname + location.search);
  }).catch(error => {
    if (error.status === 400) {
      resetPanel.hidden = true;
      if (resetMissing) resetMissing.hidden = false;
      history.replaceState(null, "", location.pathname + location.search);
    }
    // Keep valid fragments intact on transport/server failures.
  });
}

for (const panel of document.querySelectorAll("[data-resend-issued-at]")) {
  const issuedAt = Number(panel.dataset.resendIssuedAt || "0");
  const status = panel.querySelector("[data-resend-status]");
  const button = panel.querySelector("[data-resend-button]");
  if (!issuedAt || !status || !button) continue;
  let timer;
  const tick = () => {
    const remaining = Math.max(0, 60 - Math.floor(Date.now() / 1000 - issuedAt));
    if (remaining > 0) {
      button.disabled = true;
      status.textContent = `${panel.dataset.resendWait} ${remaining}s`;
    } else {
      button.disabled = false;
      status.textContent = panel.dataset.resendReady;
      if (timer) window.clearInterval(timer);
    }
  };
  timer = window.setInterval(tick, 1000);
  tick();
}

for (const button of document.querySelectorAll(".show-password")) {
  button.addEventListener("click", () => {
    const field = document.getElementById(button.dataset.target);
    if (!field) return;
    const show = field.type === "password";
    field.type = show ? "text" : "password";
    const label = show ? button.dataset.hideLabel : button.dataset.showLabel;
    button.classList.toggle("is-visible", show);
    button.setAttribute("aria-label", label);
    button.setAttribute("aria-pressed", String(show));
    field.focus();
  });
}

const summary = document.querySelector(".error-summary");
if (summary) summary.focus();

const offline = document.getElementById("offline");
function networkState() {
  if (offline) offline.hidden = navigator.onLine;
}
window.addEventListener("online", networkState);
window.addEventListener("offline", networkState);
networkState();

for (const form of document.querySelectorAll(".auth-live-form")) {
  form.addEventListener("submit", event => {
    if (!navigator.onLine) {
      event.preventDefault();
      networkState();
      return;
    }
    const status = form.querySelector(".submit-status");
    if (status) status.textContent = form.dataset.workingLabel;
  });
}
