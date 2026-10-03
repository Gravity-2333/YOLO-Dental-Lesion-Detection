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
  let magnifierPreferenceInitialized = false;
  let magnifierZoom = 2.5;
  const MAGNIFIER_ICON = '<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path></svg>';

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

  const magnifierEnabled = () => {
    const runtimeValue = document.documentElement.dataset.resultMagnifierEnabled;
    if (runtimeValue === "true" || runtimeValue === "false") {
      return runtimeValue === "true";
    }
    const input = document.querySelector(
      '#magnifier-enabled-setting input[type="checkbox"]',
    );
    return !(input instanceof HTMLInputElement) || input.checked;
  };

  const formatMagnifierZoom = () => `${magnifierZoom.toFixed(2).replace(/\.?0+$/u, "")}x`;

  const synchronizeMagnifierToggleButtons = () => {
    const enabled = magnifierEnabled();
    document.querySelectorAll(".result-magnifier-toggle").forEach((button) => {
      button.classList.toggle("is-active", enabled);
      button.setAttribute("aria-pressed", String(enabled));
      button.setAttribute("aria-label", enabled ? "关闭悬停放大镜" : "开启悬停放大镜");
      button.setAttribute("title", enabled ? "关闭悬停放大镜" : "开启悬停放大镜");
    });
  };

  const initializeMagnifierToggleButtons = () => {
    document.querySelectorAll(".primary-result-card .icon-button-wrapper.top-panel").forEach((toolbar) => {
      if (toolbar.querySelector(".result-magnifier-toggle")) {
        return;
      }
      const button = document.createElement("button");
      button.type = "button";
      button.className = "result-magnifier-toggle";
      button.innerHTML = MAGNIFIER_ICON;
      toolbar.prepend(button);
    });
    synchronizeMagnifierToggleButtons();
  };

  const synchronizeMagnifierSettingInput = () => {
    const runtimeValue = document.documentElement.dataset.resultMagnifierEnabled;
    const input = document.querySelector(
      '#magnifier-enabled-setting input[type="checkbox"]',
    );
    if (
      (runtimeValue === "true" || runtimeValue === "false")
      && input instanceof HTMLInputElement
      && input.checked !== (runtimeValue === "true")
    ) {
      input.click();
    }
  };

  const setMagnifierEnabled = (enabled) => {
    document.documentElement.dataset.resultMagnifierEnabled = String(enabled);
    const input = document.querySelector(
      '#magnifier-enabled-setting input[type="checkbox"]',
    );
    if (input instanceof HTMLInputElement && input.checked !== enabled) {
      input.click();
    }
    if (!enabled) {
      hideResultMagnifiers();
    }
    synchronizeMagnifierToggleButtons();
  };

  const initializeMagnifierPreference = () => {
    if (magnifierPreferenceInitialized) {
      return;
    }
    const marker = document.querySelector(".magnifier-runtime-setting[data-enabled]");
    if (!(marker instanceof HTMLElement)) {
      return;
    }
    document.documentElement.dataset.resultMagnifierEnabled =
      marker.dataset.enabled === "false" ? "false" : "true";
    magnifierPreferenceInitialized = true;
    synchronizeMagnifierToggleButtons();
  };

  const hideResultMagnifiers = () => {
    document.querySelectorAll(".result-magnifier.is-visible").forEach((lens) => {
      lens.classList.remove("is-visible");
    });
  };

  const ensureResultMagnifier = (stage) => {
    let lens = stage.querySelector(":scope > .result-magnifier");
    if (lens instanceof HTMLElement) {
      return lens;
    }
    lens = document.createElement("div");
    lens.className = "result-magnifier";
    lens.setAttribute("aria-hidden", "true");
    const canvas = document.createElement("canvas");
    lens.appendChild(canvas);
    stage.appendChild(lens);
    return lens;
  };

  const imageContentBounds = (image) => {
    const rect = image.getBoundingClientRect();
    if (!image.naturalWidth || !image.naturalHeight || !rect.width || !rect.height) {
      return null;
    }
    const scale = Math.min(
      rect.width / image.naturalWidth,
      rect.height / image.naturalHeight,
    );
    const width = image.naturalWidth * scale;
    const height = image.naturalHeight * scale;
    return {
      left: rect.left + (rect.width - width) / 2,
      top: rect.top + (rect.height - height) / 2,
      width,
      height,
      scale,
    };
  };

  const moveResultMagnifier = (event) => {
    if (!(event.target instanceof Element) || event.pointerType === "touch") {
      return;
    }
    const card = event.target.closest(".primary-result-card");
    const stage = card?.closest(".result-image-stage");
    const image = card?.querySelector("img");
    if (
      !magnifierEnabled()
      || !(stage instanceof HTMLElement)
      || !(image instanceof HTMLImageElement)
      || !image.complete
    ) {
      hideResultMagnifiers();
      return;
    }

    const bounds = imageContentBounds(image);
    if (!bounds) {
      return;
    }
    const x = event.clientX - bounds.left;
    const y = event.clientY - bounds.top;
    if (x < 0 || y < 0 || x > bounds.width || y > bounds.height) {
      hideResultMagnifiers();
      return;
    }

    const lens = ensureResultMagnifier(stage);
    const canvas = lens.querySelector("canvas");
    if (!(canvas instanceof HTMLCanvasElement)) {
      return;
    }
    lens.classList.add("is-visible");

    const stageRect = stage.getBoundingClientRect();
    const lensWidth = lens.offsetWidth;
    const lensHeight = lens.offsetHeight;
    const gap = 18;
    const pointerLeft = event.clientX - stageRect.left;
    const pointerTop = event.clientY - stageRect.top;
    const contentLeft = bounds.left - stageRect.left;
    const contentTop = bounds.top - stageRect.top;
    const contentRight = contentLeft + bounds.width;
    const contentBottom = contentTop + bounds.height;
    const placeLeft = x <= bounds.width / 2;
    const placeAbove = y <= bounds.height / 2;
    let left = placeLeft ? pointerLeft - lensWidth - gap : pointerLeft + gap;
    let top = placeAbove ? pointerTop - lensHeight - gap : pointerTop + gap;
    left = Math.max(
      contentLeft + 8,
      Math.min(left, contentRight - lensWidth - 8),
    );
    top = Math.max(
      contentTop + 8,
      Math.min(top, contentBottom - lensHeight - 8),
    );
    lens.style.left = `${left}px`;
    lens.style.top = `${top}px`;
    lens.dataset.quadrant = `${placeAbove ? "top" : "bottom"}-${placeLeft ? "left" : "right"}`;
    lens.dataset.zoom = formatMagnifierZoom();

    const deviceScale = Math.min(2, window.devicePixelRatio || 1);
    const canvasWidth = Math.max(1, lens.clientWidth);
    const canvasHeight = Math.max(1, lens.clientHeight);
    canvas.width = Math.round(canvasWidth * deviceScale);
    canvas.height = Math.round(canvasHeight * deviceScale);
    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }
    context.setTransform(deviceScale, 0, 0, deviceScale, 0, 0);
    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = "high";

    const zoom = magnifierZoom;
    const sourceWidth = Math.min(image.naturalWidth, canvasWidth / zoom / bounds.scale);
    const sourceHeight = Math.min(image.naturalHeight, canvasHeight / zoom / bounds.scale);
    const sourceX = Math.max(
      0,
      Math.min(
        image.naturalWidth - sourceWidth,
        (x / bounds.width) * image.naturalWidth - sourceWidth / 2,
      ),
    );
    const sourceY = Math.max(
      0,
      Math.min(
        image.naturalHeight - sourceHeight,
        (y / bounds.height) * image.naturalHeight - sourceHeight / 2,
      ),
    );
    context.clearRect(0, 0, canvasWidth, canvasHeight);
    context.drawImage(
      image,
      sourceX,
      sourceY,
      sourceWidth,
      sourceHeight,
      0,
      0,
      canvasWidth,
      canvasHeight,
    );
  };

  const adjustResultMagnifierZoom = (event) => {
    if (!event.ctrlKey || !(event.target instanceof Element)) {
      return;
    }
    const card = event.target.closest(".primary-result-card");
    const image = card?.querySelector("img");
    if (!(image instanceof HTMLImageElement) || !magnifierEnabled()) {
      return;
    }
    const bounds = imageContentBounds(image);
    if (
      !bounds
      || event.clientX < bounds.left
      || event.clientX > bounds.left + bounds.width
      || event.clientY < bounds.top
      || event.clientY > bounds.top + bounds.height
    ) {
      return;
    }
    event.preventDefault();
    const direction = event.deltaY < 0 ? 1 : -1;
    magnifierZoom = Math.max(1.5, Math.min(5, magnifierZoom + direction * 0.25));
    moveResultMagnifier(event);
  };

  const handleMagnifierToggleClick = (event) => {
    if (!(event.target instanceof Element)) {
      return;
    }
    const button = event.target.closest(".result-magnifier-toggle");
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    setMagnifierEnabled(!magnifierEnabled());
  };

  const leaveResultImage = (event) => {
    if (!(event.target instanceof Element)) {
      return;
    }
    const card = event.target.closest(".primary-result-card");
    if (card && !card.contains(event.relatedTarget)) {
      hideResultMagnifiers();
    }
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

  const reportExportTriggerButton = (dock) => {
    const candidate = dock?.querySelector(".report-export-menu-trigger");
    if (candidate instanceof HTMLButtonElement) {
      return candidate;
    }
    return candidate?.querySelector("button") || null;
  };

  const closeReportExportMenus = (except = null) => {
    document.querySelectorAll(".report-export-dock.is-open").forEach((dock) => {
      if (dock === except) {
        return;
      }
      dock.classList.remove("is-open");
      reportExportTriggerButton(dock)?.setAttribute("aria-expanded", "false");
    });
  };

  const positionReportExportMenu = (dock) => {
    const button = reportExportTriggerButton(dock);
    const popover = dock?.querySelector(
      ":scope > .styler > .report-export-popover",
    );
    if (!(button instanceof HTMLElement) || !(popover instanceof HTMLElement)) {
      return;
    }
    const triggerRect = button.getBoundingClientRect();
    const popoverRect = popover.getBoundingClientRect();
    const gap = 12;
    let left = triggerRect.right + gap;
    if (left + popoverRect.width > window.innerWidth - gap) {
      left = triggerRect.left - popoverRect.width - gap;
    }
    const top = Math.max(
      gap,
      Math.min(
        triggerRect.bottom - popoverRect.height,
        window.innerHeight - popoverRect.height - gap,
      ),
    );
    popover.style.setProperty("--report-export-popover-left", `${Math.max(gap, left)}px`);
    popover.style.setProperty("--report-export-popover-top", `${top}px`);
  };

  const handleReportExportMenuClick = (event) => {
    if (!(event.target instanceof Element)) {
      return;
    }
    const trigger = event.target.closest(".report-export-menu-trigger");
    if (trigger) {
      const button = trigger instanceof HTMLButtonElement ? trigger : trigger.querySelector("button");
      const dock = trigger.closest(".report-export-dock");
      if (!(dock instanceof HTMLElement) || button?.disabled) {
        return;
      }
      const shouldOpen = !dock.classList.contains("is-open");
      closeReportExportMenus(dock);
      dock.classList.toggle("is-open", shouldOpen);
      button?.setAttribute("aria-expanded", String(shouldOpen));
      if (shouldOpen) {
        positionReportExportMenu(dock);
      }
      return;
    }
    if (!event.target.closest(".report-export-popover")) {
      closeReportExportMenus();
    }
  };

  const start = () => {
    if (!document.body) {
      window.requestAnimationFrame(start);
      return;
    }
    labelIconActions();
    initializeMagnifierPreference();
    initializeMagnifierToggleButtons();
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
    document.addEventListener("click", handleReportExportMenuClick, true);
    document.addEventListener("click", handleMagnifierToggleClick, true);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeReportExportMenus();
      }
    });
    document.addEventListener("input", (event) => syncImageComparison(event.target), true);
    document.addEventListener("pointermove", moveResultMagnifier, true);
    document.addEventListener("pointerout", leaveResultImage, true);
    document.addEventListener("wheel", adjustResultMagnifierZoom, { capture: true, passive: false });
    document.addEventListener("change", (event) => {
      if (event.target instanceof Element && event.target.closest("#magnifier-enabled-setting")) {
        if (event.target instanceof HTMLInputElement) {
          document.documentElement.dataset.resultMagnifierEnabled = String(event.target.checked);
        }
        hideResultMagnifiers();
        synchronizeMagnifierToggleButtons();
      }
    }, true);
    window.addEventListener("scroll", scheduleStickyNavigation, { passive: true });
    window.addEventListener("resize", scheduleStickyNavigation, { passive: true });
    window.setInterval(checkRuntimeVersion, 30000);
    new MutationObserver(() => {
      scheduleMenuLabeling();
      initializeDetectionTables();
      initializeMagnifierPreference();
      initializeMagnifierToggleButtons();
      synchronizeMagnifierSettingInput();
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
