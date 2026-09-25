"use strict";
// Server rendering is the authoritative fallback; no sensitive browser storage.
(function initializeOnboarding() {
  const form = document.querySelector("#onboarding-form");
  const loading = document.querySelector("#onboarding-loading");
  const interrupted = document.querySelector("#onboarding-interrupted");
  if (!form || !loading || !interrupted) return;

  let busy = false;
  let pending = false;
  let cancelRequested = false;
  const controls = () => Array.from(form.querySelectorAll("button, input, select, textarea"));
  const show = (el) => { el.hidden = false; el.scrollIntoView({block: "start", behavior: "instant"}); };
  const hide = (el) => { el.hidden = true; };
  // Never unlock this DOM after an uncertain write. Only fresh server HTML
  // restores controls, including their authoritative disabled attributes.
  const lockControls = () => controls().forEach((control) => { control.disabled = true; });
  const sameOrigin = (url) => new URL(url, window.location.href).origin === window.location.origin;
  const replaceWithResponse = async (response) => {
    const target = response.url || window.location.href;
    if (!sameOrigin(target)) throw new Error("cross-origin response");
    if (!(response.headers.get("Content-Type") || "").includes("text/html") || response.status >= 500) {
      throw new Error("unusable server response");
    }
    const html = await response.text();
    const parsed = new DOMParser().parseFromString(html, "text/html");
    if (!parsed.querySelector("main")) throw new Error("invalid HTML response");
    window.history.replaceState({}, "", target);
    document.documentElement.replaceWith(document.adoptNode(parsed.documentElement));
    // DOMParser scripts are inert: bind the new authoritative form explicitly.
    initializeOnboarding();
  };
  const recover = async () => {
    if (pending) return;
    busy = true;
    form.setAttribute("aria-busy", "true");
    hide(interrupted); show(loading); lockControls();
    try {
      const resumeUrl = loading.dataset.recoveryUrl;
      if (!resumeUrl || !sameOrigin(resumeUrl)) throw new Error("invalid recovery destination");
      const response = await fetch(resumeUrl, {credentials: "same-origin", cache: "no-store", headers: {"Accept": "text/html"}});
      if (!response.ok) throw new Error("readback failed");
      await replaceWithResponse(response);
    } catch (_) {
      // A failed readback is still uncertain: never unlock or permit another write.
      show(interrupted); hide(loading);
    }
  };

  form.addEventListener("submit", async (event) => {
    const submitter = event.submitter;
    if (busy) { event.preventDefault(); return; }
    if (!(submitter && submitter.formNoValidate) && !form.checkValidity()) return;

    // Snapshot while controls are still enabled, so CSRF, action and file fields survive.
    const body = new FormData(form, submitter);
    event.preventDefault();
    busy = true;
    form.setAttribute("aria-busy", "true");
    hide(interrupted); show(loading); lockControls();
    pending = true;
    try {
      const response = await fetch(form.getAttribute("action") || window.location.href, {
        method: "POST", body, credentials: "same-origin", redirect: "follow",
        headers: {"Accept": "text/html"}, cache: "no-store"
      });
      pending = false;
      if (!sameOrigin(response.url || window.location.href)) throw new Error("cross-origin response");
      if (cancelRequested) {
        await recover();
      } else if (response.redirected) {
        window.location.assign(response.url);
      } else {
        // Validation/conflict HTML is authoritative even for 200 or 409 responses.
        await replaceWithResponse(response);
      }
    } catch (_) {
      pending = false;
      // The write may have committed despite a lost response. Keep the form locked.
      hide(loading); show(interrupted);
    }
  });

  loading.querySelector("[data-loading-cancel]").addEventListener("click", (event) => {
    // Cancel stops forward navigation, not the server write. Reconcile only
    // once the original request settles; never imply that it was rolled back.
    event.preventDefault();
    cancelRequested = true;
    if (!pending) recover();
  });
  interrupted.querySelector("[data-recovery-retry]").addEventListener("click", recover);
})();
