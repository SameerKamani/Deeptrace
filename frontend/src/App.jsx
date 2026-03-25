import React, { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence, useInView } from "framer-motion";
import {
  ShieldCheck, AlertOctagon, HelpCircle, Search, Camera, Eye,
  ScanSearch, Activity, Target, Database, ChevronDown, ChevronRight,
  Fingerprint, Sparkles, Send, X, Image as ImageIcon, Copy, Check,
  Zap, Globe, Layers, Cpu
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

const SCAN_STEPS = [
  "Extracting spectral frequencies...",
  "Parsing EXIF metadata...",
  "Analyzing thermal noise patterns...",
  "Evaluating lighting physics...",
  "Running semantic vision analysis...",
  "Computing error level analysis...",
  "Performing live OSINT search...",
  "Aggregating evidence signals...",
  "Generating forensic report...",
];

const SIGNAL_THEME = {
  spectral:  { color: "#a855f7", glow: "rgba(168,85,247,0.25)",  label: "Spectral" },
  metadata:  { color: "#3b82f6", glow: "rgba(59,130,246,0.25)",  label: "Metadata" },
  semantic:  { color: "#ec4899", glow: "rgba(236,72,153,0.25)",  label: "Semantic" },
  forensic:  { color: "#f59e0b", glow: "rgba(245,158,11,0.25)",  label: "Forensic" },
  noise:     { color: "#10b981", glow: "rgba(16,185,129,0.25)",  label: "Noise"    },
  lighting:  { color: "#f97316", glow: "rgba(249,115,22,0.25)",  label: "Lighting" },
  default:   { color: "#00e6ff", glow: "rgba(0,230,255,0.25)",   label: "Signal"   },
};

function getSignalTheme(category) {
  const c = (category || "").toLowerCase();
  for (const [key, theme] of Object.entries(SIGNAL_THEME)) {
    if (c.includes(key)) return theme;
  }
  return SIGNAL_THEME.default;
}

const SignalIcon = ({ category, size = 14 }) => {
  const c = (category || "").toLowerCase();
  if (c.includes("spectral")) return <Cpu size={size} />;
  if (c.includes("metadata")) return <Camera size={size} />;
  if (c.includes("semantic")) return <Eye size={size} />;
  if (c.includes("forensic")) return <ScanSearch size={size} />;
  if (c.includes("noise"))    return <Activity size={size} />;
  if (c.includes("lighting")) return <Sparkles size={size} />;
  return <Database size={size} />;
};

const VerdictIcon = ({ verdict, size = 24 }) => {
  const v = verdict.toLowerCase();
  if (v.includes("authentic")) return <ShieldCheck size={size} />;
  if (v.includes("ai"))        return <AlertOctagon size={size} />;
  return <HelpCircle size={size} />;
};

const getVerdictClass = (verdict) => {
  const v = verdict.toLowerCase();
  if (v.includes("authentic")) return "verdict-authentic";
  if (v.includes("ai"))        return "verdict-ai";
  return "verdict-inconclusive";
};

function AnimatedSignalCard({ signal, index }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-40px" });
  const theme = getSignalTheme(signal.category);

  return (
    <motion.div
      ref={ref}
      className="signal-card"
      style={{ "--signal-color": theme.color, "--signal-glow": theme.glow }}
      initial={{ opacity: 0, y: 30 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ type: "spring", stiffness: 280, damping: 22, delay: index * 0.07 }}
      whileHover={{ y: -5, boxShadow: `0 16px 40px ${theme.glow}` }}
    >
      <div className="signal-header">
        <div className="signal-title-wrap">
          <span className="signal-category" style={{ color: theme.color }}>
            <SignalIcon category={signal.category} /> {signal.category}
          </span>
          <h4>{signal.name}</h4>
        </div>
        <span className={`signal-status-badge status-${signal.status}`}>{signal.status}</span>
      </div>

      <div className="signal-stats">
        <div className="stat-item">
          <span className="stat-label">Reliability</span>
          <div className="reliability-bar-wrap">
            <span className="stat-value">{(signal.reliability * 100).toFixed(0)}%</span>
            <div className="reliability-bar">
              <motion.div
                className="reliability-fill"
                style={{ background: theme.color }}
                initial={{ width: 0 }}
                animate={isInView ? { width: `${signal.reliability * 100}%` } : {}}
                transition={{ duration: 0.8, delay: index * 0.07 + 0.3, ease: "easeOut" }}
              />
            </div>
          </div>
        </div>
        <div className="stat-item">
          <span className="stat-label">Direction</span>
          <span className={`stat-value support-${signal.supports}`}>
            {signal.supports.replace(/_/g, " ").toUpperCase()}
          </span>
        </div>
      </div>

      <div className="signal-summary">{signal.summary}</div>

      {signal.observations?.length > 0 && (
        <ul className="observations-list">
          {signal.observations.map((obs, idx) => (
            <li key={idx}>{obs}</li>
          ))}
        </ul>
      )}

      {signal.metrics?.ela_image_base64 && (
        <div className="signal-image-container">
          <img src={`data:image/png;base64,${signal.metrics.ela_image_base64}`} alt="ELA Heatmap" />
        </div>
      )}
    </motion.div>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <motion.button
      className="copy-btn"
      onClick={handleCopy}
      whileTap={{ scale: 0.9 }}
      title="Copy JSON"
    >
      <AnimatePresence mode="wait">
        {copied
          ? <motion.span key="check" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}><Check size={14} /></motion.span>
          : <motion.span key="copy"  initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}><Copy size={14} /></motion.span>
        }
      </AnimatePresence>
      {copied ? "Copied!" : "Copy"}
    </motion.button>
  );
}

