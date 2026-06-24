/* global chrome */
'use strict';

// ── ATS detection ───────────────────────────────────────────────────────────
const ATS_MAP = {
  greenhouse:       [/boards\.greenhouse\.io/, /app\.greenhouse\.io/],
  lever:            [/jobs\.lever\.co/],
  workday:          [/\.workday\.com/, /\.myworkdayjobs\.com/],
  ashby:            [/jobs\.ashbyhq\.com/],
  smartrecruiters:  [/jobs\.smartrecruiters\.com/],
  recruitee:        [/\.recruitee\.com/],
  jobvite:          [/\.jobvite\.com/],
  indeed:           [/indeed\.com\/(viewjob|apply)/],
  linkedin:         [/linkedin\.com\/jobs\/(view|easy-apply)/],
};

function detectATS(url) {
  for (const [name, patterns] of Object.entries(ATS_MAP)) {
    if (patterns.some(p => p.test(url))) return name;
  }
  return 'generic';
}

// ── Field selectors per ATS ─────────────────────────────────────────────────
const SELECTORS = {
  greenhouse: {
    first_name: '#first_name',
    last_name:  '#last_name',
    email:      '#email',
    phone:      '#phone',
    resume:     'input[type=file][id*=resume i], input[type=file][name*=resume i]',
    cover:      '#cover_letter_text, textarea[id*=cover i]',
    linkedin:   'input[placeholder*=linkedin i], input[id*=linkedin i]',
    website:    'input[placeholder*=website i], input[placeholder*=portfolio i]',
  },
  lever: {
    full_name:  'input[name=name]',
    email:      'input[name=email]',
    phone:      'input[name=phone]',
    resume:     '.resume-upload input[type=file], input[type=file]',
    cover:      'textarea[name=comments], textarea[placeholder*=cover i]',
    linkedin:   'input[name="urls[LinkedIn]"], input[placeholder*=linkedin i]',
    website:    'input[name="urls[Portfolio]"], input[placeholder*=portfolio i]',
  },
  ashby: {
    first_name: 'input[name=firstName], input[data-label*="First" i]',
    last_name:  'input[name=lastName],  input[data-label*="Last" i]',
    email:      'input[name=email], input[type=email]',
    phone:      'input[name=phone], input[type=tel]',
    resume:     'input[type=file]',
    linkedin:   'input[placeholder*=linkedin i]',
  },
  generic: {
    first_name: 'input[name*=first i]:not([type=hidden]), input[id*=first i]:not([type=hidden])',
    last_name:  'input[name*=last i]:not([type=hidden]),  input[id*=last i]:not([type=hidden])',
    full_name:  'input[name*="full" i][name*="name" i], input[placeholder*="full name" i]',
    email:      'input[type=email], input[name*=email i]',
    phone:      'input[type=tel], input[name*=phone i]',
    linkedin:   'input[name*=linkedin i], input[placeholder*=linkedin i]',
    website:    'input[name*=website i], input[name*=portfolio i]',
    cover:      'textarea[name*=cover i], textarea[id*=cover i], textarea[placeholder*=cover i]',
    resume:     'input[type=file]',
  },
};

// ── Trigger React/Angular state updates ─────────────────────────────────────
function setNativeValue(el, value) {
  const proto = el.tagName === 'TEXTAREA'
    ? window.HTMLTextAreaElement.prototype
    : window.HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
  if (setter) {
    setter.call(el, value);
  } else {
    el.value = value;
  }
  ['input', 'change', 'blur'].forEach(evt =>
    el.dispatchEvent(new Event(evt, { bubbles: true }))
  );
}

function fillInput(selector, value) {
  const el = document.querySelector(selector);
  if (el && value) {
    setNativeValue(el, value);
    return true;
  }
  return false;
}

// ── File upload via DataTransfer ─────────────────────────────────────────────
function injectPdfIntoInput(input, base64, filename) {
  try {
    const binary = atob(base64);
    const bytes  = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const file = new File([bytes], filename, { type: 'application/pdf' });
    const dt   = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    ['change', 'input'].forEach(evt =>
      input.dispatchEvent(new Event(evt, { bubbles: true }))
    );
    return true;
  } catch {
    return false;
  }
}

// ── Message helper ───────────────────────────────────────────────────────────
function send(msg) {
  return new Promise(resolve => chrome.runtime.sendMessage(msg, resolve));
}

// ── Panel state ──────────────────────────────────────────────────────────────
let state = {
  job:      null,
  profile:  null,
  ats:      detectATS(location.href),
  logs:     [],
  filling:  false,
  applied:  false,
};

// ── Panel DOM ────────────────────────────────────────────────────────────────
let panel = null;

function createPanel() {
  panel = document.createElement('div');
  panel.id = 'ae-panel';
  document.body.appendChild(panel);
  renderPanel();
}

function log(msg, type = '') {
  state.logs.push({ msg, type });
  if (state.logs.length > 30) state.logs.shift();
  updateLog();
}

