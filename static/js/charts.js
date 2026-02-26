/* ============================================================
   CHARTS.JS — All Chart.js Definitions for Dashboard
   ============================================================ */

const Charts = (() => {
  /* ── COMMON DEFAULTS ────────────────────────────────────── */
  Chart.defaults.color = '#5A6480';
  Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
  Chart.defaults.font.family = "'JetBrains Mono', monospace";

  const CYAN    = '#00E5FF';
  const MAGENTA = '#FF2E97';
  const LIME    = '#39FF14';
  const AMBER   = '#FFB300';
  const PURPLE  = '#9D4EFF';

  function gridOpts(color = 'rgba(255,255,255,0.04)') {
    return { color, drawBorder: false };
  }

  function tooltipOpts(extra = {}) {
    return {
      backgroundColor: 'rgba(12,15,26,0.95)',
      titleColor: '#F0F4FF',
      bodyColor: '#5A6480',
      borderColor: 'rgba(255,255,255,0.1)',
      borderWidth: 1,
      padding: 10,
      cornerRadius: 6,
      titleFont: { family: "'Instrument Sans', sans-serif", weight: '700', size: 13 },
      bodyFont: { family: "'JetBrains Mono', monospace", size: 11 },
      ...extra,
    };
  }

  function baseScales() {
    return {
      x: {
        grid: gridOpts(),
        ticks: { color: '#5A6480', font: { size: 10 } },
      },
      y: {
        grid: gridOpts(),
        ticks: { color: '#5A6480', font: { size: 10 } },
        border: { display: false },
      },
    };
  }

  /* ── 1. SALARY TRENDS LINE CHART ─────────────────────────── */
  function initSalaryChart(canvasId) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    return new Chart(ctx, {
      type: 'line',
      data: {
        labels: ['2019', '2020', '2021', '2022', '2023', '2024'],
        datasets: [{
          label: 'Avg Tech Salary ($)',
          data: [146104, 162175, 197043, 206895, 181861, 191681],
          borderColor: CYAN,
          backgroundColor: 'rgba(0,229,255,0.08)',
          pointBackgroundColor: CYAN,
          pointBorderColor: '#06080F',
          pointBorderWidth: 2,
          pointRadius: 5,
          pointHoverRadius: 7,
          fill: true,
          tension: 0.4,
          borderWidth: 2.5,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            ...tooltipOpts(),
            callbacks: {
              label: (ctx) => ` $${ctx.parsed.y.toLocaleString()}`,
            },
          },
        },
        scales: {
          ...baseScales(),
          y: {
            ...baseScales().y,
            ticks: {
              color: '#5A6480',
              font: { size: 10 },
              callback: v => `$${(v/1000).toFixed(0)}K`,
            },
            min: 130000,
          },
        },
      },
    });
  }

  /* ── 2. FASTEST GROWING ROLES HORIZONTAL BAR ────────────── */
  function initGrowingRolesChart(canvasId) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    return new Chart(ctx, {
      type: 'bar',
      data: {
        labels: [
          'AI Engineer',
          'AI Content Creator',
          'AI Solutions Architect',
          'Prompt Engineer',
          'AI Systems Designer',
          'AI Product Manager',
        ],
        datasets: [{
          label: 'YoY Growth (%)',
          data: [143.2, 134.5, 109.3, 95.5, 92.6, 89.7],
          backgroundColor: [
            'rgba(0,229,255,0.75)',
            'rgba(0,229,255,0.65)',
            'rgba(0,229,255,0.55)',
            'rgba(0,229,255,0.45)',
            'rgba(0,229,255,0.35)',
            'rgba(0,229,255,0.28)',
          ],
          borderColor: 'transparent',
          borderRadius: 4,
          borderSkipped: false,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: {
            ...tooltipOpts(),
            callbacks: { label: (c) => ` +${c.parsed.x}% YoY` },
          },
        },
        scales: {
          x: {
            ...baseScales().x,
            ticks: {
              color: '#5A6480',
              font: { size: 10 },
              callback: v => `+${v}%`,
            },
          },
          y: {
            ...baseScales().y,
            ticks: { color: '#A0AABB', font: { size: 11 }, padding: 4 },
          },
        },
        layout: { padding: { left: 8 } },
      },
    });
  }

  /* ── 3. TOP PAYING ROLES BAR ─────────────────────────────── */
  function initSalaryRolesChart(canvasId) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    return new Chart(ctx, {
      type: 'bar',
      data: {
        labels: [
          'Cloud Architect',
          'Data Scientist',
          'ML Engineer',
          'Software Engineer',
          'Cybersecurity Eng',
          'DevOps Engineer',
        ],
        datasets: [{
          label: 'Avg Salary ($)',
          data: [201000, 166000, 166000, 161000, 149000, 141000],
          backgroundColor: [
            'rgba(255,179,0,0.8)',
            'rgba(255,179,0,0.65)',
            'rgba(255,179,0,0.55)',
            'rgba(255,179,0,0.45)',
            'rgba(255,179,0,0.35)',
            'rgba(255,179,0,0.28)',
          ],
          borderColor: 'transparent',
          borderRadius: 4,
          borderSkipped: false,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            ...tooltipOpts(),
            callbacks: { label: (c) => ` $${c.parsed.y.toLocaleString()}` },
          },
        },
        scales: {
          ...baseScales(),
          y: {
            ...baseScales().y,
            ticks: {
              color: '#5A6480',
              font: { size: 10 },
              callback: v => `$${(v/1000).toFixed(0)}K`,
            },
            min: 120000,
          },
        },
      },
    });
  }

  /* ── 4. TECH LAYOFFS TIMELINE (bar+line) ─────────────────── */
  function initLayoffsChart(canvasId) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    const labels = [
      '2022', 'Q1\'23', 'Q2\'23', 'Q3\'23', 'Q4\'23',
      'Q1\'24', 'Q2\'24', 'Q3\'24', 'Q4\'24',
      'Jan\'25','Feb\'25','Mar\'25','Apr\'25','May\'25','Jun\'25',
      'Jul\'25','Aug\'25','Sep\'25','Oct\'25','Nov\'25','Dec\'25',
      '2026 YTD',
    ];
    const data = [
      263000, 167600, 60000, 40000, 30000,
      57000, 43000, 30000, 12000,
      2400, 16200, 8800, 24500, 10400, 1600,
      16300, 6300, 4200, 18500, 8900, 300,
      50000,
    ];

    // Cumulative line
    let cum = 0;
    const cumData = data.map(v => { cum += v; return cum; });

    return new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            type: 'bar',
            label: 'Layoffs per Period',
            data,
            backgroundColor: data.map((_, i) =>
              i === labels.length - 1 ? 'rgba(255,179,0,0.8)' :
              i < 1 ? 'rgba(255,46,151,0.7)' :
              'rgba(255,46,151,0.5)'
            ),
            borderColor: 'transparent',
            borderRadius: 3,
            yAxisID: 'y',
          },
          {
            type: 'line',
            label: 'Cumulative',
            data: cumData,
            borderColor: CYAN,
            backgroundColor: 'transparent',
            pointRadius: 2,
            pointHoverRadius: 5,
            borderWidth: 1.5,
            tension: 0.4,
            yAxisID: 'y2',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: {
              color: '#5A6480',
              font: { size: 11 },
              boxWidth: 12,
              usePointStyle: true,
              padding: 16,
            },
          },
          tooltip: {
            ...tooltipOpts(),
            callbacks: {
              label: (c) => ` ${c.dataset.label}: ${c.parsed.y.toLocaleString()}`,
            },
          },
        },
        scales: {
          x: {
            grid: gridOpts(),
            ticks: { color: '#5A6480', font: { size: 9 }, maxRotation: 45 },
          },
          y: {
            grid: gridOpts(),
            ticks: {
              color: '#5A6480', font: { size: 9 },
              callback: v => `${(v/1000).toFixed(0)}K`,
            },
            position: 'left',
            border: { display: false },
          },
          y2: {
            grid: { display: false },
            ticks: {
              color: 'rgba(0,229,255,0.4)', font: { size: 9 },
              callback: v => `${(v/1000).toFixed(0)}K`,
            },
            position: 'right',
            border: { display: false },
          },
        },
      },
    });
  }

  /* ── 5. BLS 10-YEAR PROJECTIONS ─────────────────────────── */
  function initBLSChart(canvasId) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    return new Chart(ctx, {
      type: 'bar',
      data: {
        labels: [
          'Data Scientists',
          'Info Security Analysts',
          'Operations Research',
          'Computer Research Sci.',
          'Software Developers',
          'Computer/Math Total',
        ],
        datasets: [
          {
            label: 'Growth % (2024-2034)',
            data: [33.5, 28.5, 21.5, 19.7, 15.8, 10.1],
            backgroundColor: 'rgba(57,255,20,0.6)',
            borderColor: 'transparent',
            borderRadius: 4,
            yAxisID: 'y',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            ...tooltipOpts(),
            callbacks: { label: (c) => ` +${c.parsed.y}% growth` },
          },
        },
        scales: {
          x: {
            grid: gridOpts(),
            ticks: { color: '#5A6480', font: { size: 10 }, maxRotation: 20 },
          },
          y: {
            grid: gridOpts(),
            ticks: {
              color: '#5A6480', font: { size: 10 },
              callback: v => `+${v}%`,
            },
            border: { display: false },
          },
        },
      },
    });
  }

  /* ── DESTROY & REINIT GUARD ──────────────────────────────── */
  const registry = {};

  function init(id, fn) {
    if (registry[id]) {
      registry[id].destroy();
      delete registry[id];
    }
    const chart = fn(id);
    if (chart) registry[id] = chart;
    return chart;
  }

  return {
    initSalaryChart:     (id) => init(id, initSalaryChart),
    initGrowingRolesChart: (id) => init(id, initGrowingRolesChart),
    initSalaryRolesChart: (id) => init(id, initSalaryRolesChart),
    initLayoffsChart:    (id) => init(id, initLayoffsChart),
    initBLSChart:        (id) => init(id, initBLSChart),
  };
})();
