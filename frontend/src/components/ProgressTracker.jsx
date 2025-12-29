import "../App.css";

function ProgressTracker({ jobStatus, onDownload, onRetry, onStop }) {
  if (!jobStatus) {
    return (
      <div className="progress-container">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Initializing scraper...</p>
        </div>
      </div>
    );
  }

  // Calculate correct values - FIXED to prevent negative numbers
  const totalUrls = jobStatus.total_urls || 0;
  const processedUrls = jobStatus.processed_urls || 0;
  const successfulUrls = jobStatus.successful_urls || 0;
  const failedUrls = jobStatus.failed_urls || 0;
  
  // In progress = total - processed (never negative)
  const inProgressUrls = Math.max(0, totalUrls - processedUrls);
  
  const progressPercentage = totalUrls > 0
    ? Math.round((processedUrls / totalUrls) * 100)
    : 0;

  const isCompleted = jobStatus.status === "completed";
  const isStopped = jobStatus.status === "stopped";
  const isOffline = jobStatus.status === "offline" || jobStatus.isOffline;

  return (
    <div className="progress-container">
      {isOffline && (
        <div className="offline-banner">
          <span>📡</span>
          <div>
            <strong>Offline Mode</strong>
            <p>Server is disconnected. Showing last known data.</p>
          </div>
        </div>
      )}
      
      <div className="progress-header">
        <h2>Scraping Progress</h2>
        <div className="iteration-badge">
          {isOffline ? (
            <span>📡 Offline</span>
          ) : (
            <span>Iteration {jobStatus.current_iteration || 1} / {jobStatus.max_iterations || 3}</span>
          )}
        </div>
      </div>

      <div className="progress-bar-container">
        <div className="progress-bar">
          <div 
            className="progress-bar-fill" 
            style={{ width: `${progressPercentage}%` }}
          >
            {progressPercentage > 0 && <span>{progressPercentage}%</span>}
          </div>
        </div>
        <div className="progress-text">
          {processedUrls} / {totalUrls} URLs processed
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card in-progress">
          <div className="stat-icon">⏳</div>
          <div className="stat-content">
            <div className="stat-label">In Progress</div>
            <div className="stat-value">{inProgressUrls}</div>
          </div>
        </div>

        <div className="stat-card success">
          <div className="stat-icon">✓</div>
          <div className="stat-content">
            <div className="stat-label">Successful</div>
            <div className="stat-value">{successfulUrls}</div>
          </div>
        </div>

        <div 
          className="stat-card failed" 
          onClick={failedUrls > 0 && isCompleted ? onRetry : null}
          style={{ cursor: failedUrls > 0 && isCompleted ? 'pointer' : 'default' }}
        >
          <div className="stat-icon">✗</div>
          <div className="stat-content">
            <div className="stat-label">Failed</div>
            <div className="stat-value">{failedUrls}</div>
          </div>
          {failedUrls > 0 && isCompleted && (
            <div className="retry-hint">Click to retry</div>
          )}
        </div>
      </div>

      {(isCompleted || isStopped) && !isOffline && (
        <div className="action-buttons">
          <button className="download-btn" onClick={onDownload}>
            <span>📥</span>
            Download Results CSV
          </button>
          
          {failedUrls > 0 && (
            <button className="retry-btn" onClick={onRetry}>
              <span>🔄</span>
              Retry {failedUrls} Failed URLs
            </button>
          )}
        </div>
      )}

      {isStopped && (
        <div className="stopped-status">
          <span>🛑</span>
          <span>Scraping stopped by user. {successfulUrls} URLs completed successfully.</span>
        </div>
      )}

      {isOffline && (
        <div className="offline-actions">
          <div className="offline-message">
            <p>📡 Server is offline. Data shown is from last sync.</p>
            <p>Restart the server to download results or retry failed URLs.</p>
          </div>
        </div>
      )}

      {!isCompleted && !isStopped && !isOffline && (
        <div>
          <div className="scraping-status">
            <div className="pulse-dot"></div>
            <span>Scraping in progress... ({successfulUrls} successful, {failedUrls} failed so far)</span>
          </div>
          <div className="stop-action">
            <button className="stop-btn" onClick={onStop}>
              <span>⏹️</span>
              Stop Scraping
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProgressTracker;