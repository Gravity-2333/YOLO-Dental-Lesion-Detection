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
  ]);
  let labelingScheduled = false;
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
      if (button.getAttribute("aria-label") !== "更多") {
        button.setAttribute("aria-label", "更多");
      }
      if (button.getAttribute("title") !== "更多") {
        button.setAttribute("title", "更多");
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
    labelPathValues();
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

  const start = () => {
    if (!document.body) {
      window.requestAnimationFrame(start);
      return;
    }
    labelIconActions();
    void checkRuntimeVersion();
    window.addEventListener("focus", checkRuntimeVersion);
    window.addEventListener("online", checkRuntimeVersion);
    document.addEventListener("visibilitychange", checkRuntimeVersion);
    ["input", "change", "focusin", "pointerover"].forEach((eventName) => {
      document.addEventListener(eventName, (event) => syncPathValueTitle(event.target), true);
    });
    window.setInterval(checkRuntimeVersion, 30000);
    new MutationObserver(scheduleMenuLabeling).observe(document.body, {
      childList: true,
      subtree: true,
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
