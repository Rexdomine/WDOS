"use strict";
// Server rendering is the authoritative fallback; no sensitive browser storage.
document.querySelectorAll("form").forEach(form => form.addEventListener("submit", () => form.setAttribute("aria-busy", "true")));
