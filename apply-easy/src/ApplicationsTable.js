import React, { useState } from 'react';

const STATUS_MAP = { 0: 'Pending', 1: 'Applied', 2: 'Skipped', 3: 'Error' };
const STATUS_COLOR = { 0: '#f59e0b', 1: '#22c55e', 2: '#9ca3af', 3: '#ef4444' };
const TYPE_COLOR = { easy: '#22c55e', full_form: '#f59e0b', unknown: '#6b7280' };

const ApplicationsTable = ({ jobs }) => {
  const [search, setSearch]   = useState('');
  const [statusF, setStatusF] = useState('');
  const [typeF,   setTypeF]   = useState('');
  const [sortKey, setSortKey] = useState('fit_score');
  const [sortDir, setSortDir] = useState('desc');

  const toggleSort = key => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const filtered = (jobs || [])
    .filter(j => {
      const q = search.toLowerCase();
      const matchSearch = !q ||
        (j.title   || '').toLowerCase().includes(q) ||
        (j.company || '').toLowerCase().includes(q);
      const matchStatus = !statusF || String(j.applied) === statusF;
      const matchType   = !typeF   || (j.apply_type || '') === typeF;
      return matchSearch && matchStatus && matchType;
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
          <option value="unknown">Unknown</option>
        </select>
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
              <Th col="apply_type"  label="Apply Type" />
              <Th col="fit_score"   label="Fit" />
              <th>Claude Q</th>
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
