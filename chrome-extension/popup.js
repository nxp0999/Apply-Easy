'use strict';

const API = 'http://localhost:8765';

// Role cluster keyword map (mirrors config.py ROLE_CLUSTERS)
const CLUSTER_KEYWORDS = {
  ml_ai:            ['data scientist','machine learning','ml engineer','ai engineer','nlp','deep learning','applied scientist','research scientist'],
  data_engineering: ['data engineer','big data','analytics engineer','etl','platform engineer'],
  analytics_bi:     ['business intelligence','data analyst','bi engineer','business analyst'],
  entry_ds:         ['associate data','junior data','junior ml','entry level data'],
  python_dev:       ['python developer','software engineer data','backend data'],
};

function guessCluster(title) {
  const t = title.toLowerCase();
  for (const [key, kws] of Object.entries(CLUSTER_KEYWORDS)) {
    if (kws.some(k => t.includes(k))) return key;
  }
  return null;
}

let allJobs = [];

// ── Load jobs ────────────────────────────────────────────────────────────────
async function loadJobs() {
  setStatus('checking');
  document.getElementById('job-count').textContent = 'Loading…';

  try {
    const res = await fetch(`${API}/api/pending-jobs`);
    if (!res.ok) throw new Error('API unreachable');
    allJobs = await res.json();
    setStatus('ok');
    renderList();
  } catch {
    setStatus('err');
    document.getElementById('job-count').textContent = 'Dashboard offline';
    document.getElementById('job-list').innerHTML =
      '<div class="empty">Start the dashboard:<br><code>python dashboard.py</code></div>';
  }
}

// ── Filter + render ──────────────────────────────────────────────────────────
function renderList() {
  const search   = document.getElementById('search').value.toLowerCase();
  const role     = document.getElementById('filter-role').value;
  const platform = document.getElementById('filter-platform').value;
  const minFit   = parseInt(document.getElementById('filter-fit').value) || 0;
  const applyType= document.getElementById('filter-type').value;

  const filtered = allJobs.filter(j => {
    if (search && !`${j.title} ${j.company}`.toLowerCase().includes(search)) return false;
    if (platform && j.platform !== platform) return false;
    if (minFit && (j.fit_score || 0) < minFit) return false;
    if (applyType && j.apply_type !== applyType) return false;
    if (role && guessCluster(j.title) !== role) return false;
    return true;
  });

  document.getElementById('job-count').textContent =
    `${filtered.length} of ${allJobs.length} jobs`;

  const list = document.getElementById('job-list');

  if (!filtered.length) {
    list.innerHTML = '<div class="empty">No jobs match your filters.<br>Try adjusting the search or run the pipeline.</div>';
    return;
  }

  list.innerHTML = filtered.map(j => {
    const score = j.fit_score;
    const fitCls = score >= 75 ? 'fit-high' : score >= 60 ? 'fit-mid' : score ? 'fit-low' : 'fit-none';
    const fitLabel = score ? `${score}%` : '—';
    const typeCls  = j.apply_type === 'easy' ? 'type-easy' : 'type-full_form';
    const typeLabel = j.apply_type === 'easy' ? 'Easy' : 'Form';
    const salaryHtml = (j.salary_min || j.salary_max)
      ? `<span class="salary-chip">₹${fmt(j.salary_min)}${j.salary_max ? '–'+fmt(j.salary_max) : '+'}</span>`
      : '';
    const url = j.apply_url_direct || j.apply_url || '#';

    return `
      <a class="job-card" href="${escAttr(url)}" target="_blank" data-id="${escAttr(j.job_id)}">
        <div class="job-title">${escHtml(j.title)}</div>
        <div class="job-meta">
          ${escHtml(j.company)}
          <span class="type-chip ${typeCls}">${typeLabel}</span>
          ${salaryHtml}
        </div>
        <div class="fit-badge ${fitCls}">${fitLabel}</div>
      </a>
    `;
  }).join('');
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(n) {
  if (!n) return '';
  return n >= 100000 ? (n/100000).toFixed(1)+'L' : n >= 1000 ? (n/1000).toFixed(0)+'K' : n;
}

function escHtml(s)  { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function escAttr(s)  { return String(s||'').replace(/"/g,'&quot;'); }

function setStatus(state) {
  const dot = document.getElementById('status-dot');
  dot.className = 'dot dot-' + state;
  dot.title = state === 'ok' ? 'Connected' : state === 'err' ? 'Dashboard offline' : 'Checking…';
}

// ── Event wiring ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadJobs();

  document.getElementById('btn-refresh').addEventListener('click', loadJobs);

  ['search','filter-role','filter-platform','filter-fit','filter-type'].forEach(id => {
    document.getElementById(id).addEventListener('input', renderList);
    document.getElementById(id).addEventListener('change', renderList);
  });
});
