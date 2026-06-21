/**
 * Nazarene School Portal — UI Utilities
 * Global helpers for charts, dark mode, sidebar, and interactions.
 */

// ── Chart Defaults ─────────────────────────────────────────────────────────
window.NZCharts = {
  colors: {
    brand:   '#6366f1', brandAlpha: 'rgba(99,102,241,0.12)',
    success: '#10b981', successAlpha: 'rgba(16,185,129,0.12)',
    warning: '#f59e0b', warningAlpha: 'rgba(245,158,11,0.12)',
    danger:  '#ef4444', dangerAlpha: 'rgba(239,68,68,0.12)',
    info:    '#0ea5e9', infoAlpha: 'rgba(14,165,233,0.12)',
    purple:  '#8b5cf6',
    rose:    '#f43f5e',
    cyan:    '#06b6d4',
    lime:    '#84cc16',
    palette: ['#6366f1','#10b981','#f59e0b','#0ea5e9','#8b5cf6','#f43f5e','#06b6d4','#84cc16','#ec4899','#f97316'],
  },

  getDefaults() {
    const dark = document.documentElement.classList.contains('dark');
    return {
      textColor:   dark ? '#94a3b8' : '#64748b',
      gridColor:   dark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
      borderColor: dark ? '#1e293b' : '#ffffff',
      tooltipBg:   dark ? 'rgba(15,23,42,0.95)' : 'rgba(15,23,42,0.90)',
    };
  },

  barConfig(labels, datasets, opts = {}) {
    const d = this.getDefaults();
    return {
      type: 'bar',
      data: { labels, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        animation: { duration: 800, easing: 'easeOutQuart' },
        plugins: {
          legend: opts.legend !== undefined ? opts.legend : { display: false },
          tooltip: {
            backgroundColor: d.tooltipBg, padding: 12, cornerRadius: 10,
            titleColor: '#fff', bodyColor: '#cbd5e1',
            displayColors: false,
            callbacks: opts.tooltipCallbacks || {},
          },
        },
        scales: {
          y: {
            beginAtZero: true, max: opts.maxY || 100,
            grid: { color: d.gridColor },
            ticks: { color: d.textColor, callback: opts.yTick || (v => v + '%'), font: { size: 11 } },
          },
          x: {
            grid: { display: false },
            ticks: { color: d.textColor, font: { size: 11 } },
          },
        },
        ...opts.extra,
      },
    };
  },

  lineConfig(labels, datasets, opts = {}) {
    const d = this.getDefaults();
    return {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        animation: { duration: 1000, easing: 'easeOutQuart' },
        plugins: {
          legend: opts.legend !== undefined ? opts.legend : { display: false },
          tooltip: {
            backgroundColor: d.tooltipBg, padding: 12, cornerRadius: 10,
            titleColor: '#fff', bodyColor: '#cbd5e1',
            displayColors: false,
            callbacks: opts.tooltipCallbacks || {},
          },
        },
        scales: {
          y: {
            beginAtZero: true, max: opts.maxY || 100,
            grid: { color: d.gridColor },
            ticks: { color: d.textColor, callback: opts.yTick || (v => v + '%'), font: { size: 11 } },
          },
          x: {
            grid: { display: false },
            ticks: { color: d.textColor, font: { size: 12, weight: '600' } },
          },
        },
        ...opts.extra,
      },
    };
  },

  doughnutConfig(labels, data, colors, opts = {}) {
    const d = this.getDefaults();
    return {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{ data, backgroundColor: colors, borderWidth: 3, borderColor: d.borderColor }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        animation: { animateRotate: true, duration: 1000 },
        cutout: opts.cutout || '65%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: { padding: 16, usePointStyle: true, color: d.textColor, font: { size: 12, weight: '600' } },
          },
          tooltip: {
            backgroundColor: d.tooltipBg, padding: 12, cornerRadius: 10,
            titleColor: '#fff', bodyColor: '#cbd5e1',
          },
        },
        ...opts.extra,
      },
    };
  },

  showEmpty(canvasId, icon, msg) {
    icon = icon || 'fas fa-chart-bar';
    msg = msg || 'No data yet';
    var el = document.getElementById(canvasId);
    if (!el) return;
    var container = el.closest('.relative, div');
    if (container) {
      container.innerHTML =
        '<div class="flex flex-col items-center justify-center py-16 px-6 text-center">' +
          '<div class="w-16 h-16 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center text-3xl text-surface-400 dark:text-surface-500 mb-4">' +
            '<i class="' + icon + '"></i>' +
          '</div>' +
          '<p class="text-sm font-medium text-surface-900 dark:text-white">' + msg + '</p>' +
        '</div>';
    }
  },
};

