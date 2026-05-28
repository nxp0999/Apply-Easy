// api.js — fetch data from the Python Flask server
// In dev (npm start), CRA proxies /api/* to localhost:8765 via package.json "proxy"
// In prod (npm run build), both are served from the same origin

export const getApplications = async () => {
  const res = await fetch('/api/jobs');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const getStats = async () => {
  const res = await fetch('/api/stats');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const runPipelineStep = async (cmd) => {
  const res = await fetch(`/api/run/${cmd}`, { method: 'POST' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

// Returns an EventSource; caller is responsible for closing it.
export const subscribeToLogs = (onMessage) => {
  const es = new EventSource('/api/logs');
  es.onmessage = (e) => { if (e.data) onMessage(e.data); };
  es.onerror   = ()  => es.close();
  return es;
};
