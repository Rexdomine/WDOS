"use strict";
// Recovery secrets never enter query strings, storage, analytics or logs.
const proof = document.getElementById("id_proof");
if (proof && location.hash.length > 1) {
  proof.value = location.hash.slice(1);
  history.replaceState(null, "", location.pathname);
}
for (const button of document.querySelectorAll(".show-password")) {
  button.addEventListener("click", () => {
    const field = document.getElementById(button.dataset.target);
    if (!field) return;
    const show = field.type === "password";
    field.type = show ? "text" : "password";
    const label = show ? (button.dataset.hideLabel || "Hide password") : (button.dataset.showLabel || "Show password");
    button.classList.toggle("is-visible", show);
    button.setAttribute("aria-label", label);
    button.setAttribute("aria-pressed", String(show));
    field.focus();
  });
}
const summary = document.querySelector(".error-summary");
if (summary) summary.focus();
const offline = document.getElementById("offline");
function networkState() { if (offline) offline.hidden = navigator.onLine; }
window.addEventListener("online", networkState);
window.addEventListener("offline", networkState);
networkState();
for (const form of document.querySelectorAll(".auth-live-form")) {
  form.addEventListener("submit", event => {
    if (!navigator.onLine) { event.preventDefault(); networkState(); return; }
    // Preserve the clicked button value (MFA setup) in native form submission.
    form.querySelector(".submit-status").textContent = form.dataset.workingLabel || "Working… Please wait.";
  });
}
