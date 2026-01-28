"""
Gaming Content Agent - Web Frontend
Lokalni webove rozhrani pro spousteni agenta
"""

import os
import re
import sys
import json
import threading
import subprocess
from flask import Flask, render_template_string, make_response, request

from article_writer import parse_topics_from_report, scrape_full_article, write_article

app = Flask(__name__)

agent_running = False
agent_thread = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gaming Content Agent</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #13a4ec;
            --background: #101c22;
            --console-bg: #1e1e1e;
            --header-bg: #181818;
            --input-bg: #282828;
            --terminal-green: #4ade80;
            --terminal-red: #f87171;
            --terminal-yellow: #fbbf24;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Inter', sans-serif;
            background: var(--background);
            color: #d1d5db;
            min-height: 100vh;
            padding: 1rem;
        }

        .container {
            max-width: 1800px;
            margin: 0 auto;
        }

        .main-grid {
            display: grid;
            grid-template-columns: 1fr 320px;
            gap: 1rem;
            min-height: calc(100vh - 2rem);
        }

        .main-column {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            min-height: 0;
        }

        .main-column .console {
            flex: 1;
            min-height: 300px;
        }

        @media (max-width: 1200px) {
            .main-grid {
                grid-template-columns: 1fr;
                height: auto;
            }
        }

        .console {
            background: var(--console-bg);
            border-radius: 0.5rem;
            overflow: hidden;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.05);
            display: flex;
            flex-direction: column;
        }

        .console-header {
            background: var(--header-bg);
            padding: 0.75rem 1.5rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            flex-shrink: 0;
        }

        .window-controls { display: flex; gap: 0.5rem; }
        .dot { width: 12px; height: 12px; border-radius: 50%; }
        .dot.red { background: rgba(239, 68, 68, 0.8); }
        .dot.yellow { background: rgba(234, 179, 8, 0.8); }
        .dot.green { background: rgba(34, 197, 94, 0.8); }

        .console-title {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.875rem;
            color: white;
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .console-title span.path { color: var(--primary); }

        .status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--terminal-green);
        }

        .status-dot.running {
            animation: pulse 1s infinite;
            background: var(--terminal-yellow);
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }

        .console-body {
            padding: 1rem 1.5rem;
            flex: 1;
            overflow-y: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            line-height: 1.8;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .success { color: var(--terminal-green); }
        .error { color: var(--terminal-red); }
        .warning { color: var(--terminal-yellow); }
        .info { color: var(--primary); }
        .dim { color: #6b7280; }

        .link {
            color: var(--primary);
            text-decoration: none;
            border-bottom: 1px dashed var(--primary);
            transition: all 0.2s;
        }
        .link:hover {
            color: #fff;
            border-bottom-color: #fff;
        }

        .console-footer {
            background: var(--header-bg);
            padding: 0.75rem 1.5rem;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-shrink: 0;
        }

        .prompt {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.875rem;
            color: var(--primary);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .cursor { animation: blink 1s step-end infinite; }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
        }

        .actions { display: flex; gap: 0.75rem; }

        .btn {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            padding: 0.5rem 1.25rem;
            border: none;
            border-radius: 0.25rem;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: #0d8fd4; }
        .btn-primary:disabled { background: #374151; color: #6b7280; cursor: not-allowed; }
        .btn-secondary { background: var(--input-bg); color: #9ca3af; }
        .btn-secondary:hover { background: #374151; color: white; }

        /* Sidebar */
        .sidebar {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            overflow: hidden;
        }

        .panel {
            background: var(--console-bg);
            border-radius: 0.5rem;
            border: 1px solid rgba(255, 255, 255, 0.05);
            overflow: hidden;
        }

        .panel-header {
            background: var(--header-bg);
            padding: 0.6rem 1rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            color: var(--primary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .panel-body {
            padding: 0.75rem;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.5rem;
        }

        .stat-item {
            background: var(--input-bg);
            padding: 0.6rem;
            border-radius: 0.25rem;
            text-align: center;
        }

        .stat-item .value {
            font-size: 1.1rem;
            font-weight: 700;
            color: white;
            font-family: 'JetBrains Mono', monospace;
        }

        .stat-item .label {
            font-size: 0.6rem;
            color: #6b7280;
            text-transform: uppercase;
            margin-top: 0.15rem;
        }

        /* History */
        .history-list {
            max-height: calc(100vh - 280px);
            overflow-y: auto;
        }

        .history-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.6rem 0.75rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            cursor: pointer;
            transition: background 0.2s;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
        }

        .history-item:hover {
            background: var(--input-bg);
        }

        .history-item.active {
            background: rgba(19, 164, 236, 0.1);
            border-left: 2px solid var(--primary);
        }

        .history-date { color: #9ca3af; }
        .history-time { color: var(--terminal-green); font-size: 0.6rem; }

        .history-btn {
            padding: 0.2rem 0.4rem;
            font-size: 0.6rem;
            background: var(--input-bg);
            border: none;
            border-radius: 0.125rem;
            color: #9ca3af;
            cursor: pointer;
            font-family: 'JetBrains Mono', monospace;
        }

        .history-btn:hover {
            background: var(--primary);
            color: white;
        }

        .no-history {
            color: #6b7280;
            font-size: 0.7rem;
            text-align: center;
            padding: 1.5rem;
        }

        /* Report Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.85);
            z-index: 1000;
            padding: 2rem;
        }

        .modal.active {
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .modal-content {
            background: var(--console-bg);
            border-radius: 0.5rem;
            width: 100%;
            max-width: 1400px;
            max-height: 90vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .modal-header {
            background: var(--header-bg);
            padding: 0.75rem 1.5rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .modal-title {
            font-family: 'JetBrains Mono', monospace;
            color: white;
            font-size: 0.9rem;
        }

        .modal-close {
            background: var(--terminal-red);
            border: none;
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1rem;
        }

        .modal-body {
            padding: 1.5rem;
            overflow-y: auto;
            flex: 1;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            line-height: 1.8;
            white-space: pre-wrap;
            color: #d1d5db;
        }

        /* Topics panel */
        .topics-panel {
            background: var(--console-bg);
            border-radius: 0.5rem;
            border: 1px solid rgba(255, 255, 255, 0.05);
            margin-top: 1rem;
            overflow: hidden;
            display: none;
        }

        .topics-panel.visible { display: block; }

        .topics-panel .panel-header {
            background: var(--header-bg);
            padding: 0.6rem 1rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            color: var(--terminal-green);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .topics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 0.75rem;
            padding: 0.75rem;
        }

        .topic-card {
            background: var(--input-bg);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 0.375rem;
            padding: 0.75rem;
            transition: border-color 0.2s;
        }

        .topic-card:hover { border-color: var(--primary); }

        .topic-card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }

        .topic-card-name {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            font-weight: 600;
            color: white;
            line-height: 1.4;
        }

        .virality-badge {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.6rem;
            padding: 0.15rem 0.4rem;
            border-radius: 0.2rem;
            font-weight: 700;
            white-space: nowrap;
            flex-shrink: 0;
        }

        .virality-high { background: rgba(239, 68, 68, 0.2); color: #f87171; }
        .virality-med { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }
        .virality-low { background: rgba(74, 222, 128, 0.2); color: #4ade80; }

        .topic-card-title {
            font-size: 0.7rem;
            color: #9ca3af;
            margin-bottom: 0.5rem;
            line-height: 1.4;
        }

        .topic-card-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .topic-card-sources {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.6rem;
            color: #6b7280;
        }

        .btn-write {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.65rem;
            padding: 0.35rem 0.75rem;
            border: 1px solid var(--primary);
            background: transparent;
            color: var(--primary);
            border-radius: 0.2rem;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-write:hover { background: var(--primary); color: white; }
        .btn-write:disabled { border-color: #374151; color: #6b7280; cursor: not-allowed; background: transparent; }

        /* Article modal */
        .article-modal {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.85);
            z-index: 1001;
            padding: 2rem;
        }

        .article-modal.active {
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .article-modal-content {
            background: var(--console-bg);
            border-radius: 0.5rem;
            width: 100%;
            max-width: 900px;
            max-height: 90vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .article-modal-header {
            background: var(--header-bg);
            padding: 0.75rem 1.5rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .article-modal-title {
            font-family: 'JetBrains Mono', monospace;
            color: white;
            font-size: 0.85rem;
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            margin-right: 1rem;
        }

        .article-modal-close {
            background: var(--terminal-red);
            border: none;
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1rem;
            flex-shrink: 0;
        }

        .tab-switcher {
            display: flex;
            background: var(--header-bg);
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .tab-btn {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            padding: 0.5rem 1.5rem;
            background: transparent;
            border: none;
            color: #6b7280;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }

        .tab-btn.active { color: var(--primary); border-bottom-color: var(--primary); }
        .tab-btn:hover { color: #d1d5db; }

        .article-body {
            padding: 1.5rem;
            overflow-y: auto;
            flex: 1;
            font-family: 'Inter', sans-serif;
            font-size: 0.9rem;
            line-height: 1.7;
            color: #d1d5db;
        }

        .article-body h2 { color: white; margin: 1rem 0 0.5rem; font-size: 1.1rem; }
        .article-body p { margin-bottom: 0.75rem; }
        .article-body strong { color: white; }

        .article-actions {
            background: var(--header-bg);
            padding: 0.6rem 1.5rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .article-meta {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.6rem;
            color: #6b7280;
        }

        .btn-copy {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            padding: 0.4rem 1rem;
            background: var(--primary);
            border: none;
            color: white;
            border-radius: 0.2rem;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-copy:hover { background: #0d8fd4; }

        .generating-overlay {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 3rem;
            color: #9ca3af;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            min-height: 200px;
        }

        .generating-spinner {
            width: 32px;
            height: 32px;
            border: 3px solid rgba(255, 255, 255, 0.1);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-bottom: 1rem;
        }

        @keyframes spin { to { transform: rotate(360deg); } }

        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: var(--console-bg); }
        ::-webkit-scrollbar-thumb { background: #444; border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: #555; }
    </style>
</head>
<body>
    <div class="container">
        <div class="main-grid">
          <div class="main-column">
            <div class="console">
                <div class="console-header">
                    <div class="window-controls">
                        <div class="dot red"></div>
                        <div class="dot yellow"></div>
                        <div class="dot green"></div>
                    </div>
                    <div class="console-title">
                        <span>gaming_content_agent</span>
                        <span class="path">C:/AI/gaming-content-agent</span>
                    </div>
                    <div class="status">
                        <div class="status-dot" id="statusDot"></div>
                        <span id="statusText">READY</span>
                    </div>
                </div>

                <div class="console-body" id="output"><span class="dim">================================================================================
                      GAMING CONTENT AGENT - Web Frontend
================================================================================</span>

<span class="info">Pripraveno ke spusteni. Klikni na RUN_AGENT nebo vyber zaznam z historie.</span>
</div>

                <div class="console-footer">
                    <div class="prompt">
                        <span>$</span>
                        <span class="cursor">_</span>
                    </div>
                    <div class="actions">
                        <button class="btn btn-secondary" onclick="clearOutput()">CLEAR</button>
                        <button class="btn btn-primary" id="runBtn" onclick="runAgent()">RUN_AGENT</button>
                    </div>
                </div>
            </div>

            <div class="topics-panel" id="topicsPanel">
                <div class="panel-header">TOP TEMATA - WRITE_ARTICLE</div>
                <div class="topics-grid" id="topicsGrid"></div>
            </div>
          </div>

            <div class="sidebar">
                <div class="panel">
                    <div class="panel-header">Statistiky</div>
                    <div class="panel-body">
                        <div class="stats-grid">
                            <div class="stat-item">
                                <div class="value" id="statArticles">0</div>
                                <div class="label">Clanky</div>
                            </div>
                            <div class="stat-item">
                                <div class="value" id="statSources">0</div>
                                <div class="label">Zdroje</div>
                            </div>
                            <div class="stat-item">
                                <div class="value" id="statTime">0s</div>
                                <div class="label">Cas</div>
                            </div>
                            <div class="stat-item">
                                <div class="value" id="statRuns">-</div>
                                <div class="label">Behu</div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="panel" style="flex: 1; display: flex; flex-direction: column;">
                    <div class="panel-header">Historie behu</div>
                    <div class="history-list" id="historyList">
                        <div class="no-history">Nacitam...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="modal" id="modal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title" id="modalTitle">Report</div>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body" id="modalBody"></div>
        </div>
    </div>

    <div class="article-modal" id="articleModal">
        <div class="article-modal-content">
            <div class="article-modal-header">
                <div class="article-modal-title" id="articleModalTitle">Generovany clanek</div>
                <button class="article-modal-close" onclick="closeArticleModal()">&times;</button>
            </div>
            <div class="tab-switcher">
                <button class="tab-btn active" onclick="switchTab('cs')" id="tabCs">CESKY</button>
                <button class="tab-btn" onclick="switchTab('en')" id="tabEn">ENGLISH</button>
            </div>
            <div class="article-body" id="articleBody"></div>
            <div class="article-actions">
                <div class="article-meta" id="articleMeta"></div>
                <button class="btn-copy" onclick="copyArticleHtml()">COPY HTML</button>
            </div>
        </div>
    </div>

    <script>
        let polling = null;
        let startTime = null;
        let timerInterval = null;
        let currentRunId = null;
        let articleResult = null;
        let currentArticleLang = 'cs';
        let articlePolling = null;

        document.addEventListener('DOMContentLoaded', loadHistory);

        function runAgent() {
            const btn = document.getElementById('runBtn');
            const output = document.getElementById('output');
            const statusDot = document.getElementById('statusDot');
            const statusText = document.getElementById('statusText');

            btn.disabled = true;
            btn.innerHTML = 'RUNNING...';
            statusDot.classList.add('running');
            statusText.textContent = 'PROCESSING';
            output.innerHTML = '<span class="info">Spoustim agenta...</span>\\n\\n';
            hideTopics();

            startTime = Date.now();
            timerInterval = setInterval(updateTimer, 1000);

            fetch('/start')
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'started') {
                        polling = setInterval(pollOutput, 500);
                    }
                });
        }

        function pollOutput() {
            fetch('/output')
                .then(r => r.json())
                .then(data => {
                    if (data.lines && data.lines.length > 0) {
                        for (const line of data.lines) {
                            appendLine(line);
                        }
                    }

                    if (data.articles) document.getElementById('statArticles').textContent = data.articles;
                    if (data.sources) document.getElementById('statSources').textContent = data.sources;

                    if (!data.running) {
                        finish(data.success);
                        loadHistory();
                        // Po dokonceni agenta nacti temata z posledniho runu
                        if (data.success) {
                            fetch('/history')
                                .then(r => r.json())
                                .then(h => {
                                    if (h.runs.length > 0) {
                                        loadTopics(h.runs[0].id);
                                    }
                                });
                        }
                    }
                });
        }

        function appendLine(text) {
            const output = document.getElementById('output');
            let html = linkifyUrls(text);

            if (text.includes('OK') || text.includes('HOTOVO') || text.includes('Analyzovano') || text.includes('Pripraveno')) {
                html = '<span class="success">' + html + '</span>';
            } else if (text.includes('ERROR') || text.includes('Chyba') || text.includes('chyba')) {
                html = '<span class="error">' + html + '</span>';
            } else if (text.includes('Kontroluji') || text.includes('Pripravuji') || text.includes('Spusteno') || text.includes('Stahuji')) {
                html = '<span class="info">' + html + '</span>';
            } else if (text.includes('===') || text.includes('---') || text.includes('***')) {
                html = '<span class="dim">' + html + '</span>';
            }

            output.innerHTML += html + '\\n';
            output.scrollTop = output.scrollHeight;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function linkifyUrls(text) {
            const escaped = escapeHtml(text);
            const urlRegex = /(https?:\/\/[^\s<>"')\]]+)/g;
            return escaped.replace(urlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer" class="link">$1</a>');
        }

        function finish(success) {
            clearInterval(polling);
            clearInterval(timerInterval);

            document.getElementById('runBtn').disabled = false;
            document.getElementById('runBtn').innerHTML = 'RUN_AGENT';
            document.getElementById('statusDot').classList.remove('running');
            document.getElementById('statusText').textContent = success ? 'COMPLETED' : 'ERROR';
        }

        function updateTimer() {
            if (startTime) {
                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                document.getElementById('statTime').textContent = elapsed + 's';
            }
        }

        function clearOutput() {
            document.getElementById('output').innerHTML = '<span class="dim">Konzole vymazana.</span>\\n\\n<span class="info">Pripraveno.</span>';
            document.getElementById('statusText').textContent = 'READY';
            hideTopics();
        }

        function loadHistory() {
            fetch('/history')
                .then(r => r.json())
                .then(data => {
                    const list = document.getElementById('historyList');
                    document.getElementById('statRuns').textContent = data.runs.length;

                    if (data.runs.length === 0) {
                        list.innerHTML = '<div class="no-history">Zadna historie</div>';
                        return;
                    }

                    list.innerHTML = data.runs.map(run => {
                        const badge = run.articles > 0
                            ? `<span style="font-size:0.55rem;background:rgba(74,222,128,0.15);color:#4ade80;padding:0.1rem 0.3rem;border-radius:0.15rem;margin-left:0.4rem;">${run.articles} cl.</span>`
                            : '';
                        return `
                        <div class="history-item" onclick="loadRun('${run.id}')">
                            <div>
                                <div class="history-date">${run.date}${badge}</div>
                                <div class="history-time">${run.time}</div>
                            </div>
                            <button class="history-btn" onclick="event.stopPropagation(); openModal('${run.id}')">REPORT</button>
                        </div>`;
                    }).join('');

                    // Pri prvnim nacteni zobraz temata z posledniho runu
                    if (!currentRunId && data.runs.length > 0) {
                        loadTopics(data.runs[0].id);
                    }
                });
        }

        function loadRun(runId) {
            document.getElementById('statusText').textContent = 'LOADING...';

            fetch('/history/' + runId)
                .then(r => r.json())
                .then(data => {
                    const output = document.getElementById('output');
                    output.innerHTML = '<span class="dim">================== ZAZNAM: ' + runId + ' ==================</span>\\n\\n';

                    if (data.report) {
                        output.innerHTML += linkifyUrls(data.report);
                    } else {
                        output.innerHTML += '<span class="warning">Report nenalezen</span>';
                    }

                    document.getElementById('statusText').textContent = 'VIEWING';

                    if (data.articles_count) {
                        document.getElementById('statArticles').textContent = data.articles_count;
                    }

                    loadTopics(runId);
                });
        }

        function openModal(runId) {
            fetch('/history/' + runId)
                .then(r => r.json())
                .then(data => {
                    document.getElementById('modalTitle').textContent = 'Report: ' + runId;
                    document.getElementById('modalBody').innerHTML = linkifyUrls(data.report || 'Report nenalezen');
                    document.getElementById('modal').classList.add('active');
                });
        }

        function closeModal() {
            document.getElementById('modal').classList.remove('active');
        }

        /* ===== Topics & Article Writer ===== */

        function loadTopics(runId) {
            currentRunId = runId;
            fetch('/topics/' + runId)
                .then(r => r.json())
                .then(data => {
                    if (data.error || !data.topics || data.topics.length === 0) {
                        hideTopics();
                        return;
                    }
                    renderTopics(data.topics, runId);
                });
        }

        function hideTopics() {
            document.getElementById('topicsPanel').classList.remove('visible');
        }

        function renderTopics(topics, runId) {
            const grid = document.getElementById('topicsGrid');
            grid.innerHTML = topics.map(t => {
                const score = t.virality_score || 0;
                let badgeClass = 'virality-low';
                if (score >= 80) badgeClass = 'virality-high';
                else if (score >= 50) badgeClass = 'virality-med';

                const sourcesCount = (t.sources || []).length;
                const viewBtn = t.has_article
                    ? `<button class="btn-write" style="border-color:var(--terminal-green);color:var(--terminal-green);" onclick="viewSavedArticle('${runId}', ${t.index})">VIEW_ARTICLE</button>`
                    : '';
                const writeBtn = `<button class="btn-write" onclick="startWriteArticle('${runId}', ${t.index})">WRITE_ARTICLE</button>`;

                return `
                <div class="topic-card">
                    <div class="topic-card-header">
                        <div class="topic-card-name">${escapeHtml(t.topic)}</div>
                        <div class="virality-badge ${badgeClass}">${score}/100</div>
                    </div>
                    <div class="topic-card-title">${escapeHtml(t.title)}</div>
                    <div class="topic-card-footer">
                        <div class="topic-card-sources">${sourcesCount} zdroj${sourcesCount !== 1 ? 'e' : ''}</div>
                        <div style="display:flex;gap:0.4rem;">${viewBtn}${writeBtn}</div>
                    </div>
                </div>`;
            }).join('');

            document.getElementById('topicsPanel').classList.add('visible');
        }

        function startWriteArticle(runId, topicIndex) {
            // Disable all write buttons
            document.querySelectorAll('.btn-write').forEach(btn => {
                btn.disabled = true;
                btn.textContent = 'WAIT...';
            });

            // Show modal with spinner
            const modal = document.getElementById('articleModal');
            document.getElementById('articleModalTitle').textContent = 'Generuji clanek...';
            document.getElementById('articleBody').innerHTML = '<div class="generating-overlay"><div class="generating-spinner"></div><div>Stahuji zdroje a generuji clanek...</div></div>';
            document.getElementById('articleMeta').textContent = '';
            modal.classList.add('active');

            fetch('/write-article', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ run_id: runId, topic_index: topicIndex })
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    document.getElementById('articleBody').innerHTML = '<div class="generating-overlay" style="color: var(--terminal-red);">' + escapeHtml(data.error) + '</div>';
                    enableWriteButtons();
                    return;
                }
                // Poll for result
                articlePolling = setInterval(() => pollArticleOutput(), 1500);
            });
        }

        function pollArticleOutput() {
            fetch('/write-article/output')
                .then(r => r.json())
                .then(data => {
                    if (data.running) return;

                    clearInterval(articlePolling);
                    enableWriteButtons();

                    if (data.error) {
                        document.getElementById('articleBody').innerHTML = '<div class="generating-overlay" style="color: var(--terminal-red);">' + escapeHtml(data.error) + '</div>';
                        return;
                    }

                    if (data.result) {
                        articleResult = data.result;
                        currentArticleLang = 'cs';
                        document.getElementById('articleModalTitle').textContent = 'Vygenerovany clanek';
                        showArticleTab('cs');

                        const meta = [];
                        if (data.result.tokens_in) meta.push('In: ' + data.result.tokens_in);
                        if (data.result.tokens_out) meta.push('Out: ' + data.result.tokens_out);
                        if (data.result.cost) meta.push(data.result.cost);
                        document.getElementById('articleMeta').textContent = meta.join(' | ');

                        // Refresh topics to show VIEW button
                        if (currentRunId) loadTopics(currentRunId);
                    }
                });
        }

        function enableWriteButtons() {
            document.querySelectorAll('.btn-write').forEach(btn => {
                btn.disabled = false;
                btn.textContent = 'WRITE_ARTICLE';
            });
        }

        function viewSavedArticle(runId, topicIndex) {
            const modal = document.getElementById('articleModal');
            document.getElementById('articleModalTitle').textContent = 'Ulozeny clanek';
            document.getElementById('articleBody').innerHTML = '<div class="generating-overlay"><div class="generating-spinner"></div><div>Nacitam...</div></div>';
            document.getElementById('articleMeta').textContent = 'Ulozeno na disku';
            modal.classList.add('active');

            fetch('/articles/' + runId + '/' + topicIndex)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('articleBody').innerHTML = '<div class="generating-overlay" style="color: var(--terminal-red);">' + escapeHtml(data.error) + '</div>';
                        return;
                    }
                    articleResult = data;
                    currentArticleLang = 'cs';
                    showArticleTab('cs');
                });
        }

        function switchTab(lang) {
            currentArticleLang = lang;
            showArticleTab(lang);
        }

        function showArticleTab(lang) {
            document.getElementById('tabCs').classList.toggle('active', lang === 'cs');
            document.getElementById('tabEn').classList.toggle('active', lang === 'en');

            if (articleResult) {
                const html = lang === 'cs' ? articleResult.cs : articleResult.en;
                document.getElementById('articleBody').innerHTML = html || '<div class="generating-overlay">Verze neni k dispozici</div>';
            }
        }

        function closeArticleModal() {
            document.getElementById('articleModal').classList.remove('active');
            if (articlePolling) clearInterval(articlePolling);
        }

        function copyArticleHtml() {
            if (!articleResult) return;
            const html = currentArticleLang === 'cs' ? articleResult.cs : articleResult.en;
            if (!html) return;

            navigator.clipboard.writeText(html).then(() => {
                const btn = document.querySelector('.btn-copy');
                btn.textContent = 'COPIED!';
                setTimeout(() => { btn.textContent = 'COPY HTML'; }, 2000);
            });
        }

        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') {
                closeArticleModal();
                closeModal();
            }
        });
        document.getElementById('modal').addEventListener('click', e => { if (e.target.id === 'modal') closeModal(); });
        document.getElementById('articleModal').addEventListener('click', e => { if (e.target.id === 'articleModal') closeArticleModal(); });
    </script>
</body>
</html>
'''

output_lines = []
output_lock = threading.Lock()
articles_count = 0
sources_count = 0
run_success = False
sent_line_index = 0

# Article writer state
article_writer_state = {
    'running': False,
    'result': None,
    'error': None,
}
article_writer_lock = threading.Lock()


def json_response(data):
    response = make_response(json.dumps(data, ensure_ascii=False))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response


def run_agent_process():
    global agent_running, output_lines, articles_count, sources_count, run_success

    run_success = False

    with output_lock:
        agent_running = True
        output_lines = []
        articles_count = 0
        sources_count = 0

    try:
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'

        process = subprocess.Popen(
            [sys.executable, '-u', os.path.join(BASE_DIR, 'main.py')],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=BASE_DIR,
            env=env,
            bufsize=0
        )

        line_buffer = b''
        while True:
            byte = process.stdout.read(1)
            if not byte:
                break

            if byte == b'\n':
                try:
                    line = line_buffer.decode('utf-8', errors='replace').rstrip()
                except:
                    line = str(line_buffer)

                if line:
                    with output_lock:
                        output_lines.append(line)

                        if 'Analyzováno:' in line or 'Analyzovano:' in line:
                            try:
                                # Podpora obou variant (s háčkem i bez)
                                parts = line.replace('Analyzováno:', 'Analyzovano:').split('Analyzovano:')
                                articles_count = int(parts[1].split()[0])
                            except:
                                pass
                        elif 'Zdroje:' in line:
                            try:
                                sources_count = int(line.split('Zdroje:')[1].split()[0])
                            except:
                                pass
                        elif 'Nalezeno' in line and 'článků' in line:
                            try:
                                # Parsuj "Nalezeno 10 nových článků"
                                parts = line.split()
                                for i, part in enumerate(parts):
                                    if part == 'Nalezeno':
                                        articles_count = int(parts[i+1])
                                        break
                            except:
                                pass

                line_buffer = b''
            else:
                line_buffer += byte

        process.wait()
        run_success = (process.returncode == 0)

        with output_lock:
            if run_success:
                output_lines.append("=" * 70)
                output_lines.append("HOTOVO! Agent dokoncil praci.")
                output_lines.append("=" * 70)
            else:
                output_lines.append(f"Agent skoncil s chybou (kod {process.returncode})")

    except Exception as e:
        with output_lock:
            output_lines.append(f"CHYBA: {str(e)}")
    finally:
        with output_lock:
            agent_running = False


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/start')
def start():
    global agent_thread, sent_line_index

    with output_lock:
        if agent_running:
            return json_response({'status': 'already_running'})
        sent_line_index = 0

    agent_thread = threading.Thread(target=run_agent_process)
    agent_thread.start()

    return json_response({'status': 'started'})


@app.route('/output')
def get_output():
    global sent_line_index

    with output_lock:
        new_lines = output_lines[sent_line_index:]
        sent_line_index = len(output_lines)

        return json_response({
            'lines': new_lines,
            'running': agent_running,
            'success': run_success,
            'articles': articles_count,
            'sources': sources_count
        })


@app.route('/status')
def status():
    with output_lock:
        running = agent_running
    return json_response({'running': running})


@app.route('/history')
def get_history():
    runs = []

    if os.path.exists(OUTPUT_DIR):
        for folder in sorted(os.listdir(OUTPUT_DIR), reverse=True):
            folder_path = os.path.join(OUTPUT_DIR, folder)
            if os.path.isdir(folder_path) and re.match(r'^[\w\-]+$', folder):
                try:
                    date_str = folder[:8]
                    time_str = folder[9:]
                    formatted_date = f"{date_str[6:8]}.{date_str[4:6]}.{date_str[:4]}"
                    formatted_time = f"{time_str[:2]}:{time_str[2:4]}"
                    # Spocitej vygenerovane clanky (article_*_cs.html)
                    article_count = len([f for f in os.listdir(folder_path) if f.startswith('article_') and f.endswith('_cs.html')])
                    runs.append({'id': folder, 'date': formatted_date, 'time': formatted_time, 'articles': article_count})
                except:
                    runs.append({'id': folder, 'date': folder, 'time': '', 'articles': 0})

    return json_response({'runs': runs})


@app.route('/history/<run_id>')
def get_run(run_id):
    if not re.match(r'^[\w\-]+$', run_id):
        return json_response({'error': 'Invalid run_id'}), 400
    run_path = os.path.join(OUTPUT_DIR, run_id)
    result = {'id': run_id, 'report': None, 'articles_count': 0}

    report_path = os.path.join(run_path, 'report.txt')
    if os.path.exists(report_path):
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                result['report'] = f.read()
        except:
            result['report'] = 'Chyba pri cteni reportu'

    articles_path = os.path.join(run_path, 'articles.json')
    if os.path.exists(articles_path):
        try:
            with open(articles_path, 'r', encoding='utf-8') as f:
                articles = json.load(f)
                result['articles_count'] = len(articles)
        except:
            pass

    return json_response(result)


@app.route('/topics/<run_id>')
def get_topics(run_id):
    if not re.match(r'^[\w\-]+$', run_id):
        return json_response({'error': 'Invalid run_id'}), 400

    report_path = os.path.join(OUTPUT_DIR, run_id, 'report.txt')
    if not os.path.exists(report_path):
        return json_response({'error': 'Report not found'}), 404

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report_text = f.read()

        topics = parse_topics_from_report(report_text)

        # Serializovatelna verze
        topics_out = []
        run_dir = os.path.join(OUTPUT_DIR, run_id)
        for i, t in enumerate(topics):
            has_article = os.path.exists(os.path.join(run_dir, f'article_{i}_cs.html'))
            topics_out.append({
                'index': i,
                'topic': t.get('topic', ''),
                'title': t.get('title', ''),
                'angle': t.get('angle', ''),
                'context': t.get('context', ''),
                'hook': t.get('hook', ''),
                'virality': t.get('virality', ''),
                'virality_score': t.get('virality_score', 0),
                'seo_keywords': t.get('seo_keywords', ''),
                'sources': t.get('sources', []),
                'has_article': has_article,
            })

        return json_response({'topics': topics_out, 'run_id': run_id})
    except Exception as e:
        return json_response({'error': str(e)}), 500


@app.route('/write-article', methods=['POST'])
def write_article_endpoint():
    global article_writer_state

    data = request.get_json(force=True)
    run_id = data.get('run_id', '')
    topic_index = data.get('topic_index', 0)

    if not re.match(r'^[\w\-]+$', run_id):
        return json_response({'error': 'Invalid run_id'}), 400

    with article_writer_lock:
        if article_writer_state['running']:
            return json_response({'error': 'Already generating'}), 409

    report_path = os.path.join(OUTPUT_DIR, run_id, 'report.txt')
    if not os.path.exists(report_path):
        return json_response({'error': 'Report not found'}), 404

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report_text = f.read()

        topics = parse_topics_from_report(report_text)
        if topic_index < 0 or topic_index >= len(topics):
            return json_response({'error': 'Invalid topic_index'}), 400

        topic = topics[topic_index]
    except Exception as e:
        return json_response({'error': str(e)}), 500

    # Reset state a spust na pozadi
    with article_writer_lock:
        article_writer_state = {
            'running': True,
            'result': None,
            'error': None,
        }

    def generate():
        try:
            # Stahni zdrojove clanky
            source_texts = []
            for url in topic.get('sources', []):
                text = scrape_full_article(url)
                if text:
                    source_texts.append(text)

            # Generuj clanek
            result = write_article(topic, source_texts)

            if 'error' in result:
                with article_writer_lock:
                    article_writer_state['running'] = False
                    article_writer_state['error'] = result['error']
                return

            # Uloz soubory
            run_dir = os.path.join(OUTPUT_DIR, run_id)
            for lang in ['cs', 'en']:
                html = result.get(lang, '')
                if html:
                    filepath = os.path.join(run_dir, f'article_{topic_index}_{lang}.html')
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(html)

            with article_writer_lock:
                article_writer_state['running'] = False
                article_writer_state['result'] = result

        except Exception as e:
            with article_writer_lock:
                article_writer_state['running'] = False
                article_writer_state['error'] = str(e)

    thread = threading.Thread(target=generate)
    thread.start()

    return json_response({'status': 'started'})


@app.route('/write-article/output')
def write_article_output():
    with article_writer_lock:
        state = dict(article_writer_state)
    return json_response(state)


@app.route('/articles/<run_id>/<int:topic_index>')
def get_saved_article(run_id, topic_index):
    if not re.match(r'^[\w\-]+$', run_id):
        return json_response({'error': 'Invalid run_id'}), 400

    run_dir = os.path.join(OUTPUT_DIR, run_id)
    result = {}

    for lang in ['cs', 'en']:
        filepath = os.path.join(run_dir, f'article_{topic_index}_{lang}.html')
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                result[lang] = f.read()

    if not result:
        return json_response({'error': 'Article not found'}), 404

    return json_response(result)


if __name__ == '__main__':
    print("")
    print("=" * 70)
    print("          GAMING CONTENT AGENT - Web Frontend")
    print("=" * 70)
    print("")
    print("  Server bezi na: http://localhost:5000")
    print("")
    print("=" * 70)

    app.run(debug=False, host='127.0.0.1', port=5000, threaded=True)
