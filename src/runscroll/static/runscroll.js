// runscroll — inline client script (no external refs, vanilla, ES2017+).
//
// Built on a strict assumption: the Python side knows nothing about TOC,
// search, filters, or themes. Everything is reconstructed at page load by
// scanning the DOM. That's what allows the streaming append-write
// architecture (handoff §5) to work — Python never has to "know all
// sections in advance."
(function () {
  'use strict';

  const LEVELS = ['info', 'debug', 'warning', 'error', 'success'];

  function init() {
    document.documentElement.dataset.runscrollReady = '1';
    buildLevelFilter();
    buildToc();
    bindSearch();
    bindLevelFilter();
    bindTheme();
    updateBadges();
  }

  // -- Level filter (built dynamically so adding a level only touches
  //    LEVELS above) ----------------------------------------------------
  function buildLevelFilter() {
    const root = document.querySelector('.rs-level-filter');
    if (!root) return;
    LEVELS.forEach(function (level) {
      const label = document.createElement('label');
      label.className = 'rs-level-chip rs-level-chip-' + level;
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = true;
      cb.dataset.rsLevel = level;
      label.appendChild(cb);
      label.appendChild(document.createTextNode(' ' + level));
      root.appendChild(label);
    });
  }

  function bindLevelFilter() {
    const root = document.querySelector('.rs-level-filter');
    if (!root) return;
    root.addEventListener('change', function (e) {
      const cb = e.target;
      if (!cb || !cb.dataset || !cb.dataset.rsLevel) return;
      const cls = 'rs-hide-' + cb.dataset.rsLevel;
      document.body.classList.toggle(cls, !cb.checked);
    });
  }

  // -- TOC: scan <section data-rs-section-id> nodes ---------------------
  function buildToc() {
    const sections = document.querySelectorAll('section[data-rs-section-id]');
    if (!sections.length) return;
    const nav = document.querySelector('.rs-toc-nav');
    const panel = document.querySelector('.rs-toc-panel');
    const toggle = document.querySelector('.rs-toc-toggle');
    if (!nav || !panel || !toggle) return;

    const ul = document.createElement('ul');
    ul.className = 'rs-toc-list';
    sections.forEach(function (sec) {
      const li = document.createElement('li');
      li.className = 'rs-toc-item';
      li.dataset.rsDepth = sec.dataset.rsDepth || '1';
      const a = document.createElement('a');
      a.href = '#' + sec.id;
      a.textContent = sec.dataset.rsSectionName || '(unnamed section)';
      li.appendChild(a);
      ul.appendChild(li);
    });
    nav.appendChild(ul);

    toggle.hidden = false;
    toggle.addEventListener('click', function () {
      panel.hidden = !panel.hidden;
    });
    const closeBtn = panel.querySelector('.rs-toc-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        panel.hidden = true;
      });
    }
    // Auto-close on click of any TOC link (mobile-friendly).
    nav.addEventListener('click', function (e) {
      if (e.target && e.target.tagName === 'A' && window.matchMedia('(max-width: 720px)').matches) {
        panel.hidden = true;
      }
    });
  }

  // -- Search: substring match against entry textContent ----------------
  function bindSearch() {
    const input = document.querySelector('.rs-search');
    if (!input) return;
    let raf = null;
    input.addEventListener('input', function () {
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(function () {
        applySearch(input.value);
      });
    });
  }

  function applySearch(query) {
    const q = (query || '').trim().toLowerCase();
    const entries = document.querySelectorAll('.rs-entry');
    if (!q) {
      entries.forEach(function (e) {
        e.classList.remove('rs-entry-hidden-search');
      });
      return;
    }
    entries.forEach(function (e) {
      const text = (e.textContent || '').toLowerCase();
      e.classList.toggle('rs-entry-hidden-search', text.indexOf(q) === -1);
    });
  }

  // -- Theme toggle (default dark; click swaps to light) ----------------
  function bindTheme() {
    const btn = document.querySelector('.rs-theme-toggle');
    if (!btn) return;
    btn.addEventListener('click', function () {
      const isLight = document.documentElement.classList.toggle('rs-light');
      btn.textContent = isLight ? '☀' : '☾';
    });
  }

  // -- Error/warning count badges in header -----------------------------
  function updateBadges() {
    const errorBadge = document.querySelector('[data-rs-count="error"]');
    const warningBadge = document.querySelector('[data-rs-count="warning"]');
    const errorCount = document.querySelectorAll('.rs-text-error').length;
    const warningCount = document.querySelectorAll('.rs-text-warning').length;
    if (errorBadge && errorCount > 0) {
      errorBadge.hidden = false;
      errorBadge.textContent = errorCount + ' error' + (errorCount === 1 ? '' : 's');
    }
    if (warningBadge && warningCount > 0) {
      warningBadge.hidden = false;
      warningBadge.textContent = warningCount + ' warning' + (warningCount === 1 ? '' : 's');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
