import React from 'react';
import Chart from 'react-apexcharts';

const FitScoreDistributionChart = ({ jobs }) => {
  const buckets = [0, 0, 0, 0, 0]; // 0-20, 21-40, 41-60, 61-80, 81-100
  (jobs || []).forEach(j => {
    const score = j.fit_score || 0;
    buckets[Math.min(Math.floor(score / 20), 4)]++;
  });

  const options = {
    chart: { type: 'bar', toolbar: { show: false }, background: 'transparent' },
    xaxis: { categories: ['0–20', '21–40', '41–60', '61–80', '81–100'] },
    yaxis: { labels: { style: { colors: '#9ca3af' } } },
    colors: ['#6366f1'],
    plotOptions: { bar: { borderRadius: 4, columnWidth: '55%' } },
    dataLabels: { enabled: false },
    grid: { borderColor: '#374151' },
    theme: { mode: 'dark' },
  };

  return (
    <div className="chart-card">
      <h3>Fit Score Distribution</h3>
      <Chart
        options={options}
        series={[{ name: 'Jobs', data: buckets }]}
        type="bar"
        height={220}
      />
    </div>
  );
};

export default FitScoreDistributionChart;