function updateLog() {
  const el = document.getElementById('ae-log');
  if (!el) return;
  el.innerHTML = state.logs.map(l => {
    const cls = l.type === 'ok' ? 'ae-ok' : l.type === 'err' ? 'ae-err' : l.type === 'warn' ? 'ae-warn' : '';
    return `<div class="${cls}">${escHtml(l.msg)}</div>`;
  }).join('');
  el.scrollTop = el.scrollHeight;
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function fitClass(score) {
  if (score >= 75) return 'ae-fit-high';
  if (score >= 60) return 'ae-fit-mid';
  return 'ae-fit-low';
}

function renderPanel() {
  if (!panel) return;
  const { job, ats, filling, applied } = state;

  const jobHtml = job ? `
    <div class="ae-job-card">
      <div class="ae-job-title">${escHtml(job.title)}</div>
      <div class="ae-job-company">${escHtml(job.company)}</div>
      ${job.fit_score ? `<span class="ae-fit-badge ${fitClass(job.fit_score)}">${job.fit_score}% match</span>` : ''}
    </div>
  ` : `
    <div class="ae-job-card">
      <div class="ae-job-company">No matching job found in DB</div>
      <div style="font-size:11px;color:#64748b;margin-top:4px;">
        Run the pipeline first, or open a job from the popup
      </div>
    </div>
  `;

  panel.innerHTML = `
    <div id="ae-header">
      <span class="ae-logo">⚡ Apply Easy</span>
      <button class="ae-toggle" id="ae-toggle-btn">◀</button>
    </div>
    <div id="ae-body">
      <div class="ae-section-label">Detected ATS: ${ats}</div>
      ${jobHtml}
      <hr class="ae-divider">
      <div class="ae-section-label">Actions</div>
      <button class="ae-btn ae-btn-primary" id="ae-fill-profile"
        ${filling || !job ? 'disabled' : ''}>
        ${filling ? '<span class="ae-spinner"></span>' : '📋'} Fill Profile Fields
      </button>
      <button class="ae-btn ae-btn-secondary" id="ae-fill-ai"
        ${filling || !job ? 'disabled' : ''}>
        ${filling ? '<span class="ae-spinner"></span>' : '🤖'} AI-fill Text Questions
      </button>
      <button class="ae-btn ae-btn-warning" id="ae-upload-resume"
        ${!job ? 'disabled' : ''}>
        📄 Upload Resume PDF
      </button>
      <button class="ae-btn ae-btn-success" id="ae-mark-applied"
        ${!job || applied ? 'disabled' : ''}>
        ${applied ? '✅ Marked Applied' : '✓ Mark as Applied'}
      </button>
      <hr class="ae-divider">
      <div class="ae-section-label">Log</div>
      <div class="ae-log" id="ae-log"></div>
    </div>
  `;

  document.getElementById('ae-toggle-btn').onclick = togglePanel;
  document.getElementById('ae-header').onclick = (e) => {
    if (e.target.id !== 'ae-toggle-btn') togglePanel();
  };
  if (job) {
    document.getElementById('ae-fill-profile').onclick  = fillProfileFields;
    document.getElementById('ae-fill-ai').onclick       = fillAIFields;
    document.getElementById('ae-upload-resume').onclick = uploadResume;
    document.getElementById('ae-mark-applied').onclick  = markApplied;
  }
  updateLog();
}

function togglePanel() {
  panel.classList.toggle('ae-minimized');
  const btn = document.getElementById('ae-toggle-btn');
  if (btn) btn.textContent = panel.classList.contains('ae-minimized') ? '▶' : '◀';
}

// ── Fill: profile fields ─────────────────────────────────────────────────────
async function fillProfileFields() {
  if (!state.profile || !state.job) return;
  state.filling = true;
  renderPanel();

  const p    = state.profile;
  const sel  = { ...SELECTORS.generic, ...(SELECTORS[state.ats] || {}) };
  let filled = 0;

  const tryFill = (key, value) => {
    const s = sel[key];
    if (s && fillInput(s, value)) { filled++; log(`✓ ${key}`, 'ok'); }
  };

  if (sel.full_name) {
    tryFill('full_name', p.full_name);
  } else {
    tryFill('first_name', p.first_name);
    tryFill('last_name',  p.last_name);
  }

  tryFill('email',    p.email);
  tryFill('phone',    p.phone);
  tryFill('linkedin', p.linkedin_url);
  tryFill('website',  p.github_url);

  // Cover letter text
  if (state.job.cover_letter) {
    const coverSel = sel.cover;
    if (coverSel && fillInput(coverSel, state.job.cover_letter)) {
      filled++;
      log('✓ cover letter', 'ok');
    }
  }

  // Common dropdowns / radio groups
  fillSelectByLabel('country',  p.country);
  fillSelectByLabel('authorize', p.work_authorization === 'Yes' ? 'Yes' : 'No');

  log(`Profile fill done — ${filled} fields`, 'ok');
  state.filling = false;
  renderPanel();
}

function fillSelectByLabel(keyword, value) {
  document.querySelectorAll('select').forEach(sel => {
    const label = (sel.getAttribute('aria-label') || sel.id || sel.name || '').toLowerCase();
    if (label.includes(keyword.toLowerCase())) {
      const opt = [...sel.options].find(o =>
        o.text.toLowerCase().includes(value.toLowerCase()) ||
        o.value.toLowerCase().includes(value.toLowerCase())
      );
      if (opt) {
        sel.value = opt.value;
        sel.dispatchEvent(new Event('change', { bubbles: true }));
      }
    }
  });
}

// ── Fill: AI text questions ──────────────────────────────────────────────────
async function fillAIFields() {
  if (!state.job) return;
  state.filling = true;
  renderPanel();

  // Collect text/textarea fields that look like open questions (not name/email/phone)
  const skipPatterns = /name|email|phone|address|city|zip|linkedin|github|url|website|date|degree|gpa|salary/i;

  const candidates = [];
  document.querySelectorAll('textarea, input[type=text]').forEach(el => {
    if (el.offsetParent === null) return; // hidden
    const label = getFieldLabel(el);
    if (!label || skipPatterns.test(label)) return;
    if (el.value && el.value.trim().length > 5) return; // already filled
    candidates.push({ el, label });
  });

  if (candidates.length === 0) {
    log('No open-question fields found', 'warn');
    state.filling = false;
    renderPanel();
    return;
  }

  log(`Found ${candidates.length} question field(s)…`);

  for (const { el, label } of candidates) {
    log(`AI → "${label.slice(0, 40)}"…`);
    const answer = await send({
      type: 'FILL_FIELD',
      jobId: state.job.job_id,
      label,
      context: document.title,
    });
    if (answer) {
      setNativeValue(el, answer);
      log(`✓ filled: "${label.slice(0, 30)}"`, 'ok');
    } else {
      log(`✗ no answer for: "${label.slice(0, 30)}"`, 'err');
    }
  }

  log('AI fill complete', 'ok');
  state.filling = false;
  renderPanel();
}

function getFieldLabel(el) {
  // 1. <label for=id>
  if (el.id) {
    const lbl = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
    if (lbl) return lbl.innerText.trim();
  }
  // 2. aria-label
  if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
  // 3. placeholder
  if (el.placeholder) return el.placeholder;
  // 4. Walk up to find parent label text
  let node = el.parentElement;
  for (let i = 0; i < 5; i++) {
    if (!node) break;
    const text = node.querySelector('label, legend, [class*=label]');
    if (text) return text.innerText.trim();
    node = node.parentElement;
  }
  return '';
}

// ── Upload resume PDF ────────────────────────────────────────────────────────
async function uploadResume() {
  const fileInputs = document.querySelectorAll('input[type=file]');
  const resumeInput = [...fileInputs].find(inp => {
    const name = (inp.name + inp.id + inp.getAttribute('accept') || '').toLowerCase();
    return name.includes('resume') || name.includes('cv') || inp === fileInputs[0];
  });

  if (!resumeInput) {
    log('No file input found on page', 'err');
    return;
  }

  log('Fetching PDF from local API…');
  const pdf = await send({ type: 'FETCH_PDF_BLOB', jobId: state.job.job_id });

  if (!pdf) {
    log('PDF not found — run --process first', 'err');
    return;
  }

  const ok = injectPdfIntoInput(resumeInput, pdf.base64, pdf.filename);
  if (ok) {
    log(`✓ Uploaded ${pdf.filename}`, 'ok');
  } else {
    log('PDF injection failed — upload manually', 'warn');
    // Highlight the input so user can upload manually
    resumeInput.style.outline = '3px solid #6366f1';
    resumeInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

// ── Mark applied ─────────────────────────────────────────────────────────────
async function markApplied() {
  if (!state.job) return;
  const result = await send({
    type:  'MARK_APPLIED',
    jobId: state.job.job_id,
    notes: `Applied via Chrome extension on ${new Date().toLocaleDateString()}`,
  });
  if (result && result.ok) {
    state.applied = true;
    log('✓ Marked as applied in DB', 'ok');
    renderPanel();
  } else {
    log('Failed to mark applied', 'err');
  }
}

// ── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  // Small delay to let SPA frameworks mount their DOM
  await new Promise(r => setTimeout(r, 1500));

  createPanel();
  log('Detecting page…');

  // Load profile
  state.profile = await send({ type: 'FETCH_PROFILE' });

  // Try to find matching job
  state.job = await send({ type: 'FETCH_JOB_BY_URL', url: location.href });

  if (state.job) {
    log(`Matched: ${state.job.title} @ ${state.job.company}`, 'ok');
  } else {
    log('No matched job in DB', 'warn');
  }

  renderPanel();
}

// Only run on pages that look like actual application forms
const isAppPage = () => {
  const url = location.href;
  return (
    /\/apply|\/application|\/job\/|\/jobs\/|viewjob|easy-apply/i.test(url) ||
    Object.values(ATS_MAP).flat().some(p => p.test(url))
  );
};

if (isAppPage()) {
  init();
}
