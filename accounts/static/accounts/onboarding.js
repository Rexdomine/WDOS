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
    initializeProfileMenus();
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


function initializeProfileMenus() {
  document.querySelectorAll('[data-profile-menu]').forEach((menu) => {
    const trigger = menu.querySelector('[data-profile-trigger]'); const panel = menu.querySelector('[data-profile-panel]');
    if (!trigger || !panel) return;
    const close = () => { panel.hidden = true; trigger.setAttribute('aria-expanded', 'false'); };
    trigger.addEventListener('click', () => { panel.hidden = !panel.hidden; trigger.setAttribute('aria-expanded', String(!panel.hidden)); if (!panel.hidden) panel.querySelector('button')?.focus(); });
    menu.addEventListener('keydown', (event) => { if (event.key === 'Escape') { close(); trigger.focus(); } });
    document.addEventListener('click', (event) => { if (!menu.contains(event.target)) close(); });
  });
}
function initializeRecordTabs() {
  const tabs = Array.from(document.querySelectorAll('[data-record-tab]'));
  if (!tabs.length) return;
  const panels = tabs.map((tab) => document.getElementById(tab.getAttribute('aria-controls'))).filter(Boolean);
  const namedPanels = Array.from(document.querySelectorAll('[data-workspace-panel]'));
  const syncWorkspaceNavigation = (stateId) => {
    document.querySelectorAll('.foundation-shell .navitem, .foundation-shell .mobile-nav a').forEach((link) => {
      const active = link.getAttribute('href') === `#${stateId}`;
      link.classList.toggle('active', link.classList.contains('navitem') && active);
      if (active) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
  };
  const hideNamedPanels = () => namedPanels.forEach((panel) => { panel.hidden = true; });
  const activate = (tab, moveFocus = false) => {
    tabs.forEach((candidate) => {
      const selected = candidate === tab;
      candidate.classList.toggle('active', selected);
      candidate.setAttribute('aria-selected', String(selected));
      candidate.tabIndex = selected ? 0 : -1;
    });
    panels.forEach((panel) => {
      // The approved Overview composition keeps related information beside the
      // workspace record; only the primary overview/history panels are exclusive.
      panel.hidden = panel.id === 'records-panel' ? false : panel.id !== tab.getAttribute('aria-controls');
    });
    hideNamedPanels();
    syncWorkspaceNavigation(tab.getAttribute('aria-controls') === 'overview-panel' ? 'workspace-home' : tab.getAttribute('aria-controls'));
    if (moveFocus) tab.focus();
  };
  const activateNamedPanel = (panel) => {
    panels.forEach((candidate) => { candidate.hidden = true; });
    hideNamedPanels();
    panel.hidden = false;
    syncWorkspaceNavigation(panel.id);
    tabs.forEach((candidate) => {
      candidate.classList.remove('active');
      candidate.setAttribute('aria-selected', 'false');
      candidate.tabIndex = -1;
    });
    // Keep the visible record tablist in the document's sequential tab order
    // while a named workspace panel is active.
    tabs[0].tabIndex = 0;
  };
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', (event) => { event.preventDefault(); activate(tab); window.history.replaceState({}, '', tab.hash); });
    tab.addEventListener('keydown', (event) => {
      if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      activate(tabs[next], true);
      window.history.replaceState({}, '', tabs[next].hash);
    });
  });
  const activateHash = () => {
    const tab = tabs.find((candidate) => candidate.hash === window.location.hash);
    if (tab) activate(tab);
    else if (window.location.hash === '#workspace-home') activate(tabs[0]);
    else {
      const panel = namedPanels.find((candidate) => `#${candidate.id}` === window.location.hash);
      if (panel) activateNamedPanel(panel);
    }
  };
  document.querySelectorAll('[data-record-target]').forEach((shortcut) => {
    shortcut.addEventListener('click', (event) => {
      const tab = tabs.find((candidate) => candidate.getAttribute('aria-controls') === shortcut.dataset.recordTarget);
      if (!tab) return;
      event.preventDefault();
      activate(tab);
      window.history.replaceState({}, '', shortcut.hash);
    });
  });
  document.querySelectorAll('[data-workspace-target]').forEach((shortcut) => {
    shortcut.addEventListener('click', (event) => {
      const panel = document.getElementById(shortcut.dataset.workspaceTarget);
      if (!panel) return;
      event.preventDefault();
      activateNamedPanel(panel);
      window.history.replaceState({}, '', shortcut.hash);
    });
  });
  window.addEventListener("hashchange", activateHash);
  const initialTab = tabs.find((tab) => tab.hash === window.location.hash) || tabs[0];
  const initialNamedPanel = namedPanels.find((panel) => `#${panel.id}` === window.location.hash);
  if (initialNamedPanel) activateNamedPanel(initialNamedPanel);
  else if (window.location.hash === '#workspace-home') activate(tabs[0]);
  else activate(initialTab);
}

initializeProfileMenus();
initializeRecordTabs();
