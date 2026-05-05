// runscroll — inline client script (no external refs).
//
// Step 4 ships an empty entry point. Step 9 will populate this with:
//   - sidebar TOC built by scanning <section data-rs-section> nodes
//   - top-of-page search filtering entries by text content
//   - level-toggle checkboxes (info / debug / warning / error / success)
//   - dark mode toggle and error/warning count badges
//
// Constraints: vanilla, no dependencies, no network, ES2017+. The whole
// runtime ships as a single inline <script> tag in the report HTML.
(function () {
  'use strict';

  function init() {
    document.documentElement.dataset.runscrollReady = '1';
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
