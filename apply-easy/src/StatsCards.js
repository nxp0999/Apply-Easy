import React from 'react';

const StatsCards = ({ stats }) => {
  const cards = [
    { label: 'Total Jobs',   value: stats?.total      ?? '—', color: '#6366f1' },
    { label: 'Pending',      value: stats?.pending     ?? '—', color: '#f59e0b' },
    { label: 'Applied',      value: stats?.applied     ?? '—', color: '#22c55e' },
    { label: 'Skipped',      value: stats?.skipped     ?? '—', color: '#ef4444' },
    { label: 'Easy Apply',   value: stats?.easy_apply  ?? '—', color: '#8b5cf6' },
    { label: 'Avg Fit Score',value: stats?.avg_fit     ?? '—', color: '#0ea5e9' },
  ];

  return (
    <div className="stats-grid">
      {cards.map(({ label, value, color }) => (
        <div className="stat-card" key={label} style={{ borderTop: `3px solid ${color}` }}>
          <span className="stat-value">{value}</span>
          <span className="stat-label">{label}</span>
        </div>
      ))}
    </div>
  );
};

export default StatsCards;
