const API_BASE_URL = 'http://localhost:8000';

// Offline data management
const saveJobDataOffline = (jobId, platform, data) => {
  const key = `${platform}_job_data_${jobId}`;
  localStorage.setItem(key, JSON.stringify({
    ...data,
    lastUpdated: new Date().toISOString(),
    isOffline: false
  }));
};

const getJobDataOffline = (jobId, platform) => {
  const key = `${platform}_job_data_${jobId}`;
  const data = localStorage.getItem(key);
  return data ? JSON.parse(data) : null;
};

const markJobAsOffline = (jobId, platform) => {
  const existingData = getJobDataOffline(jobId, platform);
  if (existingData) {
    saveJobDataOffline(jobId, platform, {
      ...existingData,
      isOffline: true,
      status: existingData.status === 'in_progress' ? 'offline' : existingData.status
    });
  }
};

// Enhanced API calls with offline support
const apiCall = async (url, options = {}) => {
  try {
    const response = await fetch(url, {
      ...options,
      timeout: 10000 // 10 second timeout
    });
    return response;
  } catch (error) {
    console.warn('API call failed:', error.message);
    throw error;
  }
};

// ============= ZOMATO API =============
export const uploadCSV = async (file) => {
  console.log('Uploading Zomato file:', file.name);
  
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/api/zomato/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error('Upload error:', errorText);
    throw new Error('Upload failed');
  }

  return response.json();
};

export const startScraping = async (jobId, resIds) => {
  const response = await fetch(`${API_BASE_URL}/api/zomato/start-scraping-with-ids`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      job_id: jobId,
      res_ids: resIds,
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to start scraping');
  }

  return response.json();
};

export const stopScraping = async (jobId) => {
  const response = await fetch(`${API_BASE_URL}/api/zomato/stop/${jobId}`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error('Failed to stop scraping');
  }

  return response.json();
};

export const getJobStatus = async (jobId) => {
  try {
    const response = await apiCall(`${API_BASE_URL}/api/zomato/status/${jobId}`);

    if (!response.ok) {
      throw new Error('Failed to get status');
    }

    const data = await response.json();
    // Save successful response offline
    saveJobDataOffline(jobId, 'zomato', data.job);
    return data;
  } catch (error) {
    // Try to get offline data
    const offlineData = getJobDataOffline(jobId, 'zomato');
    if (offlineData) {
      console.log('Using offline data for job status');
      markJobAsOffline(jobId, 'zomato');
      return {
        success: true,
        job: {
          ...offlineData,
          status: offlineData.status === 'in_progress' ? 'offline' : offlineData.status,
          isOffline: true
        }
      };
    }
    throw error;
  }
};

export const downloadResults = async (jobId) => {
  const response = await fetch(`${API_BASE_URL}/api/zomato/download/${jobId}`);

  if (!response.ok) {
    throw new Error('Failed to download results');
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `zomato_results_${jobId}.csv`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
};

export const getFailedUrls = async (jobId) => {
  const response = await fetch(`${API_BASE_URL}/api/zomato/failed/${jobId}`);

  if (!response.ok) {
    throw new Error('Failed to get failed URLs');
  }

  return response.json();
};

export const retryFailedUrls = async (jobId) => {
  const response = await fetch(`${API_BASE_URL}/api/zomato/retry-failed/${jobId}`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error('Failed to retry');
  }

  return response.json();
};

// ============= SWIGGY API =============
export const uploadSwiggyCSV = async (file) => {
  console.log('Uploading Swiggy file:', file.name);
  
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/api/swiggy/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error('Upload error:', errorText);
    throw new Error('Upload failed');
  }

  return response.json();
};

export const startSwiggyScraping = async (jobId, resIds) => {
  const response = await fetch(`${API_BASE_URL}/api/swiggy/start-scraping-with-ids`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      job_id: jobId,
      res_ids: resIds,
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to start Swiggy scraping');
  }

  return response.json();
};

export const stopSwiggyScraping = async (jobId) => {
  const response = await fetch(`${API_BASE_URL}/api/swiggy/stop/${jobId}`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error('Failed to stop Swiggy scraping');
  }

  return response.json();
};

