import "../App.css";

function StartScraperModal({ show, onClose, onStart, totalUrls }) {
  if (!show) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>🚀 Ready to Start Scraping?</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div className="modal-info">
            <div className="info-item">
              <span className="info-icon">📊</span>
              <div>
                <div className="info-label">Total URLs</div>
                <div className="info-value">{totalUrls}</div>
              </div>
            </div>

            <div className="info-item">
              <span className="info-icon">⚡</span>
              <div>
                <div className="info-label">Workers</div>
                <div className="info-value">3 Threads</div>
              </div>
            </div>

            <div className="info-item">
              <span className="info-icon">🔄</span>
              <div>
                <div className="info-label">Max Retries</div>
                <div className="info-value">3 Iterations</div>
              </div>
            </div>
          </div>

          <div className="modal-note">
            <p><strong>Note:</strong> The scraper will automatically retry failed URLs up to 3 times. You can monitor progress in real-time and download results when complete.</p>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={onStart}>
            <span>🚀</span>
            Start Scraper
          </button>
        </div>
      </div>
    </div>
  );
}

export default StartScraperModal;