function ScanningOverlay({ steps, currentStep }) {
  return (
    <div className="scan-overlay">
      <div className="scan-laser" />
      <div className="scan-corners">
        <span className="corner tl" />
        <span className="corner tr" />
        <span className="corner bl" />
        <span className="corner br" />
      </div>
      <div className="scan-status">
        <span className="scan-dot" />
        <AnimatePresence mode="wait">
          <motion.span
            key={currentStep}
            className="scan-text"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.35 }}
          >
            {steps[currentStep % steps.length]}
          </motion.span>
        </AnimatePresence>
      </div>
    </div>
  );
}

function ForensicReportCard({ reportData, showJson, onToggleJson }) {
  if (!reportData) return null;
  const jsonStr = JSON.stringify(reportData, null, 2);

  return (
    <div className="report-inner">
      <motion.div
        className={`verdict-stamp ${getVerdictClass(reportData.verdict)}`}
        initial={{ opacity: 0, scale: 0.92 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ type: "spring", stiffness: 300, damping: 20 }}
      >
        <VerdictIcon verdict={reportData.verdict} size={28} />
        <div className="verdict-text-wrap">
          <span className="verdict-label">Verdict</span>
          <span className="verdict-value">{reportData.verdict.replace(/_/g, " ").toUpperCase()}</span>
        </div>
        <span className="report-ts">{new Date(reportData.generated_at).toLocaleString()}</span>
      </motion.div>

      <motion.div
        className="narrative"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25, duration: 0.5 }}
      >
        {reportData.explanation}
      </motion.div>

      <motion.div
        className="signals-section"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.45 }}
      >
        <h3 className="signals-section-title">
          <Layers size={14} /> Evidence signals
        </h3>
        <div className="signals-grid">
          {reportData.evidence?.signals?.length > 0
            ? reportData.evidence.signals.map((signal, i) => (
                <AnimatedSignalCard key={signal.id} signal={signal} index={i} />
              ))
            : <p style={{ color: "var(--text-muted)" }}>No signals extracted.</p>
          }
        </div>
      </motion.div>

      <motion.div
        className="json-section"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
      >
        <div className="json-toggle-row">
          <button className="json-toggle" onClick={() => onToggleJson()}>
            {showJson ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            Raw JSON export
          </button>
          {showJson && <CopyButton text={jsonStr} />}
        </div>
        <AnimatePresence>
          {showJson && (
            <motion.pre
              className="json-view"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.3 }}
            >
              {jsonStr}
            </motion.pre>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}

