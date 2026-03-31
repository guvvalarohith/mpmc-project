// script.js
// Fetch real-time data from the Flask API

function getStatusClassBasedOnLocalLimits(id, val) {
    if (id === 'co2') {
        if (val > 2000) return 'danger';
        if (val > 1000) return 'warning';
        return 'safe';
    }
    if (id === 'lpg') {
        if (val > 500) return 'danger';
        if (val >= 200) return 'warning';
        return 'safe';
    }
    if (id === 'smoke') {
        if (val > 300) return 'danger';
        if (val >= 100) return 'warning';
        return 'safe';
    }
    return 'safe';
}

function updateSensor(id, val, maxUiScale) {
    const status = getStatusClassBasedOnLocalLimits(id, val);
    
    // Update value text
    document.getElementById(`${id}-value`).textContent = Math.floor(val);
    
    // Update badge text and classes
    const badge = document.getElementById(`${id}-badge`);
    badge.textContent = status.toUpperCase();
    badge.className = `badge ${status}`;
    
    // Update progress bar
    const progress = document.getElementById(`${id}-progress`);
    const width = Math.min((val / maxUiScale) * 100, 100);
    progress.style.width = `${width}%`;
    progress.className = `progress ${status}`;
}

async function fetchLiveSensorData() {
    try {
        const response = await fetch('/current-status');
        const data = await response.json();
        
        // Output from JSON: { co2, lpg, smoke, temperature, humidity, status, harmful_parameter, message }
        
        updateSensor('co2', data.co2, 5000);
        updateSensor('lpg', data.lpg, 1000);
        updateSensor('smoke', data.smoke, 500);
        
        // Temperature, humidity, and soil moisture
        document.getElementById('temp-value').textContent = Math.floor(data.temperature);
        document.getElementById('hum-value').textContent = Math.floor(data.humidity);
        document.getElementById('moist-value').textContent = Math.floor(data.soil_moisture);

        // Overall ML/Backend Status Update
        const overallStatus = data.status.toLowerCase(); // 'safe', 'warning', 'danger'
        const mlStatus = data.ml_status.toLowerCase();
        
        const mlPrediction = document.getElementById('ml-prediction');
        mlPrediction.textContent = data.ml_status;
        mlPrediction.className = `ml-status ${mlStatus}`;
        
        const dot = document.getElementById('overall-status-dot');
        const dotText = document.getElementById('overall-status-text');
        
        dot.className = `status-dot ${overallStatus}`;
        if(overallStatus === 'safe') dotText.textContent = "System Normal";
        else if(overallStatus === 'warning') dotText.textContent = "Caution: Elevated Levels";
        else dotText.textContent = "CRITICAL HAZARD DETECTED";

        // Update Backend Alert Banner
        const banner = document.getElementById('system-alert-banner');
        banner.textContent = data.message;
        // Strip out old banner classes and add new
        banner.className = `system-message msg-${overallStatus}`;
        
    } catch (error) {
        console.error("Error fetching live data. Is the Flask backend running?", error);
        
        // Alert Disconnection
        const banner = document.getElementById('system-alert-banner');
        banner.textContent = "API Disconnected - Backend Server Offline";
        banner.className = `system-message msg-danger`;
        
        const mlPrediction = document.getElementById('ml-prediction');
        mlPrediction.textContent = "OFFLINE";
        mlPrediction.className = "ml-status danger";
    }
}

// Initial pull and interval loop (fetch every 2.5s)
fetchLiveSensorData();
setInterval(fetchLiveSensorData, 2500);

// Trigger manual email
async function triggerManualEmail() {
    const btn = document.getElementById('manual-email-btn');
    const successText = document.getElementById('email-success-text');
    
    // UI feedback
    btn.disabled = true;
    btn.style.opacity = '0.7';
    btn.textContent = 'Sending...';
    
    try {
        const res = await fetch('/send-manual-email', { method: 'POST' });
        if(res.ok) {
            successText.style.display = 'block';
            setTimeout(() => {
                successText.style.display = 'none';
            }, 5000);
        } else {
            alert('Failed to send manual email.');
        }
    } catch(e) {
        console.error('Email trigger error:', e);
        alert('Network error while requesting manual email.');
    }
    
    // Reset UI
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.textContent = 'Send Current Status via Email';
}
