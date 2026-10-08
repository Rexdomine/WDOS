"use strict";

// Recovery secrets move only from the URL fragment into the CSRF-protected POST body.
// They never enter a query string, response markup, browser storage, or logs.
const resetPanel = document.querySelector("[data-reset-form]");
const resetMissing = document.querySelector("[data-reset-missing]");
const resetInvalid = document.querySelector("[data-reset-invalid]");
const proof = document.getElementById("id_proof");
const fragmentValue = location.hash.length > 1 ? location.hash.slice(1) : "";
const proofPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.[A-Za-z0-9_-]+$/i;
const fragment = proofPattern.test(fragmentValue) ? fragmentValue : "";
const replacementFragment = fragmentValue && fragmentValue !== "main" && !/^id_[A-Za-z0-9_-]+$/.test(fragmentValue) ? fragmentValue : "";
if (resetPanel && proof && (fragment || replacementFragment)) {
  resetPanel.hidden = true;
  const csrf = resetPanel.querySelector('input[name="csrfmiddlewaretoken"]');
  const preserveFragment = async () => {
    if (!csrf) return false;
    const body = new URLSearchParams({
      csrfmiddlewaretoken: csrf.value,
      preserve_fragment: "1",
      proof: fragment || replacementFragment,
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
    return response;
  };
  preserveFragment().then(response => {
    proof.value = fragment;
    resetPanel.hidden = false;
    if (resetMissing) resetMissing.hidden = true;
    const flowId = response.headers.get("X-Reset-Flow") || (fragment ? fragment.split(".", 1)[0] : "");
    const next = new URL(location.href);
    next.hash = "";
    if (flowId) next.searchParams.set("reset_flow", flowId);
    history.replaceState(null, "", next.pathname + next.search);
  }).catch(error => {
    if (error.status === 400) {
      resetPanel.hidden = true;
      if (resetMissing) resetMissing.hidden = true;
      if (resetInvalid) resetInvalid.hidden = false;
      history.replaceState(null, "", location.pathname + location.search);
    }
    // Keep valid fragments intact on transport/server failures.
  });
}

for (const panel of document.querySelectorAll("[data-resend-remaining]")) {
  const initialRemaining = Number(panel.dataset.resendRemaining || "0");
  const status = panel.querySelector("[data-resend-status]");
  const button = panel.querySelector("[data-resend-button]");
  if (!status || !button) continue;
  let remaining = Math.max(0, Math.ceil(initialRemaining));
  let timer;
  const tick = () => {
    if (remaining > 0) {
      button.disabled = true;
      status.textContent = `${panel.dataset.resendWait} ${remaining}s`;
      remaining -= 1;
    } else {
      button.disabled = false;
      status.textContent = panel.dataset.resendReady;
      if (timer) window.clearInterval(timer);
    }
  };
  timer = window.setInterval(tick, 1000);
  tick();
}

function handlePasswordToggle(button) {
  const targetId = button.dataset.target || button.getAttribute("aria-controls");
  const field = targetId ? document.getElementById(targetId) : button.closest(".password-wrap")?.querySelector("input");
  if (!field) return;
  const isCurrentlyPassword = field.type === "password";
  field.type = isCurrentlyPassword ? "text" : "password";
  const showLabel = button.dataset.showLabel || "Show password";
  const hideLabel = button.dataset.hideLabel || "Hide password";
  const newLabel = isCurrentlyPassword ? hideLabel : showLabel;
  button.classList.toggle("is-visible", isCurrentlyPassword);
  button.setAttribute("aria-label", newLabel);
  button.setAttribute("title", newLabel);
  button.setAttribute("aria-pressed", String(isCurrentlyPassword));
  try {
    const len = field.value.length;
    field.setSelectionRange(len, len);
  } catch (_) {}
}

document.addEventListener("click", (event) => {
  const button = event.target.closest(".show-password");
  if (!button) return;
  event.preventDefault();
  event.stopPropagation();
  handlePasswordToggle(button);
});

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
