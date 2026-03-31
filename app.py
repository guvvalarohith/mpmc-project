import logging
import smtplib
import ssl
import threading
import time
from datetime import datetime
from email.mime.text import MIMEText
from flask import Flask, request, jsonify
import joblib
import os
import numpy as np

# ================= Configure Logging =================
logging.basicConfig(
    filename='alerts.log',
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logging.info("Backend Application Started.")

# ================= Load ML Model =================
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'gas_model.pkl')
try:
    ml_model = joblib.load(MODEL_PATH)
    logging.info(f"ML Model loaded successfully from {MODEL_PATH}")
except Exception as e:
    ml_model = None
    logging.error(f"Failed to load ML Model: {e}")

app = Flask(__name__, static_folder='.', static_url_path='')

# ================= Global State Tracking =================
latest_data = {
    "co2": 0,
    "lpg": 0,
    "smoke": 0,
    "temperature": 25,
    "humidity": 50,
    "soil_moisture": 50,
    "status": "SAFE",
    "ml_status": "SAFE",
    "harmful_parameter": "None",
    "message": "Current environment conditions are within safe limits."
}

# State history to prevent redundant automatic emails
previous_status = "SAFE"
previous_harmful_params = []

# ================= Email Alert SysteEREm =================
def _send_email_task(email_type, status, ml_status, harmful_params, message, sensor_data, timestamp):
    """Background worker function attempting to dispatch the email via Gmail SMTP."""
    sender = "rohithreddy2577@gmail.com"
    recipient = "guvvala.rohithreddy2024@vitstudent.ac.in"
    password = "rraw airs gmrc ynyv"
    
    if email_type == "Automatic":
        subject = f"ALERT: [{status}] Hazardous Gas Detected"
    else:
        subject = f"Status Report: [{status}] System Summary"
        
    body = f"""
=================================================
      HAZARDOUS GAS MONITORING SYSTEM
=================================================
Report Type:   {email_type}
System Status: {status}
AI Prediction: {ml_status}
Timestamp:     {timestamp}

--- SENSOR DATA SNAPSHOT ---
• CO2 Level:     {sensor_data.get('co2', 0)} ppm
• LPG Level:     {sensor_data.get('lpg', 0)} ppm
• Smoke Level:   {sensor_data.get('smoke', 0)} ppm
• Temperature:   {sensor_data.get('temperature', 0)} °C
• Humidity:      {sensor_data.get('humidity', 0)} %
• Soil Moisture: {sensor_data.get('soil_moisture', 0)} %

-------------------------------------------------
"""
    if email_type == "Automatic":
        body += f"HAZARD DETAILS:\nDetected Issue: {', '.join(harmful_params)}\nRecommendation:  {message}\n"
    else:
        body += f"MESSAGE: {message}\n"
    
    body += "=================================================\n"
    
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls(context=context)
                server.login(sender, password)
                server.sendmail(sender, recipient, msg.as_string())
            logging.info(f"Email Sent [{email_type}] - Status: {status} - Harmful Params: {harmful_params} - Confirmation: Delivered to {recipient}")
            break
        except Exception as e:
            logging.error(f"Email Dispatch Error [{email_type}] attempt {attempt+1}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(3)  # Wait 3 seconds before network retry
            else:
                logging.error(f"FATAL: Failed to send {email_type} email after {max_retries} attempts.")

def send_email_async(email_type, status, ml_status, harmful_params, message, sensor_data, timestamp):
    """Spawns an asynchronous daemon thread."""
    thread = threading.Thread(target=_send_email_task, args=(email_type, status, ml_status, harmful_params, message, sensor_data, timestamp))
    thread.daemon = True
    thread.start()

# ================= Sensor Evaluation Logic =================
def evaluate_sensor(name, val):
    if name == 'co2': return 'DANGER' if val > 2000 else 'WARNING' if val > 1000 else 'SAFE'
    elif name == 'lpg': return 'DANGER' if val > 500 else 'WARNING' if val >= 200 else 'SAFE'
    elif name == 'smoke': return 'DANGER' if val > 300 else 'WARNING' if val >= 100 else 'SAFE'
    elif name == 'temperature': return 'DANGER' if val > 45 else 'WARNING' if val < 18 or val >= 35 else 'SAFE'
    elif name == 'humidity': return 'DANGER' if val > 85 else 'WARNING' if val < 30 or val >= 70 else 'SAFE'
    elif name == 'soil_moisture': return 'DANGER' if val > 85 or val < 15 else 'WARNING' if val >= 75 or val <= 25 else 'SAFE'
    return 'SAFE'

# ================= Flask Routes =================
@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/sensor-data', methods=['POST'])
def receive_sensor_data():
    global latest_data, previous_status, previous_harmful_params
    
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "Invalid or missing JSON"}), 400
            
        co2 = float(data.get('co2', 0))
        # Validation layer for CO2
        if co2 < 0 or co2 > 10000:
            return jsonify({"error": "Invalid CO2 sensor reading"}), 400
            
        lpg = float(data.get('lpg', 0))
        smoke = float(data.get('smoke', 0))
        temp = float(data.get('temperature', 0))
        hum = float(data.get('humidity', 0))
        moist = float(data.get('soil_moisture', 0))
        
        statuses = {
            'CO2': evaluate_sensor('co2', co2),
            'LPG': evaluate_sensor('lpg', lpg),
            'Smoke': evaluate_sensor('smoke', smoke),
            'Temperature': evaluate_sensor('temperature', temp),
            'Humidity': evaluate_sensor('humidity', hum),
            'Soil Moisture': evaluate_sensor('soil_moisture', moist)
        }
        
        overall_status = 'SAFE'
        harmful_params = []
        
        if 'DANGER' in statuses.values():
            overall_status = 'DANGER'
            harmful_params = [k for k, v in statuses.items() if v == 'DANGER']
        elif 'WARNING' in statuses.values():
            overall_status = 'WARNING'
            harmful_params = [k for k, v in statuses.items() if v == 'WARNING']
            
        if overall_status == 'SAFE':
            message = "Current environment conditions are within safe limits."
            harmful_parameter_str = "None"
        else:
            param_list = " and ".join(harmful_params)
            status_word = overall_status.capitalize()
            message = f"{status_word}: Abnormal {param_list} levels detected"
            
            # Specific custom overrides
            if 'CO2' in harmful_params and overall_status == 'WARNING':
                message = "Warning: Elevated CO2 level detected"
            elif 'CO2' in harmful_params and overall_status == 'DANGER':
                message = "Danger: High CO2 concentration detected at the dumpyard"
            elif 'LPG' in harmful_params and overall_status == 'DANGER':
                message = "Danger: High LPG level detected at the dumpyard"
            elif 'Soil Moisture' in harmful_params and overall_status == 'WARNING':
                message = "Warning: High Soil Moisture indicating possible liquid leakage"
            elif 'Temperature' in harmful_params and 'Smoke' in harmful_params and overall_status == 'DANGER':
                message = "Danger: High Temperature and Smoke levels detected"
                
            harmful_parameter_str = ", ".join(harmful_params)
            
        # ML MODEL INFERENCE
        ml_prediction_str = "SAFE"
        if ml_model:
            try:
                # Features: co2, lpg, smoke, temp, humidity (matching training script)
                features = np.array([[co2, lpg, smoke, temp, hum]])
                pred = ml_model.predict(features)[0]
                status_map = {0: "SAFE", 1: "WARNING", 2: "DANGER"}
                ml_prediction_str = status_map.get(pred, "SAFE")
                logging.info(f"ML Inference Result: {ml_prediction_str}")
            except Exception as e:
                logging.error(f"ML Inference Error: {e}")

        # AUTOMATIC EMAIL TRIGGER LOGIC
        is_escalation = False
        if overall_status in ['WARNING', 'DANGER']:
            if previous_status == 'SAFE':
                is_escalation = True
            elif previous_status == 'WARNING' and overall_status == 'DANGER':
                is_escalation = True
            else:
                new_params = set(harmful_params) - set(previous_harmful_params)
                if len(new_params) > 0:
                    is_escalation = True
                    
        if is_escalation:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.warning(f"AUTOMATIC TRIGGER: Status={overall_status}, Harmful={harmful_params}, ML={ml_prediction_str}")
            send_email_async("Automatic", overall_status, ml_prediction_str, harmful_params, message, data, ts)
            
        previous_status = overall_status
        previous_harmful_params = harmful_params
        
        latest_data = {
            "co2": co2, "lpg": lpg, "smoke": smoke, "temperature": temp, "humidity": hum, "soil_moisture": moist,
            "status": overall_status, "ml_status": ml_prediction_str, "harmful_parameter": harmful_parameter_str, "message": message
        }
        
        return jsonify({
            "status": overall_status, 
            "ml_status": ml_prediction_str,
            "harmful_parameter": harmful_parameter_str, 
            "message": message
        }), 200

    except Exception as e:
        logging.error(f"Backend Server Crash Exception: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/send-manual-email', methods=['POST'])
def handle_manual_email():
    """Triggered by the frontend UI manual button click."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"MANUAL EMAIL TRIGGER INITIATED from UI.")
    
    # Send snapshot of current global state
    harmful_list = latest_data["harmful_parameter"].split(", ") if latest_data["harmful_parameter"] != "None" else []
    send_email_async("Manual", latest_data["status"], latest_data["ml_status"], harmful_list, latest_data["message"], latest_data, ts)
    
    return jsonify({"success": "Email dispatched to thread"}), 200

@app.route('/current-status', methods=['GET'])
def get_current_status():
    return jsonify(latest_data)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    logging.info(f"Initializing Internet listener on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
