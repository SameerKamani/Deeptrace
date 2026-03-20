import React, { useState, useRef } from "react";
import { 
  ShieldCheck, AlertOctagon, HelpCircle, 
  UploadCloud, Search, Activity, Camera, Eye, ScanSearch, MapPin, Target, Database,
  ChevronDown, ChevronRight, Fingerprint, Sparkles
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

const VerdictIcon = ({ verdict }) => {
  const v = verdict.toLowerCase();
  if (v.includes("authentic")) return <ShieldCheck size={28} />;
  if (v.includes("ai")) return <AlertOctagon size={28} />;
  return <HelpCircle size={28} />;
};

const getVerdictClass = (verdict) => {
  const v = verdict.toLowerCase();
  if (v.includes("authentic")) return "verdict-authentic";
  if (v.includes("ai")) return "verdict-ai";
  return "verdict-inconclusive";
};

const SignalIcon = ({ category }) => {
  const c = category.toLowerCase();
  if (c.includes('spectral')) return <Activity size={14} />;
  if (c.includes('metadata')) return <Camera size={14} />;
  if (c.includes('semantic')) return <Eye size={14} />;
  if (c.includes('forensic')) return <ScanSearch size={14} />;
  if (c.includes('noise')) return <Target size={14} />;
  if (c.includes('lighting')) return <Sparkles size={14} />;
  return <Database size={14} />;
};

export default function App() {
  const [status, setStatus] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [fileSelected, setFileSelected] = useState(false);
  const [showJson, setShowJson] = useState(false);
  
  const fileInputRef = useRef(null);

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      setFileSelected(true);
      setPreviewUrl(URL.createObjectURL(file));
      setReportData(null);
      setStatus("");
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) {
      if(fileInputRef.current) {
         const dataTransfer = new DataTransfer();
         dataTransfer.items.add(file);
         fileInputRef.current.files = dataTransfer.files;
         handleFileChange({ target: { files: [file] } });
      }
    }
  };

  const handleAnalyze = async (event) => {
    event.preventDefault();
    const file = fileInputRef.current?.files[0];
    if (!file) {
      setStatus("Please select an image first.");
      return;
    }

    setIsAnalyzing(true);
    setStatus("Extracting forensic signals and querying reasoning engine...");
    setReportData(null);
    setShowJson(false);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorPayload = await response.json();
        // Sometimes backend returns HTML or non-JSON if standard HTTP error
        setStatus(errorPayload.error || "Analysis failed due to a server error.");
        setIsAnalyzing(false);
        return;
      }

      const report = await response.json();
      setReportData(report);
      setStatus("");
    } catch (error) {
      setStatus("Unable to reach the backend analysis engine. Check your connection.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="app">
      <header>
        <div className="logo-wrapper">
          <Fingerprint size={40} className="logo-icon" />
          <div>
            <h1>DeepTrace</h1>
            <p>Explainable Forensic Verification for Visual Media</p>
          </div>
        </div>
        <div className="badge">
          <span className="badge-dot"></span>
          System Ready
        </div>
      </header>

      <main>
        <div className="glass-panel top-section">
          <form className="upload-area" onSubmit={handleAnalyze}>
            <div 
              className="dropzone" 
              onDragOver={handleDragOver} 
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <UploadCloud size={48} className="dropzone-icon" />
              <div className="dropzone-text">
                {fileSelected ? "Image selected. Click or drop to change." : "Drag & drop an image here"}
              </div>
              <div className="dropzone-subtext">Supports valid image formats up to 10MB</div>
              <input 
                ref={fileInputRef}
                type="file" 
                accept="image/*" 
                className="file-input" 
                onChange={handleFileChange}
              />
            </div>
            <button 
              type="submit" 
              className="btn-primary" 
              disabled={!fileSelected || isAnalyzing}
            >
              <Search size={20} />
              {isAnalyzing ? "Scanning Evidence Profile..." : "Initiate Forensic Scan"}
            </button>
            {status && <div className="status-text">{status}</div>}
          </form>

          <div className="preview-container">
            {previewUrl ? (
              <>
                <img 
                  src={previewUrl} 
                  alt="Subject material" 
                  className="preview-image" 
                  style={{ opacity: isAnalyzing ? 0.6 : 1 }}
                />
                {isAnalyzing && <div className="scanline"></div>}
              </>
            ) : (
              <div className="status-text">
                <Eye size={24} style={{ opacity: 0.5 }} />
                <span>Target image preview</span>
              </div>
            )}
          </div>
        </div>

        {reportData && (
          <div className="glass-panel results-section fade-in">
            <div className="results-header">
              <h2>Forensic Report</h2>
              <span style={{color: "var(--text-muted)", fontSize: "14px"}}>
                Generated at: {new Date(reportData.generated_at).toLocaleString()}
              </span>
            </div>

            <div className={`verdict-banner ${getVerdictClass(reportData.verdict)}`}>
              <VerdictIcon verdict={reportData.verdict} />
              <span>Verdict: {reportData.verdict.replace(/_/g, " ").toUpperCase()}</span>
            </div>

            <div className="explanation-card">
              <h3><MapPin size={16} /> Investigator's Summary</h3>
              <p>{reportData.explanation}</p>
            </div>

            <h3 style={{marginBottom: "24px", color: "var(--text-main)", fontSize: "20px"}}>
               Extracted Evidence Signals
            </h3>
            
            <div className="signals-grid">
              {reportData.evidence?.signals?.length > 0 ? (
                reportData.evidence.signals.map((signal) => (
                  <div key={signal.id} className="signal-card">
                    <div className="signal-header">
                      <div className="signal-title-wrap">
                        <span className="signal-category">
                          <SignalIcon category={signal.category} /> {signal.category}
                        </span>
                        <h4>{signal.name}</h4>
                      </div>
                      <span className={`signal-status-badge status-${signal.status}`}>
                        {signal.status}
                      </span>
                    </div>

                    <div className="signal-stats">
                      <div className="stat-item">
                        <span className="stat-label">Reliability</span>
                        <span className="stat-value">{(signal.reliability * 100).toFixed(0)}%</span>
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
                        <img 
                          src={`data:image/png;base64,${signal.metrics.ela_image_base64}`} 
                          alt="ELA Heatmap" 
                        />
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <div style={{color: "var(--text-muted)"}}>No independent signals were extracted.</div>
              )}
            </div>

            <div>
              <div 
                className="json-toggle" 
                onClick={() => setShowJson(!showJson)}
              >
                {showJson ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                View Raw JSON Export
              </div>
              
              {showJson && (
                <pre className="json-view fade-in">
                  {JSON.stringify(reportData, null, 2)}
                </pre>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
