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
  const lockControls = () => {
    controls().forEach((control) => { control.disabled = true; });
    document.querySelectorAll(".searchable-select.is-open").forEach((el) => {
      if (el._searchableInstance) el._searchableInstance.close();
    });
  };
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
    initializePhotoControls();
    initializeGeographyDropdowns();
    initializeEligibilityWatcher();
    initializeSearchableDropdowns();
    initializeRecordTabs();
  };
  const recover = async () => {
    if (pending) return;
    pending = true;
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
    } finally {
      pending = false;
    }
  };

  let activeSubmitter = null;
  form.querySelectorAll('button[type="submit"], button:not([type])').forEach((btn) => {
    btn.addEventListener("click", (e) => {
      if (busy) {
        e.preventDefault();
        e.stopImmediatePropagation();
        return;
      }
      activeSubmitter = btn;
    });
  });

  form.addEventListener("submit", async (event) => {
    const submitter = event.submitter || activeSubmitter;
    if (busy) { event.preventDefault(); return; }
    if (!(submitter && submitter.formNoValidate) && !form.checkValidity()) return;

    // Snapshot while controls are still enabled, so CSRF, action and file fields survive.
    const body = new FormData(form, submitter);
    event.preventDefault();
    busy = true;
    form.setAttribute("aria-busy", "true");
    if (submitter) {
      submitter.setAttribute("aria-busy", "true");
      submitter.setAttribute("data-loading", "true");
      submitter.classList.add("is-loading");
    }
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
    if (menu._profileInitialized) return;
    menu._profileInitialized = true;
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
  if (tabs[0]._tabsInitialized) return;
  tabs[0]._tabsInitialized = true;
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
  document.querySelectorAll('.foundation-shell a[href="#workspace-home"]').forEach((link) => {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      activate(tabs[0]);
      window.history.replaceState({}, '', '#workspace-home');
    });
  });
  window.addEventListener("hashchange", activateHash);
  const initialTab = tabs.find((tab) => tab.hash === window.location.hash) || tabs[0];
  const initialNamedPanel = namedPanels.find((panel) => `#${panel.id}` === window.location.hash);
  if (initialNamedPanel) activateNamedPanel(initialNamedPanel);
  else if (window.location.hash === '#workspace-home') activate(tabs[0]);
  else activate(initialTab);
}

function initializePhotoControls() {
  document.querySelectorAll('.photo-control').forEach((control) => {
    if (control._photoInitialized) return;
    control._photoInitialized = true;
    const input = control.querySelector('input[type="file"]');
    const preview = control.querySelector('[data-photo-preview]');
    const nameLabel = control.querySelector('[data-photo-name]');
    if (!input || !nameLabel) return;

    input.addEventListener('change', () => {
      const file = input.files && input.files[0];
      if (file) {
        nameLabel.textContent = file.name;
        if (preview && file.type.startsWith('image/')) {
          try {
            preview.src = URL.createObjectURL(file);
            preview.hidden = false;
          } catch (_) {}
        }
      } else {
        nameLabel.textContent = control.getAttribute('data-default-label') || 'Choose a photo';
        if (preview && !preview.getAttribute('data-saved-src')) {
          preview.hidden = true;
          preview.src = '';
        } else if (preview && preview.getAttribute('data-saved-src')) {
          preview.src = preview.getAttribute('data-saved-src');
        }
      }
    });
  });
}

