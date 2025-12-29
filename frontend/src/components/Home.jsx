import { useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import "../App.css";

function Home() {
  const navigate = useNavigate();
  const [scrapingHistory, setScrapingHistory] = useState([]);

  useEffect(() => {
    loadScrapingHistory();
  }, []);

  const loadScrapingHistory = () => {
    const history = [];
    
    // Load from localStorage for each platform
    ['zomato', 'swiggy', 'blinkit'].forEach(platform => {
      const keys = Object.keys(localStorage).filter(key => key.startsWith(`${platform}_job_data_`));
      keys.forEach(key => {
        const data = JSON.parse(localStorage.getItem(key));
        if (data && data.status === 'completed') {
          history.push({
            platform,
            jobId: key.replace(`${platform}_job_data_`, ''),
            ...data
          });
        }
      });
    });
    
    // Sort by completion time
    history.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
    setScrapingHistory(history.slice(0, 10)); // Show last 10
  };

  const downloadResults = async (platform, jobId) => {
    try {
      const response = await fetch(`http://localhost:8000/api/${platform}/download/${jobId}`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${platform}_results_${jobId}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (error) {
      console.error('Download failed:', error);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const getPlatformIcon = (platform) => {
    const icons = { zomato: '🍽️', swiggy: '🍔', blinkit: '🛒' };
    return icons[platform] || '📊';
  };

  return (
    <div className="container">
      <div className="header-section">
        <h1 className="main-title">🚀 Scraping Dashboard</h1>
        <p className="subtitle">Select a platform to start data extraction</p>
      </div>

      <div className="box-container">
        <div className="box swiggy" onClick={() => navigate("/platform/swiggy")}>
          <div className="box-content">
            <div className="box-icon">🍔</div>
            <div className="box-title">Swiggy</div>
            <div className="box-desc">Extract restaurant data</div>
          </div>
        </div>

        <div className="box zomato" onClick={() => navigate("/platform/zomato")}>
          <div className="box-content">
            <div className="box-icon">🍽️</div>
            <div className="box-title">Zomato</div>
            <div className="box-desc">Extract restaurant data</div>
          </div>
        </div>

        <div className="box blinkit" onClick={() => navigate("/platform/blinkit")}>
          <div className="box-content">
            <div className="box-icon">🛒</div>
            <div className="box-title">Blinkit</div>
            <div className="box-desc">Extract product data</div>
          </div>
        </div>
      </div>

      {scrapingHistory.length > 0 && (
        <div className="scraping-history">
          <h2>📊 Recent Scraping Jobs</h2>
          <div className="history-list">
            {scrapingHistory.map((job, index) => (
              <div key={index} className="history-item">
                <div className="history-header">
                  <span className="platform-badge">
                    {getPlatformIcon(job.platform)} {job.platform.toUpperCase()}
                  </span>
                  <span className="scraped-date">
                    Scraped: {formatDate(job.updated_at)}
                  </span>
                </div>
                <div className="history-stats">
                  <div className="stat-item">
                    <span className="stat-label">Total:</span>
                    <span className="stat-value">{job.total_urls}</span>
                  </div>
                  <div className="stat-item success">
                    <span className="stat-label">✅ Success:</span>
                    <span className="stat-value">{job.successful_urls}</span>
                  </div>
                  <div className="stat-item failed">
                    <span className="stat-label">❌ Failed:</span>
                    <span className="stat-value">{job.failed_urls}</span>
                  </div>
                  <button 
                    className="download-btn-small"
                    onClick={() => downloadResults(job.platform, job.jobId)}
                  >
                    📥 Download CSV
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default Home;