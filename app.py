#!/usr/bin/env python3
"""
Juspay Payload Extractor Server
Simple backend to extract ___payload from Juspay payment pages
"""

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from playwright.sync_api import sync_playwright
import json
import logging
import traceback
from datetime import datetime
import os

# Setup logging
LOG_FILE = 'juspay_extractor.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Request log storage
REQUEST_LOGS = []

app = Flask(__name__)
CORS(app)

HTML_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Juspay Payload Extractor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            min-height: 100vh;
            padding: 20px;
            position: relative;
        }
        .signature {
            position: fixed;
            top: 20px;
            right: 20px;
            color: #ffffff;
            font-size: 14px;
            z-index: 1000;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #58a6ff; margin-bottom: 24px; font-size: 28px; }
        .input-section {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .input-group { display: flex; gap: 12px; }
        input[type="text"] {
            flex: 1;
            padding: 12px 16px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 8px;
            color: #c9d1d9;
            font-size: 14px;
            outline: none;
        }
        input[type="text"]:focus { border-color: #58a6ff; }
        button {
            padding: 12px 24px;
            background: #238636;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
        }
        button:hover { background: #2ea043; }
        button:disabled { background: #30363d; cursor: not-allowed; }
        button.secondary { background: #1f6feb; }
        button.secondary:hover { background: #388bfd; }
        .editor-section {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            overflow: hidden;
        }
        .editor-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background: #21262d;
            border-bottom: 1px solid #30363d;
        }
        .editor-title { font-size: 14px; font-weight: 500; color: #8b949e; }
        .editor-actions { display: flex; gap: 8px; }
        .icon-btn {
            padding: 6px 12px;
            background: #30363d;
            border: none;
            border-radius: 6px;
            color: #c9d1d9;
            font-size: 12px;
            cursor: pointer;
        }
        .icon-btn:hover { background: #484f58; }
        .status {
            padding: 12px 16px;
            font-size: 14px;
            border-bottom: 1px solid #30363d;
        }
        .status.success { background: rgba(35, 134, 54, 0.1); color: #3fb950; }
        .status.error { background: rgba(248, 81, 73, 0.1); color: #f85149; }
        .status.info { background: rgba(88, 166, 255, 0.1); color: #58a6ff; }
        textarea {
            width: 100%;
            min-height: 500px;
            padding: 16px;
            background: #0d1117;
            border: none;
            color: #c9d1d9;
            font-family: 'SF Mono', Monaco, monospace;
            font-size: 13px;
            line-height: 1.6;
            resize: vertical;
            outline: none;
        }
        .hidden { display: none; }
        .spinner {
            width: 16px;
            height: 16px;
            border: 2px solid transparent;
            border-top-color: currentColor;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            display: inline-block;
            margin-right: 8px;
            vertical-align: middle;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .modal-overlay {
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0, 0, 0, 0.8);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .modal-overlay.active { display: flex; }
        .modal-content {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            width: 90%;
            max-width: 1200px;
            max-height: 80%;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .modal-header {
            padding: 16px;
            background: #21262d;
            border-bottom: 1px solid #30363d;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .modal-close {
            background: #da3633;
            border: none;
            color: white;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
        }
        .modal-body {
            padding: 16px;
            overflow-y: auto;
            max-height: 60vh;
        }
        .log-entry {
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 12px;
        }
        .log-time { color: #58a6ff; font-size: 12px; }
        .log-url { color: #3fb950; font-size: 13px; margin: 4px 0; }
        .log-status-success { color: #3fb950; }
        .log-status-error { color: #f85149; }
        .log-error {
            color: #f85149;
            font-size: 12px;
            margin-top: 8px;
            padding: 8px;
            background: rgba(248, 81, 73, 0.1);
            border-radius: 4px;
            white-space: pre-wrap;
        }
    </style>
</head>
<body>
    <div class="signature"><strong>Created by Ajinkya Joshi</strong></div>
    <div class="container">
        <h1>Juspay Payload Extractor</h1>
        <div class="input-section">
            <div class="input-group">
                <input type="text" id="urlInput" placeholder="Enter Juspay URL"
                    onkeypress="if(event.key==='Enter')extractPayload()">
                <button id="fetchBtn" onclick="extractPayload()">
                    <span id="btnText">Extract Payload</span>
                </button>
                <button class="secondary" onclick="showLogs()">View Logs</button>
            </div>
        </div>
        <div class="editor-section">
            <div class="editor-header">
                <span class="editor-title">Payload</span>
                <div class="editor-actions">
                    <button class="icon-btn" onclick="copyToClipboard()">Copy</button>
                    <button class="icon-btn" onclick="clearEditor()">Clear</button>
                    <button class="icon-btn" onclick="downloadPayload()">Download</button>
                </div>
            </div>
            <div id="status" class="status hidden"></div>
            <textarea id="payloadEditor" placeholder="Payload will appear here..."></textarea>
        </div>
    </div>
    <div id="logsModal" class="modal-overlay">
        <div class="modal-content">
            <div class="modal-header">
                <span>Request Logs</span>
                <button class="modal-close" onclick="hideLogs()">Close</button>
            </div>
            <div class="modal-body" id="logsContainer"></div>
        </div>
    </div>
    <script>
        const urlInput = document.getElementById('urlInput');
        const payloadEditor = document.getElementById('payloadEditor');
        const fetchBtn = document.getElementById('fetchBtn');
        const btnText = document.getElementById('btnText');
        const statusDiv = document.getElementById('status');

        async function extractPayload() {
            const url = urlInput.value.trim();
            if (!url) { showStatus('Please enter a URL', 'error'); return; }

            setLoading(true);
            showStatus('Extracting payload...', 'info');

            try {
                const response = await fetch('/api/extract', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });
                const result = await response.json();

                if (result.success) {
                    payloadEditor.value = JSON.stringify(result.payload, null, 2);
                    showStatus(`Success: ${result.source}`, 'success');
                } else {
                    showStatus(result.error || 'Failed', 'error');
                    payloadEditor.value = result.details || '';
                }
            } catch (e) {
                showStatus('Error: ' + e.message, 'error');
            } finally {
                setLoading(false);
            }
        }

        async function showLogs() {
            document.getElementById('logsModal').classList.add('active');
            try {
                const response = await fetch('/api/logs');
                const logs = await response.json();
                const container = document.getElementById('logsContainer');
                if (logs.length === 0) {
                    container.innerHTML = '<p style="text-align:center;color:#8b949e;">No logs</p>';
                    return;
                }
                container.innerHTML = logs.map(log => `
                    <div class="log-entry">
                        <div class="log-time">${log.time}</div>
                        <div class="log-url">${log.url}</div>
                        <div class="${log.success?'log-status-success':'log-status-error'}">
                            ${log.success?'SUCCESS':'FAILED'}
                        </div>
                        ${log.source?`<div style="color:#8b949e;font-size:12px;">${log.source}</div>`:''}
                        ${log.error?`<div class="log-error">${log.error}</div>`:''}
                    </div>
                `).join('');
            } catch (e) {
                document.getElementById('logsContainer').innerHTML = '<p style="color:#f85149;">Failed to load</p>';
            }
        }

        function hideLogs() { document.getElementById('logsModal').classList.remove('active'); }
        function setLoading(loading) {
            fetchBtn.disabled = loading;
            btnText.innerHTML = loading ? '<span class="spinner"></span>Extracting...' : 'Extract Payload';
        }
        function showStatus(msg, type) { statusDiv.textContent = msg; statusDiv.className = `status ${type}`; statusDiv.classList.remove('hidden'); }
        function copyToClipboard() { payloadEditor.select(); document.execCommand('copy'); event.target.textContent='Copied!'; setTimeout(()=>event.target.textContent='Copy',1500); }
        function clearEditor() { payloadEditor.value = ''; statusDiv.classList.add('hidden'); }
        function downloadPayload() {
            if (!payloadEditor.value) { showStatus('Nothing to download', 'error'); return; }
            const blob = new Blob([payloadEditor.value], {type:'application/json'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a'); a.href=url; a.download='payload.json';
            document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
            showStatus('Downloaded', 'success');
        }
    </script>
</body>
</html>
'''

def extract_payload_from_url(url):
    """Extract payload using Playwright"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until='networkidle')
        page.wait_for_timeout(8000)  # Wait for SDK to load

        page_content = page.content()
        if 'session expired' in page_content.lower():
            browser.close()
            return {'error': 'ORDER_EXPIRED', 'details': 'Payment session expired'}

        # Extract all payloads
        result = page.evaluate("""() => {
            const payloads = [];

            function scan(win, path) {
                try {
                    // Check for __payload
                    if (win.__payload) {
                        const hasPaymentPage = JSON.stringify(win.__payload).includes('"action":"paymentPage"');
                        payloads.push({
                            source: path + '.__payload',
                            data: win.__payload,
                            hasPaymentPage: hasPaymentPage
                        });
                    }
                    // Check for in.juspay.hyperpay
                    if (win.in && win.in.juspay && win.in.juspay.hyperpay) {
                        payloads.push({
                            source: path + '.in.juspay.hyperpay',
                            data: win.in.juspay.hyperpay
                        });
                    }
                } catch (e) {}

                // Scan frames
                try {
                    for (let i = 0; i < win.frames.length; i++) {
                        scan(win.frames[i], path + '.frames[' + i + ']');
                    }
                } catch (e) {}
            }

            scan(window, 'window');

            // Get ssr_payload as well
            if (window.ssr_payload) {
                payloads.push({
                    source: 'window.ssr_payload',
                    data: window.ssr_payload
                });
            }

            if (payloads.length > 0) {
                // Find paymentPage payload or use first
                const paymentPage = payloads.find(p => p.hasPaymentPage);
                const best = paymentPage || payloads[0];

                return {
                    found: true,
                    source: best.source + (paymentPage ? ' [action: paymentPage]' : ''),
                    allPayloads: payloads,
                    payload: payloads.length > 1 ? { BEST_MATCH: best.data, ALL_PAYLOADS: payloads } : best.data
                };
            }

            return { found: false };
        }""")

        browser.close()
        return result

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/api/logs')
def get_logs():
    return jsonify(REQUEST_LOGS)

@app.route('/api/extract', methods=['POST'])
def api_extract():
    data = request.get_json()
    url = data.get('url', '')

    log_entry = {
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'url': url,
        'success': False,
        'error': None,
        'source': None
    }

    if not url:
        log_entry['error'] = 'No URL'
        REQUEST_LOGS.append(log_entry)
        return jsonify({'success': False, 'error': 'No URL provided'})

    try:
        logger.info(f"Processing: {url}")
        result = extract_payload_from_url(url)

        if result.get('error') == 'ORDER_EXPIRED':
            log_entry['error'] = 'Expired'
            REQUEST_LOGS.append(log_entry)
            return jsonify({'success': False, 'error': 'Order expired', 'details': result['details']})

        if result.get('found'):
            log_entry['success'] = True
            log_entry['source'] = result['source']
            REQUEST_LOGS.append(log_entry)
            logger.info(f"Success: {result['source']}")
            return jsonify({'success': True, 'source': result['source'], 'payload': result['payload']})
        else:
            log_entry['error'] = 'Not found'
            REQUEST_LOGS.append(log_entry)
            return jsonify({'success': False, 'error': 'Payload not found'})

    except Exception as e:
        error_msg = traceback.format_exc()
        log_entry['error'] = str(e)
        REQUEST_LOGS.append(log_entry)
        logger.error(f"Error: {e}")
        return jsonify({'success': False, 'error': str(e), 'details': error_msg})

if __name__ == '__main__':
    print("Server starting...")
    print(f"Open: http://localhost:5000")
    print(f"Logs: {os.path.abspath(LOG_FILE)}")
    app.run(host='0.0.0.0', port=5000, debug=False)