// ── Sidebar Collapse (desktop icon-only mode) ──────────────────────────────
window.SidebarManager = {
  COLLAPSED_KEY: 'sidebarCollapsed',

  init() {
    var sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    if (window.innerWidth >= 1024 && localStorage.getItem(this.COLLAPSED_KEY) === 'true') {
      this.collapse(false);
    }
  },

  toggle() {
    var sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    sidebar.classList.contains('sidebar-collapsed') ? this.expand() : this.collapse();
  },

  collapse(save) {
    if (save === undefined) save = true;
    var sidebar = document.getElementById('sidebar');
    var main = document.querySelector('[data-main-content]') || document.querySelector('[class*="lg:ml-"]');
    if (!sidebar) return;
    sidebar.classList.add('sidebar-collapsed');
    if (main) {
      main.classList.remove('lg:ml-64');
      main.classList.add('lg:ml-[4.5rem]');
    }
    var icon = document.getElementById('collapseIcon');
    if (icon) icon.className = 'fas fa-chevron-right text-xs text-surface-400';
    if (save) localStorage.setItem(this.COLLAPSED_KEY, 'true');
  },

  expand() {
    var sidebar = document.getElementById('sidebar');
    var main = document.querySelector('[data-main-content]') || document.querySelector('[class*="lg:ml-"]');
    if (!sidebar) return;
    sidebar.classList.remove('sidebar-collapsed');
    if (main) {
      main.classList.remove('lg:ml-[4.5rem]');
      main.classList.add('lg:ml-64');
    }
    var icon = document.getElementById('collapseIcon');
    if (icon) icon.className = 'fas fa-chevron-left text-xs text-surface-400';
    localStorage.setItem(this.COLLAPSED_KEY, 'false');
  },
};

// ── Smooth Number Animation ─────────────────────────────────────────────────
function animateNumber(el, to, duration, suffix) {
  duration = duration || 800;
  suffix = suffix || '';
  var from = 0;
  var start = performance.now();
  function step(now) {
    var progress = Math.min((now - start) / duration, 1);
    var eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(from + (to - from) * eased) + suffix;
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ── Focus Trap for Mobile Sidebar ─────────────────────────────────────────
function trapFocus(el) {
  var focusable = el.querySelectorAll('a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])');
  if (!focusable.length) return;
  var first = focusable[0], last = focusable[focusable.length - 1];
  el.addEventListener('keydown', function(e) {
    if (e.key !== 'Tab') return;
    if (e.shiftKey) { if (document.activeElement === first) { last.focus(); e.preventDefault(); } }
    else { if (document.activeElement === last) { first.focus(); e.preventDefault(); } }
  });
}

// ── Intersection Observer for scroll animations ────────────────────────────
function initScrollAnimations() {
  if (!('IntersectionObserver' in window)) return;
  var observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

  document.querySelectorAll('[data-animate]').forEach(function(el) {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    observer.observe(el);
  });
}

// ── Init on DOM ready ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  // Animate .stat-value numbers
  document.querySelectorAll('[data-animate-num]').forEach(function (el) {
    var val = parseFloat(el.dataset.animateNum) || 0;
    var suffix = el.dataset.animateSuffix || '';
    animateNumber(el, val, 900, suffix);
  });

  // Init sidebar manager
  SidebarManager.init();

  // Add focus trap to mobile sidebar
  var sidebar = document.getElementById('sidebar');
  if (sidebar) trapFocus(sidebar);

  // Init scroll animations
  initScrollAnimations();
});
