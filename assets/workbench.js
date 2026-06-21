(() => {
  const labelOverflowMenus = () => {
    document.querySelectorAll(".overflow-menu > button").forEach((button) => {
      button.setAttribute("aria-label", "更多");
      button.setAttribute("title", "更多");
    });
  };

  labelOverflowMenus();
  new MutationObserver(labelOverflowMenus).observe(document.body, {
    childList: true,
    subtree: true,
  });
})();
