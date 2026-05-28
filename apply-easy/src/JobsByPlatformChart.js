import React from 'react';
import Chart from 'react-apexcharts';

const JobsByPlatformChart = ({ jobs }) => {
  const counts = {};
  (jobs || []).forEach(j => {
    const p = (j.platform || 'unknown').toLowerCase();
    counts[p] = (counts[p] || 0) + 1;
  });
  const labels = Object.keys(counts);
  const series = labels.map(l => counts[l]);

  const options = {
    chart: { type: 'donut', background: 'transparent' },
    labels,
    colors: ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#ddd6fe'],
    legend: { position: 'bottom', labels: { colors: '#d1d5db' } },
    dataLabels: { style: { colors: ['#fff'] } },
    theme: { mode: 'dark' },
  };

  return (
    <div className="chart-card">
      <h3>Jobs by Platform</h3>
      {series.length > 0 ? (
        <Chart options={options} series={series} type="donut" height={220} />
      ) : (
        <p className="empty">No data yet</p>
      )}
    </div>
  );
};

export default JobsByPlatformChart;
