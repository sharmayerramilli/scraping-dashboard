import { useNavigate } from "react-router-dom";
import { useState, useEffect, useCallback } from "react";
import "../App.css";
import { uploadBlinkitCSV, startBlinkitScraping, getBlinkitJobStatus, downloadBlinkitResults, retryBlinkitFailedUrls, stopBlinkitScraping } from "../services/api";
import ProgressTracker from "./ProgressTracker";
import StartScraperModal from "./StartScraperModal";

function BlinkitUpload() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [resIds, setResIds] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [isScrapingStarted, setIsScrapingStarted] = useState(false);
  const [jobStatus, setJobStatus] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const pollJobStatus = async (currentJobId = jobId) => {
    const interval = setInterval(async () => {
      try {
        const result = await getBlinkitJobStatus(currentJobId);
        setJobStatus(result.job);
        
        if (result.job.status === "completed") {
          // Save completion data to localStorage for history
          const completionData = {
            ...result.job,
            platform: 'blinkit',
            completed_at: new Date().toISOString()
          };
          localStorage.setItem(`blinkit_job_data_${currentJobId}`, JSON.stringify(completionData));
          clearInterval(interval);
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 2000);
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const checkExistingJob = useCallback(async (jobId) => {
    try {
      const result = await getBlinkitJobStatus(jobId);
      if (result.job && (result.job.status === 'in_progress' || result.job.status === 'completed' || result.job.status === 'offline')) {
        setJobStatus(result.job);
        setIsScrapingStarted(true);
        
        if (result.job.status === 'in_progress' && !result.job.isOffline) {
          pollJobStatus(jobId);
        }
      } else if (result.job && result.job.status === 'stopped') {
        localStorage.removeItem('blinkit_job_id');
        setJobId(null);
        setJobStatus(null);
        setIsScrapingStarted(false);
      } else {
        localStorage.removeItem('blinkit_job_id');
      }
    } catch (err) {
      console.error('Error checking existing job:', err);
      if (!err.message.includes('Failed to fetch')) {
        localStorage.removeItem('blinkit_job_id');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const savedJobId = localStorage.getItem('blinkit_job_id');
    if (savedJobId) {
      setJobId(savedJobId);
      checkExistingJob(savedJobId);
    } else {
      setIsLoading(false);
    }
  }, [checkExistingJob]);

  const handleFileChange = async (e) => {
    const selectedFile = e.target.files[0];
    setFile(selectedFile);
    setError(null);

    if (selectedFile) {
      try {
        setIsScrapingStarted(false);
        setJobStatus(null);
        
        const result = await uploadBlinkitCSV(selectedFile);
        setJobId(result.job_id);
        setResIds(result.res_ids);
        localStorage.setItem('blinkit_job_id', result.job_id);
        setShowModal(true);
      } catch (err) {
        setError("Failed to upload file. Please check the format.");
        console.error(err);
      }
    }
  };

  const handleStartScraping = async () => {
    try {
      setShowModal(false);
      await startBlinkitScraping(jobId, resIds);
      setIsScrapingStarted(true);
      pollJobStatus(jobId);
    } catch (err) {
      setError("Failed to start scraping");
      console.error(err);
    }
  };

  const handleDownload = async () => {
    try {
      await downloadBlinkitResults(jobId);
    } catch (err) {
      setError("Failed to download results");
      console.error(err);
    }
  };

  const handleRetryFailed = async () => {
    try {
      await retryBlinkitFailedUrls(jobId);
      setIsScrapingStarted(true);
      pollJobStatus();
    } catch (err) {
      setError("Failed to retry");
      console.error(err);
    }
  };

  const handleStopScraping = async () => {
    try {
      await stopBlinkitScraping(jobId);
      setJobStatus(prev => ({ ...prev, status: 'stopped' }));
      setError(null);
    } catch (err) {
      setError("Failed to stop scraping");
      console.error(err);
    }
  };

  const handleNewJob = () => {
    localStorage.removeItem('blinkit_job_id');
    setJobId(null);
    setJobStatus(null);
    setIsScrapingStarted(false);
    setFile(null);
    setResIds([]);
    setError(null);
  };

  if (isLoading) {
    return (
      <div className="container">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Checking for existing jobs...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <button className="back-btn" onClick={() => navigate("/")}>
        ← Back to Dashboard
      </button>

      <div className="platform-header">
        <div className="platform-icon">🛒</div>
        <div>
          <h1 className="platform-title">Blinkit Scraper</h1>
          <p className="platform-subtitle">Upload CSV file with product IDs - Enhanced with smart data extraction</p>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <span>⚠️ {error}</span>
        </div>
      )}

      {!isScrapingStarted ? (
        <div className="upload-section">
          <div className="upload-card">
            <div className="upload-header">
              <h3>📄 Upload CSV File</h3>
              <p>File must contain a column named "res_id" or "product_id"</p>
            </div>

            <div className="upload-body">
              <label className="file-input-label">
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  className="file-input"
                />
                <div className="file-input-button">
                  <span className="upload-icon">📁</span>
                  <span>Choose CSV File</span>
                </div>
              </label>

              {file && (
                <div className="file-info">
                  <span className="file-icon">✓</span>
                  <div>
                    <div className="file-name">{file.name}</div>
                    <div className="file-size">
                      {(file.size / 1024).toFixed(2)} KB
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="csv-format">
              <h4>Expected CSV Format:</h4>
              <pre>
{`res_id
618825
603902
612345`}
              </pre>
            </div>
          </div>
        </div>
      ) : (
        <div>
          <div className="job-actions">
            <button className="new-job-btn" onClick={handleNewJob}>
              🆕 Start New Job
            </button>
          </div>
          <ProgressTracker
            jobStatus={jobStatus}
            onDownload={handleDownload}
            onRetry={handleRetryFailed}
            onStop={handleStopScraping}
          />
        </div>
      )}

      <StartScraperModal
        show={showModal}
        onClose={() => setShowModal(false)}
        onStart={handleStartScraping}
        totalUrls={resIds.length}
      />
    </div>
  );
}

export default BlinkitUpload;