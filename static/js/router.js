/* ============================================================
   ROUTER.JS — Hash-based SPA Routing with Transitions
   ============================================================ */

const Router = (() => {
  const ROUTES = ['dashboard', 'jobs', 'trends', 'news', 'insights'];
  const DEFAULT = 'dashboard';

  let currentPage = null;
  let onPageChange = null;

  function getHash() {
    const h = window.location.hash.replace('#', '').toLowerCase();
    return ROUTES.includes(h) ? h : DEFAULT;
  }

  function navigate(page) {
    if (!ROUTES.includes(page)) page = DEFAULT;
    window.location.hash = page;
  }

  function activate(page) {
    // Hide ALL pages first
    ROUTES.forEach(r => {
      const el = document.getElementById(`page-${r}`);
      if (el && r !== page) el.classList.remove('active');
    });

    const prev = currentPage;

    // Show target page
    const next = document.getElementById(`page-${page}`);
    if (next) {
      if (prev !== page) {
        // Animate in
        next.style.opacity = '0';
        next.style.transform = 'translateY(12px)';
      }
      next.classList.add('active');

      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          next.style.transition = 'opacity 0.28s ease, transform 0.28s ease';
          next.style.opacity = '1';
          next.style.transform = 'translateY(0)';
        });
      });
    }

    // Update nav links
    document.querySelectorAll('[data-route]').forEach(el => {
      el.classList.toggle('active', el.dataset.route === page);
    });

    currentPage = page;
    document.title = pageTitles[page] || 'IT Intelligence Dashboard';
    window.scrollTo({ top: 0, behavior: 'smooth' });

    if (onPageChange) onPageChange(page);
  }

  const pageTitles = {
    dashboard: 'Dashboard — IT Jobs Intelligence',
    jobs:      'Live Jobs — IT Jobs Intelligence',
    trends:    'Market Trends — IT Jobs Intelligence',
    news:      'Live News — IT Jobs Intelligence',
    insights:  'Insights & Strategy — IT Jobs Intelligence',
  };

  function init(changeCallback) {
    onPageChange = changeCallback;

    window.addEventListener('hashchange', () => {
      activate(getHash());
    });

    activate(getHash());
  }

  return { init, navigate, getHash, ROUTES };
})();
