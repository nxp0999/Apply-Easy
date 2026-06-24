import React, { useState } from 'react';

const STATUS_MAP = { 0: 'Pending', 1: 'Applied', 2: 'Skipped', 3: 'Error' };
const STATUS_COLOR = { 0: '#f59e0b', 1: '#22c55e', 2: '#9ca3af', 3: '#ef4444' };
const TYPE_COLOR = { easy: '#22c55e', full_form: '#f59e0b', unknown: '#6b7280' };

const CLUSTER_KEYWORDS = {
  ml_ai:            ['data scientist','machine learning','ml engineer','ai engineer','nlp','deep learning'],
  data_engineering: ['data engineer','big data','analytics engineer','etl'],
  analytics_bi:     ['business intelligence','data analyst','bi engineer'],
  entry_ds:         ['associate data','junior data','junior ml'],
  python_dev:       ['python developer','software engineer data'],
};

function guessCluster(title = '') {
  const t = title.toLowerCase();
  for (const [key, kws] of Object.entries(CLUSTER_KEYWORDS)) {
    if (kws.some(k => t.includes(k))) return key;
  }
  return null;
}

function fmtSalary(min, max) {
  const fmt = n => n >= 100000 ? (n/100000).toFixed(1)+'L' : n >= 1000 ? Math.round(n/1000)+'K' : n;
  if (min && max) return `₹${fmt(min)}–${fmt(max)}`;
  if (min) return `₹${fmt(min)}+`;
  if (max) return `≤₹${fmt(max)}`;
  return '—';
}

const ApplicationsTable = ({ jobs }) => {
  const [search,    setSearch]    = useState('');
  const [statusF,   setStatusF]   = useState('');
  const [typeF,     setTypeF]     = useState('');
  const [platformF, setPlatformF] = useState('');
  const [roleF,     setRoleF]     = useState('');
  const [minFit,    setMinFit]    = useState('');
  const [hasSalary, setHasSalary] = useState(false);
  const [sortKey,   setSortKey]   = useState('fit_score');
  const [sortDir,   setSortDir]   = useState('desc');

  const toggleSort = key => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const filtered = (jobs || [])
    .filter(j => {
      const q = search.toLowerCase();
      if (q && !(j.title||'').toLowerCase().includes(q) && !(j.company||'').toLowerCase().includes(q)) return false;
      if (statusF   && String(j.applied) !== statusF)         return false;
      if (typeF     && (j.apply_type||'') !== typeF)          return false;
      if (platformF && (j.platform||'') !== platformF)        return false;
      if (roleF     && guessCluster(j.title) !== roleF)       return false;
      if (minFit    && (j.fit_score||0) < Number(minFit))     return false;
      if (hasSalary && !j.salary_min && !j.salary_max)        return false;
      return true;
    })
    .sort((a, b) => {
      const av = a[sortKey] ?? -1;
      const bv = b[sortKey] ?? -1;
      return sortDir === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
    });

  const Th = ({ col, label }) => (
    <th onClick={() => toggleSort(col)} className="sortable">
      {label}{sortKey === col ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
    </th>
  );

  return (
    <div className="table-wrap">
      <div className="table-controls">
        <input
          className="search-input"
          type="text"
          placeholder="Search title or company…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <select className="filter-select" value={statusF} onChange={e => setStatusF(e.target.value)}>
          <option value="">All statuses</option>
          <option value="0">Pending</option>
          <option value="1">Applied</option>
          <option value="2">Skipped</option>
          <option value="3">Error</option>
        </select>
        <select className="filter-select" value={typeF} onChange={e => setTypeF(e.target.value)}>
          <option value="">All types</option>
          <option value="easy">Easy Apply</option>
          <option value="full_form">Full Form</option>
        </select>
        <select className="filter-select" value={platformF} onChange={e => setPlatformF(e.target.value)}>
          <option value="">All platforms</option>
          <option value="linkedin">LinkedIn</option>
          <option value="indeed">Indeed</option>
        </select>
        <select className="filter-select" value={roleF} onChange={e => setRoleF(e.target.value)}>
          <option value="">All roles</option>
          <option value="ml_ai">ML / AI</option>
          <option value="data_engineering">Data Engineering</option>
          <option value="analytics_bi">Analytics / BI</option>
          <option value="entry_ds">Entry DS</option>
          <option value="python_dev">Python Dev</option>
        </select>
        <input
          className="filter-select"
          type="number"
          min="0" max="100"
          placeholder="Min fit %"
          value={minFit}
          onChange={e => setMinFit(e.target.value)}
          style={{ width: '90px' }}
        />
        <label className="salary-toggle">
          <input type="checkbox" checked={hasSalary} onChange={e => setHasSalary(e.target.checked)} />
          {' '}Has salary
        </label>
        <span className="row-count">{filtered.length} jobs</span>
      </div>

      <div className="table-scroll">
        <table className="apps-table">
          <thead>
            <tr>
              <Th col="platform"    label="Platform" />
              <Th col="title"       label="Title" />
              <Th col="company"     label="Company" />
              <Th col="date_posted" label="Posted" />
              <Th col="apply_type"  label="Type" />
              <Th col="fit_score"   label="Fit" />
              <th>Claude Q</th>
              <Th col="salary_min"  label="Salary" />
              <Th col="applied"     label="Status" />
              <th>Link</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(j => {
              const quality = (() => { try { return JSON.parse(j.resume_quality || '{}'); } catch { return {}; } })();
              return (
                <tr key={j.job_id}>
                  <td className="cap">{j.platform}</td>
                  <td className="title-cell">{j.title}</td>
                  <td>{j.company}</td>
                  <td className="num mono">{j.date_posted ? j.date_posted.slice(5) : '—'}</td>
                  <td>
                    <span className="badge" style={{ background: TYPE_COLOR[j.apply_type] || '#374151' }}>
                      {j.apply_type || '?'}
                    </span>
                  </td>
                  <td className="num">
                    {j.fit_score
                      ? <span style={{ color: j.fit_score >= 70 ? '#22c55e' : j.fit_score >= 50 ? '#f59e0b' : '#ef4444' }}>
                          {j.fit_score}
                        </span>
                      : '—'}
                  </td>
                  <td className="num">{quality.overall || '—'}</td>
                  <td className="num mono" style={{ color: '#4ade80', fontSize: '11px' }}>
                    {fmtSalary(j.salary_min, j.salary_max)}
                  </td>
                  <td>
                    <span className="badge" style={{ background: STATUS_COLOR[j.applied] || '#374151' }}>
                      {STATUS_MAP[j.applied] || j.applied}
                    </span>
                  </td>
                  <td>
                    {j.apply_url &&
                      <a href={j.apply_url} target="_blank" rel="noopener noreferrer" className="apply-link">
                        Apply →
                      </a>
                    }
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ApplicationsTable;
