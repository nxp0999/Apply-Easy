import React, { useState, useEffect, useRef, useCallback } from 'react';
import StatsCards from './StatsCards';
import FitScoreDistributionChart from './FitScoreDistributionChart';
import JobsByPlatformChart from './JobsByPlatformChart';
import ApplicationsTable from './ApplicationsTable';
import LiveLogs from './LiveLogs';
import { getApplications, getStats, runPipelineStep } from './api';
import './App.css';

const POLL_MS = 5000;

const App = () => {
  const [jobs,       setJobs]       = useState([]);
  const [stats,      setStats]      = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState(null);
  const [lastSync,   setLastSync]   = useState(null);
  const [running,    setRunning]    = useState(null);
  const timerRef = useRef(null);

  const refresh = useCallback(() => {
    Promise.all([getApplications(), getStats()])
      .then(([j, s]) => { setJobs(j); setStats(s); setLastSync(new Date()); setError(null); })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh();
    timerRef.current = setInterval(refresh, POLL_MS);
    return () => clearInterval(timerRef.current);
  }, [refresh]);

  const trigger = async (cmd) => {
    setRunning(cmd);
    try { await runPipelineStep(cmd); }
    catch (e) { setError(e.message); }
    finally { setTimeout(() => setRunning(null), 2000); }
  };

  const STEPS = ['scrape', 'classify', 'process', 'dry-run', 'apply'];

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-inner">
          <h1>Apply Easy</h1>
          <span className="subtitle">Automated job application tracker</span>
          {lastSync && (
            <span className="last-sync">↻ {lastSync.toLocaleTimeString()}</span>
          )}
        </div>
        <div className="pipeline-btns">
          {STEPS.map(s => (
            <button
              key={s}
              className={`pipe-btn ${running === s ? 'running' : ''}`}
              onClick={() => trigger(s)}
              disabled={!!running}
            >
              {running === s ? '⏳' : '▶'} {s}
            </button>
          ))}
        </div>
      </header>

      <main className="app-main">
        <StatsCards stats={stats} />

        {loading && <p className="status-msg">Loading jobs…</p>}
        {error   && <p className="status-msg error">Error: {error}</p>}

        {!loading && !error && (
          <>
            <div className="charts-row">
              <FitScoreDistributionChart jobs={jobs} />
              <JobsByPlatformChart       jobs={jobs} />
            </div>
            <ApplicationsTable jobs={jobs} />
          </>
        )}

        <LiveLogs />
      </main>
    </div>
  );
};

export default App;
