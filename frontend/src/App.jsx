import React, { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export default function App() {
  const [status, setStatus] = useState("");
  const [verdict, setVerdict] = useState("No report yet.");
  const [explanation, setExplanation] = useState("");
  const [signals, setSignals] = useState([]);
  const [rawJson, setRawJson] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");

  const handleAnalyze = async (event) => {
    event.preventDefault();
    const file = event.target.elements.fileInput.files[0];
    if (!file) {
      setStatus("Select an image first.");
      return;
    }

    setStatus("Analyzing...");
    setVerdict("");
    setExplanation("");
    setSignals([]);
    setRawJson("");
    setPreviewUrl(URL.createObjectURL(file));

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorPayload = await response.json();
        setStatus(errorPayload.error || "Analysis failed.");
        return;
      }

      const report = await response.json();
      setVerdict(`Verdict: ${report.verdict.replaceAll("_", " ")}`);
      setExplanation(report.explanation || "");
      setSignals(report.evidence?.signals || []);
      setRawJson(JSON.stringify(report, null, 2));
      setStatus("Done.");
    } catch (error) {
      setStatus("Unable to reach the backend.");
    }
  };

  return (
    <main className="app">
      <header>
        <div>
          <h1>DeepTrace</h1>
          <p>Explainable forensic verification for AI-generated images.</p>
        </div>
        <div className="badge">Ethical, evidence-first</div>
      </header>

      <section className="upload">
        <form className="upload-card" onSubmit={handleAnalyze}>
          <label className="file-label" htmlFor="fileInput">
            Choose image
          </label>
          <input id="fileInput" name="fileInput" type="file" accept="image/*" />
          <button type="submit">Analyze Image</button>
          <span className="status">{status}</span>
        </form>
        <div className="preview">
          {previewUrl ? (
            <img src={previewUrl} alt="Upload preview" className="show" />
          ) : (
            <span className="preview-placeholder">Image preview</span>
          )}
        </div>
      </section>

      <section className="results">
        <div className="report-header">
          <h2>Forensic Report</h2>
          <div className="verdict">{verdict}</div>
        </div>
        <p className="explanation">{explanation}</p>
        <div className="signals">
          {signals.length === 0 ? (
            <p className="empty-signals">No signals returned yet.</p>
          ) : (
            signals.map((signal) => (
              <article
                key={signal.id}
                className={`signal-card status-${signal.status}`}
              >
                <h3>{signal.name}</h3>
                <p className="meta">
                  Reliability: {signal.reliability?.toFixed(2)} | Support:{" "}
                  {signal.supports}
                </p>
                <p>{signal.summary}</p>
                <ul className="observations">
                  {signal.observations?.map((obs, index) => (
                    <li key={`${signal.id}-${index}`}>{obs}</li>
                  ))}
                </ul>
                {signal.metrics?.ela_image_base64 ? (
                  <img
                    className="signal-image"
                    src={`data:image/png;base64,${signal.metrics.ela_image_base64}`}
                    alt="ELA heatmap"
                  />
                ) : null}
              </article>
            ))
          )}
        </div>
        <details className="raw-json">
          <summary>Raw evidence JSON</summary>
          <pre className="report-json">{rawJson}</pre>
        </details>
      </section>
    </main>
  );
}
