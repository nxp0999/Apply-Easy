import React, { useState, useEffect, useRef } from 'react';
import { subscribeToLogs } from './api';

const MAX_LINES = 200;

const LiveLogs = () => {
  const [lines,    setLines]    = useState([]);
  const [paused,   setPaused]   = useState(false);
  const [connected, setConnected] = useState(false);
  const bottomRef  = useRef(null);
  const pausedRef  = useRef(false);

  pausedRef.current = paused;

  useEffect(() => {
    const es = subscribeToLogs((line) => {
      setConnected(true);
      if (!pausedRef.current) {
        setLines(prev => {
          const next = [...prev, line];
          return next.length > MAX_LINES ? next.slice(-MAX_LINES) : next;
        });
      }
    });
    return () => es.close();
  }, []);

  useEffect(() => {
    if (!paused) bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [lines, paused]);

  const levelColor = (line) => {
    if (line.includes('ERROR') || line.includes('✗'))  return '#f87171';
    if (line.includes('WARNING') || line.includes('⚠')) return '#fbbf24';
    if (line.includes('✓') || line.includes('Applied')) return '#4ade80';
    if (line.includes('==='))                           return '#a78bfa';
    return '#94a3b8';
  };

  return (
    <div className="log-panel">
      <div className="log-header">
        <span className="log-title">
          <span className={`log-dot ${connected ? 'live' : 'dead'}`} />
          Live Pipeline Log
        </span>
        <div className="log-actions">
          <button className="log-btn" onClick={() => setPaused(p => !p)}>
            {paused ? '▶ Resume' : '⏸ Pause'}
          </button>
          <button className="log-btn" onClick={() => setLines([])}>Clear</button>
        </div>
      </div>
      <div className="log-body">
        {lines.length === 0
          ? <span className="log-empty">Waiting for pipeline activity…</span>
          : lines.map((line, i) => (
              <div key={i} className="log-line" style={{ color: levelColor(line) }}>
                {line}
              </div>
            ))
        }
        <div ref={bottomRef} />
      </div>
    </div>
  );
};

export default LiveLogs;
