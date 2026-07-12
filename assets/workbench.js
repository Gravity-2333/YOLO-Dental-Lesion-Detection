(() => {
  let labelingScheduled = false;

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

  const scheduleMenuLabeling = () => {
    if (labelingScheduled) {
      return;
    }
    labelingScheduled = true;
    window.requestAnimationFrame(() => {
      labelingScheduled = false;
      labelOverflowMenus();
    });
  };

  const start = () => {
    if (!document.body) {
      window.requestAnimationFrame(start);
      return;
    }
    labelOverflowMenus();
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