export default function App() {
  const [sessionId, setSessionId]       = useState(null);
  const [sessionError, setSessionError] = useState("");
  const [messages, setMessages]         = useState([]);
  const [status, setStatus]             = useState("");
  const [isAnalyzing, setIsAnalyzing]   = useState(false);
  const [isSending, setIsSending]       = useState(false);
  const [previewUrl, setPreviewUrl]     = useState("");
  const [fileSelected, setFileSelected] = useState(false);
  const [contextText, setContextText]   = useState("");
  const [followUp, setFollowUp]         = useState("");
  const [showJsonById, setShowJsonById] = useState({});
  const [scanStep, setScanStep]         = useState(0);

  const fileInputRef = useRef(null);
  const feedEndRef   = useRef(null);

  // Cycle scan text while analyzing
  useEffect(() => {
    if (!isAnalyzing) return;
    const id = setInterval(() => setScanStep((s) => s + 1), 2200);
    return () => clearInterval(id);
  }, [isAnalyzing]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res  = await fetch(`${API_BASE}/sessions`, { method: "POST" });
        const data = await res.json();
        if (!cancelled) setSessionId(data.session_id);
      } catch {
        if (!cancelled) setSessionError("Could not reach the API. Check backend and VITE_API_BASE.");
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, status]);

  const ensureSession = useCallback(async () => {
    if (sessionId) return sessionId;
    const res  = await fetch(`${API_BASE}/sessions`, { method: "POST" });
    const data = await res.json();
    setSessionId(data.session_id);
    return data.session_id;
  }, [sessionId]);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file || !file.type.startsWith("image/")) return;
    setFileSelected(true);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(file));
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (!file || !file.type.startsWith("image/")) return;
    if (fileInputRef.current) {
      const dt = new DataTransfer();
      dt.items.add(file);
      fileInputRef.current.files = dt.files;
      handleFileChange({ target: { files: [file] } });
    }
  };

  const clearImage = () => {
    setPreviewUrl(""); setFileSelected(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleAnalyze = async () => {
    const file = fileInputRef.current?.files[0];
    if (!file) return;
    setIsAnalyzing(true); setScanStep(0);
    setStatus("Running forensic pipeline...");
    setShowJsonById({});

    const imageSnapshot = previewUrl;

    try {
      const sid = await ensureSession();
      const fd  = new FormData();
      fd.append("file", file);
      fd.append("context", contextText.trim());

      setMessages((prev) => [
        ...prev,
        { id: `u-${Date.now()}`, role: "user", kind: "analyze", text: contextText.trim(), imageUrl: imageSnapshot },
      ]);

      const res = await fetch(`${API_BASE}/sessions/${sid}/analyze`, { method: "POST", body: fd });
      if (!res.ok) { setStatus("Analysis failed."); return; }

      const report = await res.json();
      setMessages((prev) => [...prev, { id: `a-${Date.now()}`, role: "assistant", kind: "report", report }]);
      setStatus("");
      // keep image in panel so user can reference it; allow new file
      setContextText("");
    } catch {
      setStatus("Unable to reach the backend.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleFollowUp = async () => {
    const text = followUp.trim();
    if (!text || !sessionId) return;
    setIsSending(true); setFollowUp("");
    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, role: "user", kind: "text", text }]);
    try {
      const res  = await fetch(`${API_BASE}/sessions/${sessionId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      const reply = res.ok ? data.reply : (data.error || "Could not answer.");
      setMessages((prev) => [...prev, { id: `a-${Date.now()}`, role: "assistant", kind: "text", text: reply }]);
    } catch {
      setMessages((prev) => [...prev, { id: `a-${Date.now()}`, role: "assistant", kind: "text", text: "Network error." }]);
    } finally {
      setIsSending(false);
    }
  };

  const toggleJson = (id) => setShowJsonById((prev) => ({ ...prev, [id]: !prev[id] }));
  const hasReport  = messages.some((m) => m.role === "assistant" && m.kind === "report");

  return (
    <div className="app-root">
      {/* ── HEADER ── */}
      <header className="app-header">
        <div className="logo-wrap">
          <Fingerprint size={28} className="logo-icon" />
          <div>
            <h1 className="logo-name">DeepTrace</h1>
            <p className="logo-sub">Forensic image verification</p>
          </div>
        </div>
        <nav className="header-nav">
          <a className="nav-link" href="#" onClick={(e) => e.preventDefault()}>Docs</a>
          <a className="nav-link" href="#" onClick={(e) => e.preventDefault()}>About</a>
          <div className={`status-pill ${sessionError ? "offline" : "online"}`}>
            <span className="pill-dot" />
            {sessionError ? "Offline" : "Ready"}
          </div>
        </nav>
      </header>

      {sessionError && <div className="banner-error">{sessionError}</div>}

      {/* ── MAIN LAYOUT ── */}
      <main className="main-split">

        {/* LEFT — feed */}
        <section className="feed-col">
          {messages.length === 0 && !status && (
            <motion.div
              className="feed-empty"
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <div className="empty-icon-ring">
                <Fingerprint size={36} />
              </div>
              <h2>Start a forensic examination</h2>
              <p>Drop an image in the panel on the right, add optional context, then hit Analyze. DeepTrace will run 7 independent forensic signals and produce a transparent, evidence-backed report.</p>
              <div className="feature-pills">
                <span className="feat-pill"><Zap size={12} />7 parallel detectors</span>
                <span className="feat-pill"><Globe size={12} />Live OSINT search</span>
                <span className="feat-pill"><Eye size={12} />Semantic vision AI</span>
              </div>
            </motion.div>
          )}

          <AnimatePresence initial={false}>
            {messages.map((m) => (
              <motion.div
                key={m.id}
                className={`msg-row msg-${m.role}`}
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ type: "spring", stiffness: 380, damping: 28 }}
              >
                {m.role === "user" && m.kind === "analyze" && (
                  <div className="user-bubble">
                    {m.imageUrl && <img src={m.imageUrl} alt="" className="msg-thumb" />}
                    {m.text && <p className="msg-context">{m.text}</p>}
                  </div>
                )}
                {m.role === "user" && m.kind === "text" && (
                  <div className="user-bubble text-only"><p>{m.text}</p></div>
                )}
                {m.role === "assistant" && m.kind === "text" && (
                  <div className="assistant-bubble"><p>{m.text}</p></div>
                )}
                {m.role === "assistant" && m.kind === "report" && m.report && (
                  <ForensicReportCard
                    reportData={m.report}
                    showJson={!!showJsonById[m.id]}
                    onToggleJson={() => toggleJson(m.id)}
                  />
                )}
              </motion.div>
            ))}
          </AnimatePresence>

          {status && (
            <motion.div className="feed-status" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <div className="spin-ring" />{status}
            </motion.div>
          )}
          <div ref={feedEndRef} />

          {/* Follow-up bar — appears only after a report */}
          <AnimatePresence>
            {hasReport && (
              <motion.div
                className="followup-bar"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 20 }}
              >
                <Send size={16} className="followup-icon" />
                <input
                  className="followup-input"
                  placeholder="Ask a follow-up question about this report…"
                  value={followUp}
                  onChange={(e) => setFollowUp(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleFollowUp(); }
                  }}
                  disabled={isSending || !!sessionError}
                />
                <motion.button
                  className="followup-send"
                  onClick={handleFollowUp}
                  disabled={isSending || !followUp.trim() || !!sessionError}
                  whileTap={{ scale: 0.92 }}
                >
                  {isSending ? <div className="spin-ring" /> : <Send size={16} />}
                </motion.button>
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* RIGHT — control panel */}
        <aside className="control-panel">
          <div className="panel-head-label">New examination</div>

          {/* Drop zone / preview */}
          <div
            className={`drop-zone ${previewUrl ? "has-preview" : ""}`}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => !previewUrl && fileInputRef.current?.click()}
          >
            <input ref={fileInputRef} type="file" accept="image/*" className="file-input-hidden" onChange={handleFileChange} />
            {previewUrl ? (
              <div className="preview-wrap">
                <img src={previewUrl} alt="Preview" className="preview-img" />
                {isAnalyzing && <ScanningOverlay steps={SCAN_STEPS} currentStep={scanStep} />}
                {!isAnalyzing && (
                  <div className="preview-actions">
                    <button className="preview-btn" onClick={(e) => { e.stopPropagation(); clearImage(); }}>
                      <X size={14} /> Remove
                    </button>
                    <button className="preview-btn" onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}>
                      Change
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="drop-empty">
                <div className="drop-icon-ring">
                  <div className="drop-cloud-icon" />
                </div>
                <p className="drop-title">Drop image here</p>
                <p className="drop-sub">or click to browse</p>
              </div>
            )}
          </div>

          {/* Context textarea */}
          <label className="field-label">Context <span className="optional">(optional)</span></label>
          <textarea
            className="context-input"
            rows={3}
            placeholder="e.g. Is this the Netanyahu video? Verify if this event occurred."
            value={contextText}
            onChange={(e) => setContextText(e.target.value)}
            disabled={isAnalyzing}
          />

          {/* Analyze button */}
          <motion.button
            className={`analyze-btn ${isAnalyzing ? "analyzing" : ""}`}
            onClick={handleAnalyze}
            disabled={!fileSelected || isAnalyzing || !!sessionError}
            whileHover={fileSelected && !isAnalyzing ? { scale: 1.02 } : {}}
            whileTap={fileSelected && !isAnalyzing ? { scale: 0.97 } : {}}
          >
            {isAnalyzing
              ? <><div className="spin-ring white" />Analyzing…</>
              : <><Search size={18} />Run Analysis</>
            }
          </motion.button>

          {/* Signal legend */}
          <div className="signal-legend">
            <p className="legend-title">Signal detectors</p>
            <div className="legend-grid">
              {Object.entries(SIGNAL_THEME).filter(([k]) => k !== "default").map(([key, t]) => (
                <div key={key} className="legend-item">
                  <span className="legend-dot" style={{ background: t.color, boxShadow: `0 0 6px ${t.color}` }} />
                  <span>{t.label}</span>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}