function createSearchableSelect(nativeSelect, defaultPlaceholder) {
  if (!nativeSelect) return null;

  const parent = nativeSelect.parentElement;
  const existingWrapper = parent ? parent.querySelector(`.searchable-select[data-for="${nativeSelect.id}"]`) : null;
  if (existingWrapper) {
    existingWrapper.remove();
  }

  nativeSelect.classList.add("searchable-select-native");
  nativeSelect.tabIndex = -1;
  nativeSelect.setAttribute("aria-hidden", "true");

  const wrapper = document.createElement("div");
  wrapper.className = "searchable-select";
  wrapper.setAttribute("data-for", nativeSelect.id);

  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "searchable-select-trigger";
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");
  trigger.setAttribute("id", `trigger_${nativeSelect.id}`);

  const labelSpan = document.createElement("span");
  labelSpan.className = "searchable-select-label";

  const chevronSpan = document.createElement("span");
  chevronSpan.className = "searchable-select-chevron";
  chevronSpan.setAttribute("aria-hidden", "true");
  chevronSpan.innerHTML = '<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>';

  trigger.appendChild(labelSpan);
  trigger.appendChild(chevronSpan);
  wrapper.appendChild(trigger);

  const dropdown = document.createElement("div");
  dropdown.className = "searchable-select-dropdown";
  dropdown.hidden = true;
  dropdown.setAttribute("role", "listbox");
  dropdown.setAttribute("aria-labelledby", trigger.id);

  const searchWrap = document.createElement("div");
  searchWrap.className = "searchable-select-search-wrap";

  const searchIcon = document.createElement("span");
  searchIcon.className = "searchable-select-search-icon";
  searchIcon.setAttribute("aria-hidden", "true");
  searchIcon.innerHTML = '<svg viewBox="0 0 24 24"><path d="M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14 M15 15l6 6"/></svg>';

  const searchInput = document.createElement("input");
  searchInput.type = "text";
  searchInput.className = "searchable-select-search-input";
  searchInput.placeholder = "Type to search...";
  searchInput.setAttribute("aria-label", "Search options");
  searchInput.autocomplete = "off";
  searchInput.spellcheck = false;

  const clearBtn = document.createElement("button");
  clearBtn.type = "button";
  clearBtn.className = "searchable-select-clear-search";
  clearBtn.setAttribute("aria-label", "Clear search");
  clearBtn.innerHTML = "&times;";
  clearBtn.hidden = true;

  searchWrap.appendChild(searchIcon);
  searchWrap.appendChild(searchInput);
  searchWrap.appendChild(clearBtn);
  dropdown.appendChild(searchWrap);

  const optionsList = document.createElement("div");
  optionsList.className = "searchable-select-options";
  optionsList.tabIndex = -1;
  dropdown.appendChild(optionsList);

  wrapper.appendChild(dropdown);
  nativeSelect.after(wrapper);

  const fieldLabel = (parent ? parent.querySelector(`label[for="${nativeSelect.id}"]`) : null) || document.querySelector(`label[for="${nativeSelect.id}"]`);
  if (fieldLabel) {
    fieldLabel.addEventListener("click", (e) => {
      e.preventDefault();
      trigger.focus();
      toggle();
    });
  }

  let focusedIndex = -1;

  function isOpen() {
    return !dropdown.hidden;
  }

  function open() {
    document.querySelectorAll(".searchable-select.is-open").forEach((el) => {
      if (el !== wrapper && el._searchableInstance) {
        el._searchableInstance.close();
      }
    });

    if (nativeSelect.disabled) return;

    dropdown.hidden = false;
    wrapper.classList.add("is-open");
    trigger.setAttribute("aria-expanded", "true");
    searchInput.value = "";
    clearBtn.hidden = true;
    renderOptions("");

    setTimeout(() => {
      searchInput.focus();
      const selectedEl = optionsList.querySelector(".is-selected");
      if (selectedEl) {
        selectedEl.scrollIntoView({ block: "nearest" });
      }
    }, 10);
  }

  function close() {
    if (dropdown.hidden) return;
    dropdown.hidden = true;
    wrapper.classList.remove("is-open");
    trigger.setAttribute("aria-expanded", "false");
    focusedIndex = -1;
  }

  function toggle() {
    if (isOpen()) close();
    else open();
  }

  function syncFromNative() {
    trigger.disabled = nativeSelect.disabled;
    const selectedOpt = nativeSelect.selectedOptions && nativeSelect.selectedOptions[0];
    const text = selectedOpt ? selectedOpt.textContent.trim() : "";
    const val = selectedOpt ? selectedOpt.value : "";

    if (val && text && text !== "—" && !text.toLowerCase().startsWith("select ")) {
      labelSpan.textContent = text;
      labelSpan.classList.remove("is-placeholder");
    } else {
      labelSpan.textContent = defaultPlaceholder || text || "Select";
      labelSpan.classList.add("is-placeholder");
    }

    if (isOpen()) {
      renderOptions(searchInput.value);
    }
  }

  function selectOption(val, text) {
    nativeSelect.value = val;
    nativeSelect.dispatchEvent(new Event("change", { bubbles: true }));
    nativeSelect.dispatchEvent(new Event("input", { bubbles: true }));
    syncFromNative();
    close();
    trigger.focus();
  }

  function renderOptions(query) {
    optionsList.innerHTML = "";
    focusedIndex = -1;
    const cleanQuery = (query || "").trim().toLowerCase();

    const rawOptions = Array.from(nativeSelect.options);
    const filtered = rawOptions.filter((opt) => {
      if (opt.value === "") return false;
      return opt.textContent.toLowerCase().includes(cleanQuery);
    });

    if (filtered.length === 0) {
      const empty = document.createElement("div");
      empty.className = "searchable-select-empty";
      empty.textContent = "No results found";
      optionsList.appendChild(empty);
      return;
    }

    filtered.forEach((opt, idx) => {
      const item = document.createElement("div");
      item.className = "searchable-select-option";
      item.setAttribute("role", "option");
      item.setAttribute("data-value", opt.value);
      item.setAttribute("data-index", String(idx));

      const isSel = opt.selected || opt.value === nativeSelect.value;
      if (isSel) {
        item.classList.add("is-selected");
        item.setAttribute("aria-selected", "true");
      } else {
        item.setAttribute("aria-selected", "false");
      }

      const textSpan = document.createElement("span");
      textSpan.textContent = opt.textContent;
      item.appendChild(textSpan);

      if (isSel && opt.value !== "") {
        const check = document.createElement("span");
        check.className = "searchable-select-option-check";
        check.setAttribute("aria-hidden", "true");
        check.innerHTML = '<svg viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg>';
        item.appendChild(check);
      }

      item.addEventListener("mousedown", (e) => {
        e.preventDefault();
      });

      item.addEventListener("click", () => {
        selectOption(opt.value, opt.textContent);
      });

      optionsList.appendChild(item);
    });
  }

  function updateHighlight(items) {
    items.forEach((it, i) => {
      if (i === focusedIndex) {
        it.classList.add("is-focused");
        it.scrollIntoView({ block: "nearest" });
      } else {
        it.classList.remove("is-focused");
      }
    });
  }

  trigger.addEventListener("click", (e) => {
    e.preventDefault();
    toggle();
  });

  trigger.addEventListener("keydown", (e) => {
    if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) {
      e.preventDefault();
      open();
    }
  });

  searchInput.addEventListener("input", () => {
    clearBtn.hidden = !searchInput.value;
    renderOptions(searchInput.value);
  });

  clearBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    searchInput.value = "";
    clearBtn.hidden = true;
    renderOptions("");
    searchInput.focus();
  });

  searchInput.addEventListener("keydown", (e) => {
    const items = optionsList.querySelectorAll(".searchable-select-option");
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (items.length > 0) {
        focusedIndex = (focusedIndex + 1) % items.length;
        updateHighlight(items);
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (items.length > 0) {
        focusedIndex = (focusedIndex - 1 + items.length) % items.length;
        updateHighlight(items);
      }
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (focusedIndex >= 0 && items[focusedIndex]) {
        items[focusedIndex].click();
      } else if (items.length === 1) {
        items[0].click();
      } else {
        const firstNonEmpty = Array.from(items).find((it) => it.getAttribute("data-value") !== "");
        if (firstNonEmpty) firstNonEmpty.click();
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
      trigger.focus();
    } else if (e.key === "Tab") {
      close();
    }
  });

  document.addEventListener("click", (e) => {
    if (!wrapper.contains(e.target) && (!fieldLabel || !fieldLabel.contains(e.target))) {
      close();
    }
  });

  nativeSelect.addEventListener("change", syncFromNative);
  nativeSelect.addEventListener("invalid", (e) => {
    e.preventDefault();
    open();
  });

  wrapper._searchableInstance = {
    open,
    close,
    toggle,
    syncFromNative,
  };

  syncFromNative();
  return wrapper._searchableInstance;
}

