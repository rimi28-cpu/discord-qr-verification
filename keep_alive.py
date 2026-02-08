"""
Keep-alive server for Replit
Prevents the bot from going to sleep
"""

from flask import Flask, render_template_string
from threading import Thread
import os

app = Flask('')

# HTML template for the status page
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Discord QR Verification Bot</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            padding: 50px;
            margin: 0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        .container {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            max-width: 600px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        h1 {
            font-size: 2.5em;
            margin-bottom: 20px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
        }
        .status {
            font-size: 1.2em;
            margin: 20px 0;
            padding: 15px;
            background: rgba(0, 255, 0, 0.2);
            border-radius: 10px;
            border: 2px solid rgba(0, 255, 0, 0.3);
        }
        .info {
            text-align: left;
            margin: 20px 0;
            padding: 20px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
        }
        .command {
            background: rgba(255, 255, 255, 0.2);
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
            font-family: monospace;
        }
        .footer {
            margin-top: 30px;
            font-size: 0.9em;
            opacity: 0.8;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔐 Discord QR Verification Bot</h1>
        <div class="status">✅ Bot is running and ready!</div>
        
        <div class="info">
            <h3>📋 Bot Information:</h3>
            <p><strong>Status:</strong> Active ✅</p>
            <p><strong>Uptime:</strong> {{ uptime }}</p>
            <p><strong>Commands Available:</strong></p>
            
            <div class="command">!verify [@user]</div>
            <p>Start verification process for a user</p>
            
            <div class="command">!verifystatus</div>
            <p>Check current verification status</p>
            
            <div class="command">!verifycancel</div>
            <p>Cancel current verification</p>
            
            <div class="command">!verifyhelp</div>
            <p>Show help information</p>
        </div>
        
        <div class="footer">
            <p>This bot is powered by Discord QR Login System</p>
            <p>For support, contact the server administrator</p>
        </div>
    </div>
</body>
</html>
"""

import time
start_time = time.time()

def get_uptime():
    """Calculate and format uptime"""
    seconds = int(time.time() - start_time)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m {seconds}s"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

@app.route('/')
def home():
    """Main status page"""
    return render_template_string(HTML_TEMPLATE, uptime=get_uptime())

@app.route('/health')
def health():
    """Health check endpoint"""
    return "OK", 200

@app.route('/status')
def status():
    """Simple status endpoint"""
    return {
        "status": "online",
        "uptime": get_uptime(),
        "service": "discord-qr-verification-bot"
    }

def run():
    """Run the Flask server"""
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    """Start the keep-alive server in a thread"""
    t = Thread(target=run, daemon=True)
    t.start()
    print(f"✅ Keep-alive server started on port 8080")
