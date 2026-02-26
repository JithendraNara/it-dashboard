/* ============================================================
   API.JS — CGI API Wrappers for Jobs and News
   ============================================================ */

const API = (() => {
  const CGI_BIN = '/api';

  /* ── JOBS ─────────────────────────────────────────────────── */
  async function fetchJobs({ query = '', type = 'all', source = 'all', page = 1, force = false } = {}) {
    const params = new URLSearchParams();
    if (query) params.set('query', query);
    if (type && type !== 'all') params.set('type', type);
    params.set('page', page);
    if (force) params.set('force', '1');

    const url = `${CGI_BIN}/jobs.py?${params.toString()}`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`Jobs API error: ${resp.status}`);
    const data = await resp.json();

    // Client-side source filtering (API doesn't support it natively)
    if (source && source !== 'all') {
      data.jobs = data.jobs.filter(j =>
        j.source && j.source.toLowerCase().includes(source.toLowerCase())
      );
    }

    return data;
  }

  /* ── NEWS ─────────────────────────────────────────────────── */
  async function fetchNews(force = false) {
    const params = force ? '?force=1' : '';
    const url = `${CGI_BIN}/news.py${params}`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`News API error: ${resp.status}`);
    return resp.json();
  }

  /* ── TIME HELPERS ─────────────────────────────────────────── */
  function relativeTime(dateStr) {
    if (!dateStr) return 'Recently';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) {
        // Try unix timestamp
        const ts = parseInt(dateStr);
        if (!isNaN(ts)) {
          const d2 = new Date(ts < 1e10 ? ts * 1000 : ts);
          return computeRelative(d2);
        }
        return 'Recently';
      }
      return computeRelative(d);
    } catch {
      return 'Recently';
    }
  }

  function computeRelative(d) {
    const diff = Date.now() - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1)   return 'Just now';
    if (mins < 60)  return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24)   return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 30)  return `${days}d ago`;
    const months = Math.floor(days / 30);
    return `${months}mo ago`;
  }

  function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return '';
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch { return ''; }
  }

  /* ── NEWS CATEGORIZER ─────────────────────────────────────── */
  function categorizeNews(item) {
    const text = ((item.title || '') + ' ' + (item.snippet || '')).toLowerCase();
    const layoffKw  = ['layoff', 'laid off', 'cut', 'reduction', 'downsiz', 'fire', 'eliminat', 'job cut', 'workforce'];
    const aiKw      = ['ai', 'artificial intelligence', 'machine learning', 'gpt', 'llm', 'openai', 'gemini', 'claude', 'neural', 'automation'];
    const hiringKw  = ['hiring', 'recruit', 'job opening', 'new role', 'talent', 'workforce', 'h-1b', 'salary', 'remote work'];

    if (layoffKw.some(k => text.includes(k))) return 'layoffs';
    if (aiKw.some(k => text.includes(k)))     return 'ai';
    if (hiringKw.some(k => text.includes(k))) return 'hiring';
    return 'tech';
  }

  const topicLabels = {
    layoffs: 'Layoffs',
    ai:      'AI',
    hiring:  'Hiring',
    tech:    'Tech',
  };

  /* ── JOB CARD RENDERER ────────────────────────────────────── */
  function renderJobCard(job) {
    const typeBadge = (job.type || '').toLowerCase().includes('remote')
      ? '<span class="badge badge-remote">Remote</span>'
      : '<span class="badge badge-ft">Full-time</span>';

    const srcClass = {
      'Remotive':  'badge-src-remotive',
      'RemoteOK':  'badge-src-remoteok',
      'Arbeitnow': 'badge-src-arbeitnow',
    }[job.source] || 'badge-src-remoteok';

    const tags = (job.tags || []).slice(0, 5).map(t =>
      `<span class="tag">${escHtml(t)}</span>`
    ).join('');

    const salary = job.salary ? `<span class="job-salary">${escHtml(job.salary)}</span>` : '';
    const time   = relativeTime(job.posted);
    const snippet = job.snippet ? escHtml(job.snippet.substring(0, 180)) : '';

    return `
      <div class="job-card">
        <div class="job-left">
          <a class="job-title" href="${escHtml(job.url || '#')}" target="_blank" rel="noopener noreferrer">
            ${escHtml(job.title || 'Untitled Role')}
          </a>
          <div class="job-meta">
            <span class="job-company">${escHtml(job.company || '')}</span>
            ${job.location ? `<span class="job-location">📍 ${escHtml(job.location)}</span>` : ''}
            ${salary}
          </div>
          ${snippet ? `<p class="job-snippet">${snippet}…</p>` : ''}
          <div class="tags-row">
            ${typeBadge}
            <span class="badge ${srcClass}">${escHtml(job.source || '')}</span>
            ${tags}
          </div>
        </div>
        <div class="job-right">
          <span class="job-time">${time}</span>
          <a class="apply-btn" href="${escHtml(job.url || '#')}" target="_blank" rel="noopener noreferrer">Apply →</a>
        </div>
      </div>
    `;
  }

  /* ── NEWS CARD RENDERER ──────────────────────────────────── */
  function renderNewsCard(item) {
    const topic = categorizeNews(item);
    const label = topicLabels[topic];
    const date  = formatDate(item.published) || relativeTime(item.published);
    const snippet = item.snippet
      ? cleanText(item.snippet.replace(/<[^>]+>/g, '').substring(0, 180))
      : '';

    return `
      <div class="news-card topic-${topic}">
        <div class="news-header">
          <span class="news-topic-badge">${label}</span>
          <span class="news-source-badge">${escHtml(item.source || '')}</span>
        </div>
        <a class="news-title" href="${escHtml(item.url || '#')}" target="_blank" rel="noopener noreferrer">
          ${cleanText(item.title || 'Untitled')}
        </a>
        ${snippet ? `<p class="news-snippet">${snippet}</p>` : ''}
        <div class="news-footer">
          <span>${date}</span>
          <a href="${escHtml(item.url || '#')}" target="_blank" rel="noopener noreferrer" style="color:var(--cyan);font-size:10px;">Read →</a>
        </div>
      </div>
    `;
  }

  /* ── TICKER RENDERER ─────────────────────────────────────── */
  function renderTicker(newsItems) {
    const staticItems = [
      'AI/ML Hiring +88% YoY',
      'Amazon layoffs: 14,000+ roles eliminated',
      'eBay cuts 800 jobs (9% workforce)',
      'Software Engineers: +10% YoY',
      'Forward Deployed Engineers: 42x demand surge (LinkedIn)',
      'Entry-level tech down -73% (Ravio 2026)',
      'AI skills now in 58% of tech postings',
      'Cybersecurity: 750K unfilled US openings',
    ];

    const allItems = [
      ...staticItems,
      ...(newsItems || []).slice(0, 10).map(n => n.title || '').filter(Boolean),
    ];

    // Double for seamless loop
    const doubled = [...allItems, ...allItems];
    return doubled.map(t =>
      `<span class="ticker-item"><span class="ticker-dot"></span>${escHtml(t)}</span>`
    ).join('');
  }

  /* ── UTILS ───────────────────────────────────────────────── */
  function decodeHtmlEntities(str) {
    if (!str) return '';
    const txt = document.createElement('textarea');
    txt.innerHTML = str;
    return txt.value;
  }

  function escHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function cleanText(str) {
    return escHtml(decodeHtmlEntities(str));
  }

  function skeletons(n, cls = 'skeleton-card') {
    return Array(n).fill(`<div class="skeleton ${cls}"></div>`).join('');
  }

  return {
    fetchJobs,
    fetchNews,
    relativeTime,
    formatDate,
    categorizeNews,
    renderJobCard,
    renderNewsCard,
    renderTicker,
    skeletons,
    escHtml,
  };
})();