export const getSwiggyJobStatus = async (jobId) => {
  try {
    const response = await apiCall(`${API_BASE_URL}/api/swiggy/status/${jobId}`);

    if (!response.ok) {
      throw new Error('Failed to get Swiggy status');
    }

    const data = await response.json();
    // Save successful response offline
    saveJobDataOffline(jobId, 'swiggy', data.job);
    return data;
  } catch (error) {
    // Try to get offline data
    const offlineData = getJobDataOffline(jobId, 'swiggy');
    if (offlineData) {
      console.log('Using offline data for Swiggy job status');
      markJobAsOffline(jobId, 'swiggy');
      return {
        success: true,
        job: {
          ...offlineData,
          status: offlineData.status === 'in_progress' ? 'offline' : offlineData.status,
          isOffline: true
        }
      };
    }
    throw error;
  }
};

export const downloadSwiggyResults = async (jobId) => {
  const response = await fetch(`${API_BASE_URL}/api/swiggy/download/${jobId}`);

  if (!response.ok) {
    throw new Error('Failed to download Swiggy results');
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `swiggy_results_${jobId}.csv`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
};

export const getSwiggyFailedUrls = async (jobId) => {
  const response = await fetch(`${API_BASE_URL}/api/swiggy/failed/${jobId}`);

  if (!response.ok) {
    throw new Error('Failed to get Swiggy failed URLs');
  }

  return response.json();
};

export const retrySwiggyFailedUrls = async (jobId) => {
  const response = await fetch(`${API_BASE_URL}/api/swiggy/retry-failed/${jobId}`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error('Failed to retry Swiggy');
  }

  return response.json();
};



// ============= BLINKIT API =============
export const uploadBlinkitCSV = async (file) => {
  console.log('Uploading Blinkit file:', file.name);
  
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/api/blinkit/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error('Upload error:', errorText);
    throw new Error('Upload failed');
  }

  return response.json();
};

export const startBlinkitScraping = async (jobId, resIds) => {
  const response = await fetch(`${API_BASE_URL}/api/blinkit/start-scraping-with-ids`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      job_id: jobId,
      res_ids: resIds,
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to start Blinkit scraping');
  }

  return response.json();
};

export const stopBlinkitScraping = async (jobId) => {
  const response = await fetch(`${API_BASE_URL}/api/blinkit/stop/${jobId}`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error('Failed to stop Blinkit scraping');
  }

  return response.json();
};

export const getBlinkitJobStatus = async (jobId) => {
  try {
    const response = await apiCall(`${API_BASE_URL}/api/blinkit/status/${jobId}`);

    if (!response.ok) {
      throw new Error('Failed to get Blinkit status');
    }

    const data = await response.json();
    // Save successful response offline
    saveJobDataOffline(jobId, 'blinkit', data.job);
    return data;
  } catch (error) {
    // Try to get offline data
    const offlineData = getJobDataOffline(jobId, 'blinkit');
    if (offlineData) {
      console.log('Using offline data for Blinkit job status');
      markJobAsOffline(jobId, 'blinkit');
      return {
        success: true,
        job: {
          ...offlineData,
          status: offlineData.status === 'in_progress' ? 'offline' : offlineData.status,
          isOffline: true
        }
      };
    }
    throw error;
  }
};

export const downloadBlinkitResults = async (jobId) => {
  const response = await fetch(`${API_BASE_URL}/api/blinkit/download/${jobId}`);

  if (!response.ok) {
    throw new Error('Failed to download Blinkit results');
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `blinkit_results_${jobId}.csv`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
};

export const getBlinkitFailedUrls = async (jobId) => {
  const response = await fetch(`${API_BASE_URL}/api/blinkit/failed/${jobId}`);

  if (!response.ok) {
    throw new Error('Failed to get Blinkit failed URLs');
  }

  return response.json();
};

export const retryBlinkitFailedUrls = async (jobId) => {
  const response = await fetch(`${API_BASE_URL}/api/blinkit/retry-failed/${jobId}`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error('Failed to retry Blinkit');
  }

  return response.json();
};