function initializeGeographyDropdowns() {
  const geoScript = document.getElementById("geo-data");
  if (!geoScript) return;

  let parsedData = null;
  try {
    parsedData = JSON.parse(geoScript.textContent);
  } catch (_) {
    return;
  }
  if (!parsedData) return;

  const countrySelect = document.getElementById("id_country");
  const regionSelect = document.getElementById("id_region");
  const districtSelect = document.getElementById("id_district");
  const localHomeInput = document.getElementById("id_local_home");
  const timezoneInput = document.getElementById("id_timezone");
  const timezoneOverrideInput = document.getElementById("id_timezone_override");
  const regionLabel = document.querySelector('label[for="id_region"]');
  const districtLabel = document.querySelector('label[for="id_district"]');

  if (!countrySelect || !regionSelect) return;

  const countriesList = parsedData.countries || [];
  const nigeriaDistricts = parsedData.nigeria_districts || {};
  const homesList = Array.isArray(parsedData) ? parsedData : (parsedData.homes || []);
  const countryTimezones = parsedData.country_timezones || {};
  const multiTimezoneCountries = parsedData.multi_timezone_countries || {};

  const countryPlaceholder = "Select country";
  const regionPlaceholder = "Select state";
  const districtPlaceholder = "Select LGA";

  const countryCustom = createSearchableSelect(countrySelect, countryPlaceholder);
  const regionCustom = createSearchableSelect(regionSelect, regionPlaceholder);
  const districtCustom = districtSelect ? createSearchableSelect(districtSelect, districtPlaceholder) : null;

  function getCountryRecord(countryVal) {
    if (!countryVal) return null;
    const lower = countryVal.toLowerCase();
    return countriesList.find((c) => c.name.toLowerCase() === lower || c.code.toLowerCase() === lower) || null;
  }

  function updateFieldLabels(countryRecord) {
    if (regionLabel) {
      regionLabel.textContent = countryRecord && countryRecord.admin_label
        ? countryRecord.admin_label
        : "State / Region / Province";
    }
    if (districtLabel) {
      districtLabel.textContent = countryRecord && countryRecord.local_label
        ? countryRecord.local_label
        : "Local government / District";
    }
  }

  function populateSelect(select, values, preferredValue, emptyPlaceholder) {
    const prevValue = preferredValue !== undefined ? preferredValue : select.value;
    select.innerHTML = "";
    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = emptyPlaceholder !== undefined ? emptyPlaceholder : "Select";
    select.appendChild(defaultOption);

    let found = false;
    values.forEach((val) => {
      const option = document.createElement("option");
      option.value = val;
      option.textContent = val;
      if (val === prevValue) {
        option.selected = true;
        found = true;
      }
      select.appendChild(option);
    });

    if (!found && prevValue && !values.includes(prevValue)) {
      select.value = "";
    }
  }

  function updateRegions(preserveSelected) {
    const selectedCountry = countrySelect.value;
    const countryRecord = getCountryRecord(selectedCountry);
    updateFieldLabels(countryRecord);

    const currentRegion = preserveSelected ? regionSelect.value : "";

    if (!selectedCountry) {
      populateSelect(regionSelect, [], "", "Select state");
      if (regionCustom) regionCustom.syncFromNative();
      if (districtSelect) {
        populateSelect(districtSelect, [], "", "Select LGA");
        if (districtCustom) districtCustom.syncFromNative();
      }
      updateLocalHome(true);
      return;
    }

    let matchingRegions = [];
    if (countryRecord && countryRecord.regions && countryRecord.regions.length > 0) {
      matchingRegions = countryRecord.regions.map((r) => r.name);
    } else {
      matchingRegions = Array.from(
        new Set(
          homesList
            .filter((h) => !selectedCountry || h.country === selectedCountry || h.country === "NG" || h.country === "Nigeria")
            .map((h) => h.region)
            .filter(Boolean)
        )
      ).sort();
    }

    if (currentRegion && !matchingRegions.includes(currentRegion)) {
      matchingRegions.push(currentRegion);
      matchingRegions.sort();
    }

    if (matchingRegions.length === 0) {
      populateSelect(regionSelect, [], "", "— No administrative divisions available —");
    } else {
      populateSelect(regionSelect, matchingRegions, currentRegion, "Select state");
    }

    if (regionCustom) regionCustom.syncFromNative();
    updateDistricts(preserveSelected);
  }

  function updateDistricts(preserveSelected) {
    if (!districtSelect) return;
    const selectedCountry = countrySelect.value;
    const selectedRegion = regionSelect.value;
    const currentDistrict = preserveSelected ? districtSelect.value : "";

    if (!selectedRegion) {
      populateSelect(districtSelect, [], "", "Select LGA");
      if (districtCustom) districtCustom.syncFromNative();
      updateLocalHome();
      return;
    }

    let matchingDistricts = [];
    if (selectedCountry && (selectedCountry.toLowerCase() === "nigeria" || selectedCountry.toUpperCase() === "NG") && (nigeriaDistricts[selectedRegion] || nigeriaDistricts[selectedRegion.replace(/ State$/i, "")])) {
      matchingDistricts = nigeriaDistricts[selectedRegion] || nigeriaDistricts[selectedRegion.replace(/ State$/i, "")];
    }

    const homeDistricts = homesList
      .filter(
        (h) =>
          (!selectedCountry || h.country === selectedCountry || h.country === "NG" || h.country === "Nigeria") &&
          (!selectedRegion || h.region === selectedRegion)
      )
      .map((h) => h.district)
      .filter(Boolean);

    const allDistricts = Array.from(new Set([...matchingDistricts, ...homeDistricts])).sort();

    if (currentDistrict && !allDistricts.includes(currentDistrict)) {
      allDistricts.push(currentDistrict);
      allDistricts.sort();
    }

    if (allDistricts.length === 0) {
      if (currentDistrict) {
        populateSelect(districtSelect, [currentDistrict], currentDistrict, "Select LGA");
      } else {
        populateSelect(districtSelect, [], "", "— None available —");
      }
    } else {
      populateSelect(districtSelect, allDistricts, currentDistrict, "Select LGA");
    }

    if (districtCustom) districtCustom.syncFromNative();
    updateLocalHome();
  }

  function updateLocalHome() {
    if (!localHomeInput) return;
    const selectedCountry = countrySelect.value;
    const selectedRegion = regionSelect.value;
    const selectedDistrict = districtSelect ? districtSelect.value : "";

    const matched = homesList.find(
      (h) =>
        h.country === selectedCountry &&
        h.region === selectedRegion &&
        (!selectedDistrict || h.district === selectedDistrict)
    );

    if (matched && matched.label) {
      localHomeInput.value = matched.label;
    } else {
      localHomeInput.value = "Pending assignment";
    }
  }

  function updateTimezone() {
    if (!timezoneInput) return;
    if (timezoneOverrideInput && (timezoneOverrideInput.value === "true" || timezoneOverrideInput.value === "True")) {
      return;
    }
    const selectedCountry = countrySelect.value;
    if (!selectedCountry) return;
    const countryRecord = getCountryRecord(selectedCountry);
    const code = countryRecord ? countryRecord.code.toUpperCase() : selectedCountry.toUpperCase();
    const selectedRegion = regionSelect.value;

    if (multiTimezoneCountries && (multiTimezoneCountries[code] || multiTimezoneCountries[selectedCountry])) {
      const multiCfg = multiTimezoneCountries[code] || multiTimezoneCountries[selectedCountry];
      if (selectedRegion && multiCfg.region_timezones) {
        const regTz = multiCfg.region_timezones[selectedRegion];
        if (regTz) {
          timezoneInput.value = regTz;
          return;
        }
        const lowerReg = selectedRegion.toLowerCase();
        for (const [k, tz] of Object.entries(multiCfg.region_timezones)) {
          if (k.toLowerCase() === lowerReg) {
            timezoneInput.value = tz;
            return;
          }
        }
      }
      timezoneInput.value = multiCfg.default || "Africa/Kinshasa";
      return;
    }

    const defaultTz = countryTimezones[selectedCountry] || countryTimezones[code] || (countryRecord && countryTimezones[countryRecord.name]);
    if (defaultTz) {
      timezoneInput.value = defaultTz;
    }
  }

  countrySelect.addEventListener("change", () => {
    updateRegions(false);
    updateTimezone();
  });

  regionSelect.addEventListener("change", () => {
    updateDistricts(false);
    updateTimezone();
  });

  if (districtSelect) {
    districtSelect.addEventListener("change", () => {
      updateLocalHome();
    });
  }

  if (countryCustom) countryCustom.syncFromNative();
  updateRegions(true);
  if (timezoneInput && !timezoneInput.value) {
    updateTimezone();
  }
}

