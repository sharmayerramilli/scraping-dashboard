import { useNavigate } from "react-router-dom";
import { useState, useEffect, useCallback } from "react";
import "../App.css";
import { uploadSwiggyCSV, startSwiggyScraping, getSwiggyJobStatus, downloadSwiggyResults, retrySwiggyFailedUrls, stopSwiggyScraping } from "../services/api";
import ProgressTracker from "./ProgressTracker";
import StartScraperModal from "./StartScraperModal";

function SwiggyUpload() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [resIds, setResIds] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [isScrapingStarted, setIsScrapingStarted] = useState(false);
  const [jobStatus, setJobStatus] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);

  const checkExistingJob = useCallback(async (jobId) => {
    try {
      const result = await getSwiggyJobStatus(jobId);
      if (result.job && (result.job.status === 'in_progress' || result.job.status === 'completed' || result.job.status === 'offline')) {
        setJobStatus(result.job);
        setIsScrapingStarted(true);
        
        // Continue polling if still in progress and not offline
        if (result.job.status === 'in_progress' && !result.job.isOffline) {
          const interval = setInterval(async () => {
            try {
              const statusResult = await getSwiggyJobStatus(jobId);
              setJobStatus(statusResult.job);
              if (statusResult.job.status === "completed") {
                clearInterval(interval);
              }
            } catch (err) {
              console.error("Polling error:", err);
            }
          }, 2000);
        }
      } else if (result.job && result.job.status === 'stopped') {
        localStorage.removeItem('swiggy_job_id');
        setJobId(null);
        setJobStatus(null);
        setIsScrapingStarted(false);
      } else {
        localStorage.removeItem('swiggy_job_id');
      }
    } catch (err) {
      console.error('Error checking existing job:', err);
      if (!err.message.includes('Failed to fetch')) {
        localStorage.removeItem('swiggy_job_id');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Check for existing job on component mount
  useEffect(() => {
    const savedJobId = localStorage.getItem('swiggy_job_id');
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
      setIsUploading(true);
      try {
        // Parse CSV locally first
        const text = await selectedFile.text();
        const lines = text.split('\n').filter(line => line.trim());
        
        if (lines.length < 2) {
          throw new Error('CSV must have header and at least one data row');
        }
        
        const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
        if (!headers.includes('res_id')) {
          throw new Error('CSV must contain res_id column');
        }
        
        const resIdIndex = headers.indexOf('res_id');
        const extractedIds = lines.slice(1)
          .map(line => line.split(',')[resIdIndex])
          .filter(id => id && id.trim())
          .map(id => id.trim());
        
        if (extractedIds.length === 0) {
          throw new Error('No valid restaurant IDs found');
        }
        
        // Show modal immediately with local data
        setResIds(extractedIds);
        setJobId('temp-' + Date.now());
        setShowModal(true);
        console.log('Found', extractedIds.length, 'restaurant IDs');
        
      } catch (err) {
        setError(err.message || "Failed to parse CSV file");
        console.error('CSV parse error:', err);
      } finally {
        setIsUploading(false);
      }
    }
  };

  const handleStartScraping = async () => {
    try {
      setShowModal(false);
      
      // First upload to create job, then start scraping
      const result = await uploadSwiggyCSV(file);
      const realJobId = result.job_id;
      setJobId(realJobId);
      localStorage.setItem('swiggy_job_id', realJobId);
      
      await startSwiggyScraping(realJobId, resIds);
      setIsScrapingStarted(true);
      
      pollJobStatus(realJobId);
    } catch (err) {
      setError("Failed to start scraping: " + err.message);
      console.error(err);
    }
  };

  const pollJobStatus = async (currentJobId = jobId) => {
    const interval = setInterval(async () => {
      try {
        const result = await getSwiggyJobStatus(currentJobId);
        setJobStatus(result.job);
        
        if (result.job.status === "completed") {
          // Save completion data to localStorage for history
          const completionData = {
            ...result.job,
            platform: 'swiggy',
            completed_at: new Date().toISOString()
          };
          localStorage.setItem(`swiggy_job_data_${currentJobId}`, JSON.stringify(completionData));
          clearInterval(interval);
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 2000);
  };

  const handleDownload = async () => {
    try {
      await downloadSwiggyResults(jobId);
    } catch (err) {
      setError("Failed to download results");
      console.error(err);
    }
  };

  const handleRetryFailed = async () => {
    try {
      await retrySwiggyFailedUrls(jobId);
      setIsScrapingStarted(true);
      pollJobStatus();
    } catch (err) {
      setError("Failed to retry");
      console.error(err);
    }
  };

  const handleStopScraping = async () => {
    try {
      await stopSwiggyScraping(jobId);
      setJobStatus(prev => ({ ...prev, status: 'stopped' }));
      setError(null);
    } catch (err) {
      setError("Failed to stop scraping");
      console.error(err);
    }
  };

  const handleNewJob = () => {
    localStorage.removeItem('swiggy_job_id');
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
        <div className="platform-icon">🍔</div>
        <div>
          <h1 className="platform-title">Swiggy Scraper</h1>
          <p className="platform-subtitle">Upload CSV file with restaurant IDs</p>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <span>⚠️ {error}</span>
        </div>
      )}

      {!isScrapingStarted && !showModal ? (
        <div className="upload-section">
          <div className="upload-card">
            <div className="upload-header">
              <h3>📄 Upload CSV File</h3>
              <p>File must contain a column named "res_id"</p>
            </div>

            <div className="upload-body">
              <label className="file-input-label">
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  className="file-input"
                  disabled={isUploading}
                />
                <div className="file-input-button">
                  <span className="upload-icon">{isUploading ? '⏳' : '📁'}</span>
                  <span>{isUploading ? 'Uploading...' : 'Choose CSV File'}</span>
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
787978
766
9304`}
              </pre>
            </div>
          </div>
        </div>
      ) : isScrapingStarted ? (
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
      ) : null}

      {showModal && (
        <StartScraperModal
          show={showModal}
          onClose={() => setShowModal(false)}
          onStart={handleStartScraping}
          totalUrls={resIds.length}
        />
      )}
    </div>
  );
}

export default SwiggyUpload;