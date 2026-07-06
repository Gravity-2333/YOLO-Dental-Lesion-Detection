(() => {
  const labelOverflowMenus = () => {
    document.querySelectorAll(".overflow-menu > button").forEach((button) => {
      button.setAttribute("aria-label", "更多");
      button.setAttribute("title", "更多");
    });
  };

  const start = () => {
    if (!document.body) {
      window.requestAnimationFrame(start);
      return;
    }
    labelOverflowMenus();
    new MutationObserver(labelOverflowMenus).observe(document.body, {
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