function initializeEligibilityWatcher() {
  const elScript = document.getElementById("eligibility-data");
  const elSelect = document.getElementById("id_eligibility");
  const basisInput = document.getElementById("id_verification_basis");
  if (!elScript || !elSelect || !basisInput) return;

  let elList = [];
  try {
    elList = JSON.parse(elScript.textContent);
  } catch (_) {
    return;
  }

  function updateBasis() {
    const val = elSelect.value;
    const match = elList.find((r) => r.code === val);
    if (match) {
      if (match.basis) {
        basisInput.value = match.basis;
      }
      const netSelect = document.getElementById("id_network");
      if (netSelect && match.network) {
        netSelect.value = match.network;
        netSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
    } else {
      basisInput.value = "Pending review";
    }
  }

  elSelect.addEventListener("change", updateBasis);
  if (elSelect.value) {
    updateBasis();
  }
}

function initializeSearchableDropdowns() {
  const form = document.getElementById("onboarding-form");
  const selects = form ? form.querySelectorAll("select") : document.querySelectorAll(".fields select");
  selects.forEach((sel) => {
    if (sel.classList.contains("searchable-select-native")) return;

    let placeholder = "Select";
    const labelEl = (sel.parentElement ? sel.parentElement.querySelector(`label[for="${sel.id}"]`) : null) || document.querySelector(`label[for="${sel.id}"]`);
    if (labelEl) {
      const cleanLabel = labelEl.textContent.replace(/\[🔒.*\]/g, "").replace(/\*/g, "").trim();
      if (cleanLabel) {
        placeholder = `Select ${cleanLabel.toLowerCase()}`;
      }
    }

    const placeholderMap = {
      id_eligibility: "Select age eligibility",
      id_network: "Select network",
      id_language: "Select language",
      id_timezone: "Select timezone",
      id_reading: "Select reading preference",
      id_channel: "Select channel",
    };
    if (placeholderMap[sel.id]) {
      placeholder = placeholderMap[sel.id];
    } else if (sel.options.length > 0 && sel.options[0].value === "") {
      const firstOptText = sel.options[0].textContent.trim();
      if (firstOptText && firstOptText !== "—" && firstOptText !== "-") {
        placeholder = firstOptText;
      }
    }

    createSearchableSelect(sel, placeholder);
  });
}

initializeProfileMenus();
initializeRecordTabs();
initializePhotoControls();
initializeGeographyDropdowns();
initializeEligibilityWatcher();
initializeSearchableDropdowns();
