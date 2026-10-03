(() => {
  const PATH_VALUE_SELECTOR = [
    ".path-row input",
    ".path-row textarea",
    ".path-output input",
    ".path-output textarea",
  ].join(", ");
  const GENERATED_BUTTON_LABELS = new Map([
    ["Upload file", "选择文件上传"],
    ["Paste from clipboard", "从剪贴板粘贴"],
    ["Copy conversation", "复制内容"],
    ["Fullscreen", "全屏查看"],
    ["Remove Image", "移除图片"],
  ]);
  const TAB_ROOT_SELECTOR = ".main-tabs, .sub-tabs";
  let labelingScheduled = false;
  let stickyNavigationScheduled = false;
  let runtimeAppId = "";
  let runtimeCheckInFlight = false;
  let runtimeReloading = false;
  let lastRuntimeCheckAt = 0;

  const readRuntimeAppId = async (response) => {
    if (!response.body || !response.body.getReader) {
      const config = await response.json();
      return String(config.app_id || "");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let prefix = "";
    try {
      for (let index = 0; index < 3 && prefix.length < 4096; index += 1) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        prefix += decoder.decode(value, { stream: true });
        const match = prefix.match(/"app_id"\s*:\s*(\d+)/);
        if (match) {
          return match[1];
        }
      }
      return "";
    } finally {
      await reader.cancel().catch(() => {});
    }
  };

  const checkRuntimeVersion = async () => {
    const now = Date.now();
    if (
      runtimeCheckInFlight
      || runtimeReloading
      || now - lastRuntimeCheckAt < 5000
    ) {
      return;
    }

    runtimeCheckInFlight = true;
    lastRuntimeCheckAt = now;
    try {
      const response = await fetch(new URL("config", document.baseURI), {
        cache: "no-store",
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        return;
      }
      const nextAppId = await readRuntimeAppId(response);
      if (!nextAppId) {
        return;
      }
      if (runtimeAppId && runtimeAppId !== nextAppId) {
        runtimeReloading = true;
        window.location.reload();
        return;
      }
      runtimeAppId = nextAppId;
      document.documentElement.dataset.runtimeAppId = nextAppId;
    } catch {
      // A stopped backend is expected during restart; verify again on recovery.
    } finally {
      runtimeCheckInFlight = false;
    }
  };

  const labelOverflowMenus = () => {
    document.querySelectorAll(".overflow-menu > button").forEach((button) => {
      const tabRoot = button.closest(TAB_ROOT_SELECTOR);
      const selectedMenuItem = button.parentElement?.querySelector(
        ".overflow-dropdown > button.selected",
      );
      const inferredLabel = String(selectedMenuItem?.textContent || "").trim();
      const selectedLabel = button.classList.contains("overflow-item-selected")
        ? String(tabRoot?.dataset.overflowSelectedLabel || inferredLabel).trim()
        : "";
      if (selectedLabel && tabRoot && !tabRoot.dataset.overflowSelectedLabel) {
        tabRoot.dataset.overflowSelectedLabel = selectedLabel;
      }
      const visibleLabel = selectedLabel || "更多";
      const accessibleLabel = selectedLabel
        ? `更多页面，当前：${selectedLabel}`
        : "更多";
      if (button.dataset.navLabel !== visibleLabel) {
        button.dataset.navLabel = visibleLabel;
      }
      if (button.getAttribute("aria-label") !== accessibleLabel) {
        button.setAttribute("aria-label", accessibleLabel);
      }
      if (button.getAttribute("title") !== accessibleLabel) {
        button.setAttribute("title", accessibleLabel);
      }
    });
  };

  const trackOverflowSelection = (event) => {
    if (!(event.target instanceof Element)) {
      return;
    }
    const button = event.target.closest("button");
    const tabRoot = button?.closest(TAB_ROOT_SELECTOR);
    if (!button || !tabRoot) {
      return;
    }
    if (button.closest(".overflow-dropdown")) {
      const selectedLabel = button.textContent.trim();
      if (selectedLabel) {
        tabRoot.dataset.overflowSelectedLabel = selectedLabel;
      }
      scheduleMenuLabeling();
      return;
    }
    if (button.matches('[role="tab"]')) {
      delete tabRoot.dataset.overflowSelectedLabel;
      scheduleMenuLabeling();
    }
  };

  const navigationButton = (rootSelector, label) => {
    const root = document.querySelector(rootSelector);
    if (!root) {
      return null;
    }
    const selector = root.matches(".main-tabs")
      ? ':scope > .tab-wrapper button[role="tab"], :scope > .tab-wrapper .overflow-dropdown > button'
      : 'button[role="tab"], .overflow-dropdown > button';
    return [...root.querySelectorAll(selector)]
      .find((button) => button.textContent.trim() === label) || null;
  };

  const activateTab = (rootSelector, label) => {
    const button = navigationButton(rootSelector, label);
    if (!button) {
      return false;
    }
    const isSelected = button.getAttribute("aria-selected") === "true"
      || button.classList.contains("selected");
    if (!isSelected) {
      button.click();
    }
    return true;
  };

  const navigateFromHome = (event) => {
    if (!(event.target instanceof Element)) {
      return;
    }
    const trigger = event.target.closest("[data-app-target]");
    if (!trigger) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    const pageLabel = String(trigger.dataset.appTarget || "").trim();
    const workbenchLabel = String(trigger.dataset.workbenchTarget || "").trim();
    if (!pageLabel || !activateTab(".main-tabs", pageLabel)) {
      return;
    }
    if (workbenchLabel) {
      window.requestAnimationFrame(() => activateTab(".sub-tabs", workbenchLabel));
    }
    window.requestAnimationFrame(() => {
      syncPrimaryNavigation();
      window.scrollTo({ top: 0, behavior: "auto" });
    });
  };

  const syncPrimaryNavigation = () => {
    const selected = document.querySelector(
      '.main-tabs > .tab-wrapper button[role="tab"][aria-selected="true"], '
      + ".main-tabs > .tab-wrapper .overflow-dropdown > button.selected",
    );
    const selectedLabel = String(selected?.textContent || "").trim();
    document.querySelectorAll(
      ".app-primary-nav-list > li > .app-nav-link[data-app-target]",
    ).forEach((button) => {
      const isCurrent = button.dataset.appTarget === selectedLabel;
      button.classList.toggle("is-current", isCurrent);
      if (isCurrent) {
        button.setAttribute("aria-current", "page");
      } else {
        button.removeAttribute("aria-current");
      }
    });
  };

  const labelPathPickers = () => {
    [
      ["#model-dir-picker button", "选择模型目录"],
      ["#storage-dir-picker button", "选择存储目录"],
    ].forEach(([selector, label]) => {
      document.querySelectorAll(selector).forEach((button) => {
        if (button.getAttribute("aria-label") !== label) {
          button.setAttribute("aria-label", label);
        }
        if (button.getAttribute("title") !== label) {
          button.setAttribute("title", label);
        }
      });
    });
  };

  const labelGeneratedIconButtons = () => {
    document.querySelectorAll("button").forEach((button) => {
      const label = GENERATED_BUTTON_LABELS.get(button.getAttribute("aria-label"))
        || GENERATED_BUTTON_LABELS.get(button.getAttribute("title"));
      if (!label) {
        return;
      }
      if (button.getAttribute("aria-label") !== label) {
        button.setAttribute("aria-label", label);
      }
      if (button.getAttribute("title") !== label) {
        button.setAttribute("title", label);
      }
    });
  };

  const labelImageButtons = () => {
    document.querySelectorAll(".image-container > button").forEach((button) => {
      if (!button.getAttribute("aria-label")) {
        button.setAttribute("aria-label", "打开图片预览");
      }
      if (!button.getAttribute("title")) {
        button.setAttribute("title", "打开图片预览");
      }
    });
  };

  const syncPathValueTitle = (target) => {
    if (
      !(target instanceof HTMLInputElement)
      && !(target instanceof HTMLTextAreaElement)
    ) {
      return;
    }
    if (!target.matches(PATH_VALUE_SELECTOR)) {
      return;
    }
    const value = target.value;
    if (value.trim()) {
      target.setAttribute("title", value);
    } else {
      target.removeAttribute("title");
    }
  };

  const labelPathValues = () => {
    document.querySelectorAll(PATH_VALUE_SELECTOR).forEach(syncPathValueTitle);
  };

  const labelIconActions = () => {
    labelOverflowMenus();
    labelPathPickers();
    labelGeneratedIconButtons();
    labelImageButtons();
    labelPathValues();
  };

  const syncImageComparison = (target) => {
    if (!(target instanceof HTMLInputElement) || !target.matches(".image-compare-range")) {
      return;
    }
    const comparison = target.closest("[data-image-compare]");
    if (comparison instanceof HTMLElement) {
      comparison.style.setProperty("--compare-position", `${target.value}%`);
    }
  };

  const scheduleMenuLabeling = () => {
    if (labelingScheduled) {
      return;
    }
    labelingScheduled = true;
    window.requestAnimationFrame(() => {
      labelingScheduled = false;
      labelIconActions();
    });
  };

  const syncStickyNavigation = () => {
    const shell = document.querySelector(".gradio-container");
    const headerShell = shell?.querySelector(".app-header-shell");
    const header = headerShell?.querySelector(".app-header");
    if (!(shell instanceof HTMLElement) || !headerShell || !header) {
      return;
    }
    const shellRect = shell.getBoundingClientRect();
    const headerHeight = header.getBoundingClientRect().height;
    headerShell.style.setProperty("--app-header-height", `${headerHeight}px`);
    header.style.setProperty("--app-shell-left", `${Math.max(0, shellRect.left)}px`);
    header.style.setProperty("--app-shell-width", `${shellRect.width}px`);
    const pageScrollTop = document.scrollingElement?.scrollTop || window.scrollY || 0;
    const headerOriginTop = headerShell.getBoundingClientRect().top + pageScrollTop;
    const triggerAt = headerOriginTop + headerHeight * 2;
    const shouldFloat = pageScrollTop >= Math.ceil(triggerAt);
    header.classList.toggle("app-header-floating", shouldFloat);
  };

  const scheduleStickyNavigation = () => {
    if (stickyNavigationScheduled) {
      return;
    }
    stickyNavigationScheduled = true;
    window.requestAnimationFrame(() => {
      stickyNavigationScheduled = false;
      syncStickyNavigation();
    });
  };

  const restartUpdatedToast = (mutations) => {
    mutations.forEach((mutation) => {
      const toast = mutation.target;
      if (!(toast instanceof HTMLElement) || !toast.matches(".app-toast")) {
        return;
      }
      toast.style.animation = "none";
      void toast.offsetWidth;
      toast.style.removeProperty("animation");
    });
  };

  const renderDetectionTablePage = (grid, requestedPage) => {
    const rows = [...grid.querySelectorAll(".record-detection-row")];
    const pageSize = Math.max(1, Number.parseInt(grid.dataset.pageSize || "8", 10));
    const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
    const currentPage = Math.min(pageCount, Math.max(1, requestedPage));
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;

    rows.forEach((row, index) => {
      const isVisible = index >= startIndex && index < endIndex;
      row.hidden = !isVisible;
      const detail = row.nextElementSibling;
      if (detail?.classList.contains("record-coordinate-row")) {
        detail.hidden = true;
      }
      row.querySelector(".record-coordinate-trigger")?.setAttribute("aria-expanded", "false");
    });

    grid.dataset.currentPage = String(currentPage);
    const status = grid.querySelector(".record-page-status");
    const pageNumber = grid.querySelector(".record-page-number");
    if (status) {
      status.textContent = `第 ${currentPage} / ${pageCount} 页 · 共 ${rows.length} 项`;
    }
    if (pageNumber) {
      pageNumber.textContent = `${currentPage} / ${pageCount}`;
    }
    const previous = grid.querySelector('[data-page-action="previous"]');
    const next = grid.querySelector('[data-page-action="next"]');
    if (previous instanceof HTMLButtonElement) {
      previous.disabled = currentPage <= 1;
    }
    if (next instanceof HTMLButtonElement) {
      next.disabled = currentPage >= pageCount;
    }
  };

  const initializeDetectionTables = () => {
    document.querySelectorAll(".record-detection-grid").forEach((grid) => {
      if (!(grid instanceof HTMLElement) || grid.dataset.paginationReady === "true") {
        return;
      }
      grid.dataset.paginationReady = "true";
      renderDetectionTablePage(grid, Number.parseInt(grid.dataset.currentPage || "1", 10));
    });
  };

  const handleDetectionTableClick = (event) => {
    if (!(event.target instanceof Element)) {
      return;
    }
    const coordinateTrigger = event.target.closest(".record-coordinate-trigger");
    if (coordinateTrigger instanceof HTMLButtonElement) {
      const row = coordinateTrigger.closest(".record-detection-row");
      const detail = row?.nextElementSibling;
      if (detail?.classList.contains("record-coordinate-row")) {
        const shouldOpen = coordinateTrigger.getAttribute("aria-expanded") !== "true";
        coordinateTrigger.setAttribute("aria-expanded", String(shouldOpen));
        detail.hidden = !shouldOpen;
      }
      return;
    }

    const pageButton = event.target.closest(".record-page-button");
    if (!(pageButton instanceof HTMLButtonElement) || pageButton.disabled) {
      return;
    }
    const grid = pageButton.closest(".record-detection-grid");
    if (!(grid instanceof HTMLElement)) {
      return;
    }
    const currentPage = Number.parseInt(grid.dataset.currentPage || "1", 10);
    const direction = pageButton.dataset.pageAction === "previous" ? -1 : 1;
    renderDetectionTablePage(grid, currentPage + direction);
    grid.querySelector(".record-detection-table-wrap")?.scrollTo({ top: 0, behavior: "auto" });
  };

  const start = () => {
    if (!document.body) {
      window.requestAnimationFrame(start);
      return;
    }
    labelIconActions();
    initializeDetectionTables();
    syncPrimaryNavigation();
    syncStickyNavigation();
    void checkRuntimeVersion();
    window.addEventListener("focus", checkRuntimeVersion);
    window.addEventListener("online", checkRuntimeVersion);
    document.addEventListener("visibilitychange", checkRuntimeVersion);
    ["input", "change", "focusin", "pointerover"].forEach((eventName) => {
      document.addEventListener(eventName, (event) => syncPathValueTitle(event.target), true);
    });
    document.addEventListener("click", trackOverflowSelection, true);
    document.addEventListener("click", navigateFromHome, true);
    document.addEventListener("click", handleDetectionTableClick, true);
    document.addEventListener("input", (event) => syncImageComparison(event.target), true);
    window.addEventListener("scroll", scheduleStickyNavigation, { passive: true });
    window.addEventListener("resize", scheduleStickyNavigation, { passive: true });
    window.setInterval(checkRuntimeVersion, 30000);
    new MutationObserver(() => {
      scheduleMenuLabeling();
      initializeDetectionTables();
    }).observe(document.body, {
      childList: true,
      subtree: true,
    });
    new MutationObserver(() => {
      syncPrimaryNavigation();
      scheduleStickyNavigation();
    }).observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["aria-selected"],
    });
    new MutationObserver(restartUpdatedToast).observe(document.body, {
      attributes: true,
      attributeFilter: ["data-toast-sequence"],
      subtree: true,
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
