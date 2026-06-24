'use strict';

const API = 'http://localhost:8765';

// ── Message router ─────────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'FETCH_JOB_BY_URL') {
    fetchJobByUrl(msg.url).then(sendResponse);
    return true;
  }
  if (msg.type === 'FETCH_PROFILE') {
    fetchProfile().then(sendResponse);
    return true;
  }
  if (msg.type === 'FILL_FIELD') {
    fillField(msg.jobId, msg.label, msg.context).then(sendResponse);
    return true;
  }
  if (msg.type === 'FETCH_PDF_BLOB') {
    fetchPdfBlob(msg.jobId).then(sendResponse);
    return true;
  }
  if (msg.type === 'MARK_APPLIED') {
    markApplied(msg.jobId, msg.notes).then(sendResponse);
    return true;
  }
  if (msg.type === 'FETCH_PENDING') {
    fetchPending().then(sendResponse);
    return true;
  }
});

// ── API helpers ────────────────────────────────────────────────────────────
async function fetchJobByUrl(url) {
  try {
    const res = await fetch(`${API}/api/job-by-url?url=${encodeURIComponent(url)}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

async function fetchProfile() {
  try {
    const res = await fetch(`${API}/api/profile`);
    return await res.json();
  } catch {
    return {};
  }
}

async function fillField(jobId, label, context) {
  try {
    const res = await fetch(`${API}/api/fill-field`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, label, context }),
    });
    const data = await res.json();
    return data.answer || '';
  } catch {
    return '';
  }
}

async function fetchPdfBlob(jobId) {
  try {
    const res = await fetch(`${API}/api/pdf/${jobId}`);
    if (!res.ok) return null;
    const buffer = await res.arrayBuffer();
    // Return as base64 so it can cross the message boundary
    const bytes = new Uint8Array(buffer);
    let binary = '';
    bytes.forEach(b => (binary += String.fromCharCode(b)));
    return {
      base64: btoa(binary),
      filename: res.headers.get('Content-Disposition')?.match(/filename="?([^"]+)"?/)?.[1]
                || 'resume_tailored.pdf',
    };
  } catch {
    return null;
  }
}

async function markApplied(jobId, notes) {
  try {
    const res = await fetch(`${API}/api/mark-applied/${jobId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes }),
    });
    return await res.json();
  } catch {
    return { ok: false };
  }
}

async function fetchPending() {
  try {
    const res = await fetch(`${API}/api/pending-jobs`);
    return await res.json();
  } catch {
    return [];
  }
}
