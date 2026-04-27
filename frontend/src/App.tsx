import React, { useState, useRef, useEffect, useCallback } from 'react';
import './index.css';

const API = 'http://127.0.0.1:8080';

// --- Types ---
interface MetricDetail {
  actual_pct: number;
  target_pct: number;
  variance_pct: number;
  actual_cost: number;
}

interface VenueBrief {
  venue_id: string;
  venue_name: string;
  week_ending: string;
  net_sales: number;
  prime: MetricDetail;
  labor: MetricDetail;
  food: MetricDetail;
  primary_driver: string;
  driver_detail: string;
  context_notes: string[];
}

interface ChatMessage {
  role: 'user' | 'agent';
  content: string;
  agent_name?: string;
}

// --- Session ID (persisted across page refreshes) ---
function getOrCreateSessionId(): string {
  const key = 'primeops_session_id';
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  const id = crypto.randomUUID();
  localStorage.setItem(key, id);
  return id;
}

// --- Upload Form ---
interface TheLabProps {
  onIngest: (salesFile: File, laborFile: File, purchasesFile: File, weekEnding: string) => void;
  isLoading: boolean;
  hasExistingData: boolean;
  onCancel: () => void;
}

const TheLab = ({ onIngest, isLoading, hasExistingData, onCancel }: TheLabProps) => {
  const [salesFile, setSalesFile] = useState<File | null>(null);
  const [laborFile, setLaborFile] = useState<File | null>(null);
  const [purchasesFile, setPurchasesFile] = useState<File | null>(null);
  const [weekEnding, setWeekEnding] = useState('2026-03-08');
  const allFilesSelected = salesFile && laborFile && purchasesFile;

  return (
    <div className="glass-card" style={{ maxWidth: '600px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <h2>The Lab</h2>
        {hasExistingData && (
          <button onClick={onCancel} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.85rem' }}>
            ← Back to Dashboard
          </button>
        )}
      </div>
      <p style={{ color: 'var(--text-secondary)' }}>Upload your weekly data files to run the Prime Cost engine.</p>

      <div style={{ marginTop: '2rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {[
          { label: 'POS Sales CSV (Toast)', setter: setSalesFile, file: salesFile },
          { label: 'Labor CSV (7shifts)', setter: setLaborFile, file: laborFile },
          { label: 'Purchases CSV (MarketMan)', setter: setPurchasesFile, file: purchasesFile },
        ].map(({ label, setter, file }) => (
          <div key={label}>
            <label style={{ display: 'block', marginBottom: '0.4rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{label}</label>
            <input type="file" accept=".csv" onChange={e => setter(e.target.files?.[0] ?? null)} style={{ width: '100%' }} />
            {file && <span style={{ fontSize: '0.75rem', color: 'var(--primary)' }}>✓ {file.name}</span>}
          </div>
        ))}

        <div>
          <label style={{ display: 'block', marginBottom: '0.4rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Week Ending</label>
          <input
            type="date"
            value={weekEnding}
            onChange={e => setWeekEnding(e.target.value)}
            style={{ width: '100%', padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--outline-variant)', background: 'transparent', color: 'inherit' }}
          />
        </div>
      </div>

      <button
        className="btn-primary"
        style={{ width: '100%', marginTop: '2rem' }}
        onClick={() => salesFile && laborFile && purchasesFile && onIngest(salesFile, laborFile, purchasesFile, weekEnding)}
        disabled={isLoading || !allFilesSelected}
      >
        {isLoading ? 'Crunching Data...' : 'Process via PrimeOps Engine'}
      </button>
    </div>
  );
};

// --- Metric Card ---
const MetricCard = ({ label, metric, invertGood }: { label: string; metric: MetricDetail; invertGood?: boolean }) => {
  const isGood = invertGood ? metric.variance_pct >= 0 : metric.variance_pct <= 0;
  return (
    <div className="glass-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{metric.actual_pct.toFixed(1)}%</div>
      <div className={`metric-variance ${isGood ? 'variance-good' : 'variance-bad'}`}>
        {Math.abs(metric.variance_pct).toFixed(1)}pp {metric.variance_pct <= 0 ? 'under' : 'over'} target
      </div>
      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
        ${metric.actual_cost.toLocaleString()} &nbsp;|&nbsp; target {metric.target_pct.toFixed(1)}%
      </div>
    </div>
  );
};

// --- Dashboard ---
interface DashboardProps {
  briefs: VenueBrief[];
  selectedIdx: number;
  onSelectVenue: (idx: number) => void;
  onUploadClick: () => void;
}

const MetricsDashboard = ({ briefs, selectedIdx, onSelectVenue, onUploadClick }: DashboardProps) => {
  const brief = briefs[selectedIdx];
  const isPrimeGood = brief.prime.variance_pct <= 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <h1 className="display-title" style={{ margin: 0 }}>{brief.venue_name}</h1>
          {briefs.length > 1 && (
            <select
              value={selectedIdx}
              onChange={e => onSelectVenue(Number(e.target.value))}
              style={{ padding: '0.4rem 0.8rem', borderRadius: '6px', border: '1px solid var(--outline-variant)', background: 'var(--surface)', color: 'inherit', cursor: 'pointer' }}
            >
              {briefs.map((b, i) => <option key={b.venue_id} value={i}>{b.venue_name}</option>)}
            </select>
          )}
        </div>
        <button
          onClick={onUploadClick}
          style={{ background: 'none', border: '1px solid var(--outline-variant)', color: 'var(--text-secondary)', borderRadius: '6px', padding: '0.4rem 0.8rem', cursor: 'pointer', fontSize: '0.8rem' }}
        >
          Upload New Week
        </button>
      </div>

      <p style={{ color: 'var(--text-secondary)', marginTop: '-1.5rem' }}>
        Week Ending: {brief.week_ending} &nbsp;|&nbsp; Net Sales: ${brief.net_sales.toLocaleString()}
      </p>

      {/* Metrics Grid */}
      <div className="metrics-grid">
        <MetricCard label="Prime Cost" metric={brief.prime} />
        <MetricCard label="Labor Cost" metric={brief.labor} />
        <MetricCard label="Food Cost" metric={brief.food} />
      </div>

      {/* Primary Driver */}
      <div className="glass-card">
        <h2 style={{ marginBottom: '1rem' }}>
          Primary Driver:{' '}
          <span style={{ textTransform: 'capitalize', color: isPrimeGood ? 'var(--primary)' : 'var(--error)' }}>
            {brief.primary_driver}
          </span>
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', lineHeight: '1.6' }}>
          {brief.driver_detail}
        </p>
      </div>

      {/* Agent Memory — context notes */}
      {brief.context_notes.length > 0 && (
        <div className="glass-card">
          <h2 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--primary)', display: 'inline-block', boxShadow: '0 0 8px var(--primary)' }} />
            Agent Memory
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {brief.context_notes.map((note, i) => (
              <div key={i} style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', paddingLeft: '1rem', borderLeft: '2px solid var(--outline-variant)', lineHeight: '1.5' }}>
                {note}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// --- Main App ---
function App() {
  const [briefs, setBriefs] = useState<VenueBrief[]>([]);
  const [selectedVenueIdx, setSelectedVenueIdx] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [isBootstrapping, setIsBootstrapping] = useState(true);

  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'agent', content: 'Hello. I am the PrimeOps Agentic Assistant. Ask me about Prime Cost, labor overtime, food spend, or how your venues compare.', agent_name: 'concierge' },
  ]);
  const [chatInput, setChatInput] = useState('');
  const [isChatting, setIsChatting] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const sessionId = useRef(getOrCreateSessionId()).current;

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  // Fetch brief (including context_notes) for a venue
  const fetchBrief = useCallback(async (venueId: string): Promise<VenueBrief | null> => {
    try {
      const r = await fetch(`${API}/brief/${venueId}`);
      if (!r.ok) return null;
      return await r.json();
    } catch { return null; }
  }, []);

  // Auto-load existing data on mount
  useEffect(() => {
    const bootstrap = async () => {
      try {
        const r = await fetch(`${API}/venues`);
        if (!r.ok) { setShowUpload(true); return; }
        const { venues } = await r.json();
        if (!venues?.length) { setShowUpload(true); return; }

        const loaded: VenueBrief[] = [];
        for (const v of venues) {
          const brief = await fetchBrief(v.id);
          if (brief && brief.net_sales > 0) loaded.push(brief);
        }

        if (loaded.length > 0) {
          setBriefs(loaded);
          setShowUpload(false);
        } else {
          setShowUpload(true);
        }
      } catch {
        setShowUpload(true);
      } finally {
        setIsBootstrapping(false);
      }
    };
    bootstrap();
  }, [fetchBrief]);

  // Refresh the active venue's brief (picks up new context notes after chat)
  const refreshActiveBrief = useCallback(async (venueId: string) => {
    const updated = await fetchBrief(venueId);
    if (updated) {
      setBriefs(prev => prev.map(b => b.venue_id === venueId ? updated : b));
    }
  }, [fetchBrief]);

  const handleIngest = async (salesFile: File, laborFile: File, purchasesFile: File, weekEnding: string) => {
    setIsLoading(true);
    try {
      const formData = new FormData();
      formData.append('sales_file', salesFile);
      formData.append('labor_file', laborFile);
      formData.append('purchases_file', purchasesFile);
      formData.append('week_ending', weekEnding);

      const r = await fetch(`${API}/upload`, { method: 'POST', body: formData });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail ?? `HTTP ${r.status}`);
      }

      const data = await r.json();
      // Fetch briefs (with context notes) for all returned venues
      const loaded: VenueBrief[] = [];
      for (const nugget of data.nuggets) {
        const brief = await fetchBrief(nugget.venue_id);
        if (brief) loaded.push(brief);
      }
      if (loaded.length > 0) {
        setBriefs(loaded);
        setSelectedVenueIdx(0);
        setShowUpload(false);
      }
    } catch (error) {
      alert(`Error: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async (e: React.SyntheticEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || isChatting) return;

    const userMessage = chatInput.trim();
    const activeVenueId = briefs[selectedVenueIdx]?.venue_id ?? null;

    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setChatInput('');
    setIsChatting(true);

    try {
      const r = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage, session_id: sessionId, venue_id: activeVenueId }),
      });
      if (!r.ok) throw new Error('Chat failed');
      const data = await r.json();
      setMessages(prev => [...prev, { role: 'agent', content: data.reply, agent_name: data.agent_name ?? 'assistant' }]);

      // Refresh active venue brief so new context notes appear immediately
      if (activeVenueId) await refreshActiveBrief(activeVenueId);
    } catch {
      setMessages(prev => [...prev, { role: 'agent', content: 'Error communicating with Agentic OS.' }]);
    } finally {
      setIsChatting(false);
    }
  };

  // Loading state
  if (isBootstrapping) {
    return (
      <div className="app-container" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ color: 'var(--text-secondary)' }}>Loading PrimeOps...</p>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Left: Dashboard or Upload */}
      <div className="dashboard-pane">
        {showUpload || briefs.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <TheLab
              onIngest={handleIngest}
              isLoading={isLoading}
              hasExistingData={briefs.length > 0}
              onCancel={() => setShowUpload(false)}
            />
          </div>
        ) : (
          <MetricsDashboard
            briefs={briefs}
            selectedIdx={selectedVenueIdx}
            onSelectVenue={setSelectedVenueIdx}
            onUploadClick={() => setShowUpload(true)}
          />
        )}
      </div>

      {/* Right: Chat Sidebar */}
      <div className="chat-pane">
        <div className="chat-header">
          <div className="agent-orb" />
          <h2>Agentic Assistant</h2>
        </div>

        <div className="chat-history">
          {messages.map((msg, idx) => (
            <div key={idx} className={`chat-message ${msg.role}`}>
              {msg.role === 'agent' && msg.agent_name && (
                <div style={{ fontSize: '0.7rem', color: 'var(--primary)', marginBottom: '0.25rem', textTransform: 'capitalize', opacity: 0.8 }}>
                  {msg.agent_name.replace(/_/g, ' ')}
                </div>
              )}
              <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
            </div>
          ))}
          {isChatting && (
            <div className="chat-message agent" style={{ opacity: 0.5 }}>
              <em>Thinking...</em>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className="chat-input-container" onSubmit={handleSendMessage} style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            type="text"
            className="chat-input"
            placeholder="Ask about prime cost, labor, food spend..."
            value={chatInput}
            onChange={e => setChatInput(e.target.value)}
            disabled={isChatting}
            style={{ flex: 1 }}
          />
          <button type="submit" className="btn-primary" disabled={isChatting || !chatInput.trim()} style={{ padding: '0.5rem 1rem', whiteSpace: 'nowrap' }}>
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

export default App;
