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

from article_writer import parse_topics_from_report, scrape_full_article, write_article, generate_podcast_script
import feed_manager
import wp_publisher
import publish_log

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

        .btn-podcast {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            padding: 0.4rem 1rem;
            background: transparent;
            border: 1px solid var(--terminal-green);
            color: var(--terminal-green);
            border-radius: 0.2rem;
            cursor: pointer;
            transition: all 0.2s;
            margin-right: 0.5rem;
        }

        .btn-podcast:hover { background: var(--terminal-green); color: #000; }
        .btn-podcast:disabled { border-color: #374151; color: #6b7280; cursor: not-allowed; }

        .podcast-content {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            line-height: 1.9;
            white-space: pre-wrap;
        }

        .podcast-content .speaker-alex {
            color: var(--primary);
            font-weight: 600;
        }

        .podcast-content .speaker-maya {
            color: var(--terminal-green);
            font-weight: 600;
        }

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

        /* WordPress publish panel */
        .btn-wp {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            padding: 0.4rem 1rem;
            background: transparent;
            border: 1px solid var(--terminal-yellow);
            color: var(--terminal-yellow);
            border-radius: 0.2rem;
            cursor: pointer;
            transition: all 0.2s;
            margin-right: 0.5rem;
        }

        .btn-wp:hover { background: var(--terminal-yellow); color: #000; }

        .wp-publish-panel {
            display: none;
            background: var(--header-bg);
            border-top: 1px solid rgba(251, 191, 36, 0.3);
            border-bottom: 1px solid rgba(251, 191, 36, 0.3);
            padding: 1rem 1.5rem;
        }

        .wp-publish-panel.visible { display: block; }

        .wp-panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
        }

        .wp-panel-title {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: var(--terminal-yellow);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .wp-panel-close {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.65rem;
            padding: 0.25rem 0.6rem;
            background: transparent;
            border: 1px solid rgba(255, 255, 255, 0.15);
            color: #9ca3af;
            border-radius: 0.2rem;
            cursor: pointer;
        }

        .wp-panel-close:hover { color: white; border-color: rgba(255, 255, 255, 0.3); }

        .wp-field {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 0.5rem;
        }

        .wp-field-label {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.65rem;
            color: #6b7280;
            text-transform: uppercase;
            min-width: 75px;
            flex-shrink: 0;
        }

        .wp-field > input, .wp-field > select {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            padding: 0.4rem 0.6rem;
            background: var(--input-bg);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 0.25rem;
            color: #d1d5db;
            outline: none;
            flex: 1;
        }

        .wp-field > input:focus, .wp-field > select:focus {
            border-color: var(--terminal-yellow);
        }

        .wp-categories-list {
            flex: 1;
            max-height: 120px;
            overflow-y: auto;
            background: var(--input-bg);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 0.25rem;
            padding: 0.3rem 0.5rem;
        }

        .wp-cat-item {
            display: flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.2rem 0;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            color: #d1d5db;
            cursor: pointer;
        }

        .wp-cat-item:hover { color: white; }

        .wp-cat-item input[type="checkbox"] {
            accent-color: var(--terminal-yellow);
            cursor: pointer;
        }

        .wp-cat-item.child {
            padding-left: 1.2rem;
            font-size: 0.65rem;
            color: #9ca3af;
        }

        .wp-lang-badge {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.65rem;
            padding: 0.2rem 0.5rem;
            border-radius: 0.2rem;
            font-weight: 600;
            background: rgba(251, 191, 36, 0.2);
            color: #fbbf24;
        }

        .wp-actions {
            display: flex;
            gap: 0.5rem;
            margin-top: 0.75rem;
        }

        .wp-btn-publish-both {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            padding: 0.4rem 1rem;
            border: 1px solid var(--primary);
            background: transparent;
            color: var(--primary);
            border-radius: 0.2rem;
            cursor: pointer;
            transition: all 0.2s;
        }

        .wp-btn-publish-both:hover { background: var(--primary); color: white; }
        .wp-btn-publish-both:disabled { border-color: #374151; color: #6b7280; cursor: not-allowed; background: transparent; }

        .wp-result {
            margin-top: 0.75rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            padding: 0.5rem 0.75rem;
            border-radius: 0.25rem;
            display: none;
        }

        .wp-result.visible { display: block; }
        .wp-result.success { background: rgba(74, 222, 128, 0.1); color: var(--terminal-green); }
        .wp-result.error { background: rgba(248, 113, 113, 0.1); color: var(--terminal-red); }

        .wp-result a {
            color: var(--primary);
            text-decoration: none;
            border-bottom: 1px dashed var(--primary);
        }

        .wp-result a:hover { color: white; border-bottom-color: white; }

        /* Feed management modal */
        .feeds-modal {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.85);
            z-index: 1002;
            padding: 2rem;
        }

        .feeds-modal.active {
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .feeds-modal-content {
            background: var(--console-bg);
            border-radius: 0.5rem;
            width: 100%;
            max-width: 800px;
            max-height: 90vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .feeds-modal-header {
            background: var(--header-bg);
            padding: 0.75rem 1.5rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .feeds-modal-title {
            font-family: 'JetBrains Mono', monospace;
            color: white;
            font-size: 0.9rem;
        }

        .feeds-modal-close {
            background: var(--terminal-red);
            border: none;
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1rem;
        }

        .feeds-add-form {
            display: flex;
            gap: 0.5rem;
            padding: 0.75rem 1rem;
            background: var(--header-bg);
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            align-items: center;
            flex-wrap: wrap;
        }

        .feeds-add-form input, .feeds-add-form select {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            padding: 0.4rem 0.6rem;
            background: var(--input-bg);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 0.25rem;
            color: #d1d5db;
            outline: none;
        }

        .feeds-add-form input:focus, .feeds-add-form select:focus {
            border-color: var(--primary);
        }

        .feeds-add-form input[name="feed-name"] { width: 140px; }
        .feeds-add-form input[name="feed-url"] { flex: 1; min-width: 200px; }
        .feeds-add-form select { width: 60px; }

        .feeds-list {
            overflow-y: auto;
            flex: 1;
            max-height: 60vh;
        }

        .feed-row {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.6rem 1rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            transition: background 0.15s;
        }

        .feed-row:hover { background: rgba(255, 255, 255, 0.02); }

        .feed-toggle {
            position: relative;
            width: 32px;
            height: 18px;
            flex-shrink: 0;
        }

        .feed-toggle input {
            opacity: 0;
            width: 0;
            height: 0;
        }

        .feed-toggle-slider {
            position: absolute;
            cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background: #374151;
            border-radius: 9px;
            transition: 0.2s;
        }

        .feed-toggle-slider:before {
            content: "";
            position: absolute;
            height: 14px;
            width: 14px;
            left: 2px;
            bottom: 2px;
            background: white;
            border-radius: 50%;
            transition: 0.2s;
        }

        .feed-toggle input:checked + .feed-toggle-slider {
            background: var(--terminal-green);
        }

        .feed-toggle input:checked + .feed-toggle-slider:before {
            transform: translateX(14px);
        }

        .feed-name {
            color: white;
            font-weight: 500;
            min-width: 100px;
        }

        .feed-url {
            color: #6b7280;
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .feed-lang-badge {
            font-size: 0.6rem;
            padding: 0.1rem 0.35rem;
            border-radius: 0.15rem;
            font-weight: 600;
            text-transform: uppercase;
            flex-shrink: 0;
        }

        .feed-lang-en { background: rgba(19, 164, 236, 0.2); color: var(--primary); }
        .feed-lang-cs { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }

        .feed-actions {
            display: flex;
            gap: 0.35rem;
            flex-shrink: 0;
        }

        .feed-btn {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.6rem;
            padding: 0.2rem 0.5rem;
            border: 1px solid rgba(255, 255, 255, 0.15);
            background: transparent;
            color: #9ca3af;
            border-radius: 0.15rem;
            cursor: pointer;
            transition: all 0.15s;
        }

        .feed-btn:hover { background: var(--input-bg); color: white; }
        .feed-btn-del:hover { border-color: var(--terminal-red); color: var(--terminal-red); }
        .feed-btn-save { border-color: var(--terminal-green); color: var(--terminal-green); }
        .feed-btn-save:hover { background: var(--terminal-green); color: #000; }
        .feed-btn-cancel:hover { border-color: var(--terminal-yellow); color: var(--terminal-yellow); }

        .feed-edit-input {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            padding: 0.2rem 0.4rem;
            background: var(--input-bg);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 0.15rem;
            color: #d1d5db;
            outline: none;
        }

        .feed-edit-input:focus { border-color: var(--primary); }

        .feeds-empty {
            color: #6b7280;
            font-size: 0.75rem;
            text-align: center;
            padding: 2rem;
            font-family: 'JetBrains Mono', monospace;
        }

        .feeds-status {
            background: var(--header-bg);
            padding: 0.5rem 1rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.6rem;
            color: #6b7280;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            display: flex;
            justify-content: space-between;
        }

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
            <div class="topics-panel" id="topicsPanel">
                <div class="panel-header">TOP TEMATA - WRITE_ARTICLE</div>
                <div class="topics-grid" id="topicsGrid"></div>
            </div>

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
                    <div style="display:flex;align-items:center;gap:1rem;">
                        <div class="status">
                            <div class="status-dot" id="statusDot"></div>
                            <span id="statusText">READY</span>
                        </div>
                        <div class="actions">
                            <button class="btn btn-secondary" onclick="clearOutput()">CLEAR</button>
                            <button class="btn btn-primary" id="runBtn" onclick="runAgent()">RUN_AGENT</button>
                        </div>
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
                </div>
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

                <div class="panel">
                    <div class="panel-header">RSS Feedy</div>
                    <div class="panel-body" style="text-align:center;">
                        <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#9ca3af;margin-bottom:0.5rem;" id="feedsSummary">-</div>
                        <button class="btn btn-secondary" style="width:100%;font-size:0.7rem;" onclick="openFeedsModal()">MANAGE_FEEDS</button>
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
                <button class="tab-btn" onclick="switchTab('podcast')" id="tabPodcast">PODCAST</button>
            </div>
            <div class="article-body" id="articleBody"></div>
            <div class="wp-publish-panel" id="wpPublishPanel">
                <div class="wp-panel-header">
                    <div class="wp-panel-title">Publish to WordPress</div>
                    <button class="wp-panel-close" onclick="toggleWpPanel()">CLOSE</button>
                </div>
                <div class="wp-field">
                    <div class="wp-field-label">Title</div>
                    <input type="text" id="wpTitle" placeholder="Article title...">
                </div>
                <div class="wp-field">
                    <div class="wp-field-label">Cat CS</div>
                    <div class="wp-categories-list" id="wpCategoriesCs">Loading...</div>
                </div>
                <div class="wp-field">
                    <div class="wp-field-label">Cat EN</div>
                    <div class="wp-categories-list" id="wpCategoriesEn">Loading...</div>
                </div>
                <div class="wp-field">
                    <div class="wp-field-label">Tag CS</div>
                    <select id="wpStatusTagCs" style="flex:1; background:var(--input-bg); color:var(--text-primary); border:1px solid rgba(255,255,255,0.1); border-radius:0.25rem; padding:0.3rem 0.5rem; font-family:'JetBrains Mono',monospace; font-size:0.75rem;">
                        <option value="">-- none --</option>
                    </select>
                </div>
                <div class="wp-field">
                    <div class="wp-field-label">Tag EN</div>
                    <select id="wpStatusTagEn" style="flex:1; background:var(--input-bg); color:var(--text-primary); border:1px solid rgba(255,255,255,0.1); border-radius:0.25rem; padding:0.3rem 0.5rem; font-family:'JetBrains Mono',monospace; font-size:0.75rem;">
                        <option value="">-- none --</option>
                    </select>
                </div>
                <div class="wp-field">
                    <div class="wp-field-label">Score</div>
                    <select id="wpScore" style="flex:1; max-width:80px; background:var(--input-bg); color:var(--text-primary); border:1px solid rgba(255,255,255,0.1); border-radius:0.25rem; padding:0.3rem 0.5rem; font-family:'JetBrains Mono',monospace; font-size:0.75rem;">
                        <option value="3">3</option>
                        <option value="1">1</option>
                        <option value="2">2</option>
                        <option value="4">4</option>
                        <option value="5">5</option>
                    </select>
                    <span style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;color:#6b7280;">1=low 5=top</span>
                </div>
                <div class="wp-field">
                    <div class="wp-field-label">Tags</div>
                    <input type="text" id="wpTags" placeholder="tag1, tag2, tag3">
                </div>
                <div class="wp-field">
                    <div class="wp-field-label">Language</div>
                    <span class="wp-lang-badge" id="wpLang">CS</span>
                </div>
                <div class="wp-field">
                    <div class="wp-field-label">Image</div>
                    <input type="file" id="wpImageFile" accept="image/*" style="flex:1; font-family:'JetBrains Mono',monospace; font-size:0.75rem; color:var(--text-primary);">
                </div>
                <div class="wp-field">
                    <div class="wp-field-label">Caption</div>
                    <input type="text" id="wpImageCaption" placeholder="Image caption (optional)">
                </div>
                <div class="wp-field">
                    <div class="wp-field-label">Source</div>
                    <textarea id="wpSourceInfo" rows="2" placeholder="One source per line&#10;https://... (source URL)" style="resize:vertical;"></textarea>
                </div>
                <div class="wp-actions">
                    <button class="wp-btn-publish-both" onclick="wpPublishBoth()" id="wpBtnPublishBoth">PUBLISH CS+EN</button>
                </div>
                <div class="wp-result" id="wpResult"></div>
            </div>
            <div class="article-actions">
                <div class="article-meta" id="articleMeta"></div>
                <div>
                    <button class="btn-podcast" onclick="generatePodcast()" id="btnPodcast">PODCAST_SCRIPT</button>
                    <button class="btn-wp" onclick="toggleWpPanel()" id="btnWp" style="display:none;">PUBLISH_TO_WP</button>
                    <button class="btn-copy" onclick="copyContent()">COPY</button>
                </div>
            </div>
        </div>
    </div>

    <div class="feeds-modal" id="feedsModal">
        <div class="feeds-modal-content">
            <div class="feeds-modal-header">
                <div class="feeds-modal-title">RSS Feed Management</div>
                <button class="feeds-modal-close" onclick="closeFeedsModal()">&times;</button>
            </div>
            <div class="feeds-add-form">
                <input type="text" name="feed-name" placeholder="Name" id="feedAddName">
                <input type="text" name="feed-url" placeholder="https://..." id="feedAddUrl">
                <select id="feedAddLang">
                    <option value="en">EN</option>
                    <option value="cs">CS</option>
                </select>
                <button class="btn btn-primary" style="font-size:0.7rem;padding:0.4rem 0.8rem;" onclick="addFeed()">ADD</button>
            </div>
            <div class="feeds-list" id="feedsList"></div>
            <div class="feeds-status">
                <span id="feedsCount">-</span>
                <span id="feedsMsg"></span>
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
                const writeBtn = `<button class="btn-write" data-label="SHORT" onclick="startWriteArticle('${runId}', ${t.index}, 'short')">SHORT</button><button class="btn-write" data-label="MEDIUM" onclick="startWriteArticle('${runId}', ${t.index}, 'medium')">MEDIUM</button>`;

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

        function startWriteArticle(runId, topicIndex, length) {
            // Set context for podcast generation
            setArticleContext(runId, topicIndex);

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
            articleResult = { cs: null, en: null, podcast: null };
            modal.classList.add('active');

            fetch('/write-article', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ run_id: runId, topic_index: topicIndex, length: length })
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
                        articleResult.podcast = null;
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
                if (btn.dataset.label) btn.textContent = btn.dataset.label;
            });
        }

        function viewSavedArticle(runId, topicIndex) {
            // Set context for podcast generation
            setArticleContext(runId, topicIndex);

            const modal = document.getElementById('articleModal');
            document.getElementById('articleModalTitle').textContent = 'Ulozeny clanek';
            document.getElementById('articleBody').innerHTML = '<div class="generating-overlay"><div class="generating-spinner"></div><div>Nacitam...</div></div>';
            document.getElementById('articleMeta').textContent = 'Ulozeno na disku';
            modal.classList.add('active');

            // Nacti clanek i pripadny podcast
            Promise.all([
                fetch('/articles/' + runId + '/' + topicIndex).then(r => r.json()),
                fetch('/podcast/' + runId + '/' + topicIndex + '/cs').then(r => r.json()).catch(() => null),
                fetch('/podcast/' + runId + '/' + topicIndex + '/en').then(r => r.json()).catch(() => null)
            ]).then(([articleData, podcastCs, podcastEn]) => {
                if (articleData.error) {
                    document.getElementById('articleBody').innerHTML = '<div class="generating-overlay" style="color: var(--terminal-red);">' + escapeHtml(articleData.error) + '</div>';
                    return;
                }
                articleResult = articleData;
                articleResult.podcast = (podcastCs && podcastCs.script) || (podcastEn && podcastEn.script) || null;
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
            document.getElementById('tabPodcast').classList.toggle('active', lang === 'podcast');

            if (articleResult) {
                if (lang === 'podcast') {
                    if (articleResult.podcast) {
                        document.getElementById('articleBody').innerHTML = formatPodcastScript(articleResult.podcast);
                    } else {
                        document.getElementById('articleBody').innerHTML = '<div class="generating-overlay">Podcast script neni k dispozici.<br><br>Klikni na PODCAST_SCRIPT pro vygenerovani.</div>';
                    }
                } else {
                    const html = lang === 'cs' ? articleResult.cs : articleResult.en;
                    document.getElementById('articleBody').innerHTML = html || '<div class="generating-overlay">Verze neni k dispozici</div>';
                }
            }
        }

        function closeArticleModal() {
            document.getElementById('articleModal').classList.remove('active');
            if (articlePolling) clearInterval(articlePolling);
            if (podcastPolling) clearInterval(podcastPolling);
            // Reset WP publish panel
            document.getElementById('wpPublishPanel').classList.remove('visible');
            const wpResult = document.getElementById('wpResult');
            wpResult.classList.remove('visible', 'success', 'error');
            wpResult.innerHTML = '';
        }

        function copyContent() {
            if (!articleResult) return;
            let content;
            if (currentArticleLang === 'podcast') {
                content = articleResult.podcast || '';
            } else {
                content = currentArticleLang === 'cs' ? articleResult.cs : articleResult.en;
            }
            if (!content) return;

            navigator.clipboard.writeText(content).then(() => {
                const btn = document.querySelector('.btn-copy');
                btn.textContent = 'COPIED!';
                setTimeout(() => { btn.textContent = 'COPY'; }, 2000);
            });
        }

        let currentRunIdForPodcast = null;
        let currentTopicIndexForPodcast = null;
        let podcastPolling = null;
        let currentTopicData = null;

        function setArticleContext(runId, topicIndex) {
            currentRunIdForPodcast = runId;
            currentTopicIndexForPodcast = topicIndex;

            // Load topic metadata for publish log
            currentTopicData = null;
            fetch('/topics/' + runId)
                .then(r => r.json())
                .then(data => {
                    if (data.topics) {
                        const t = data.topics.find(x => x.index === topicIndex);
                        if (t) {
                            currentTopicData = {
                                run_id: runId,
                                topic_index: topicIndex,
                                topic: t.topic || '',
                                suggested_title: t.title || '',
                                virality_score: t.virality_score || 0,
                                seo_keywords: t.seo_keywords || '',
                                sources: t.sources || [],
                                source_count: (t.sources || []).length,
                            };
                        }
                    }
                })
                .catch(() => {});
        }

        function generatePodcast() {
            if (!currentRunIdForPodcast || currentTopicIndexForPodcast === null) {
                alert('Article context not set');
                return;
            }

            const lang = currentArticleLang === 'podcast' ? 'cs' : currentArticleLang;
            const btn = document.getElementById('btnPodcast');
            btn.disabled = true;
            btn.textContent = 'GENERATING...';

            // Prepni na podcast tab a ukaž spinner
            switchTab('podcast');
            document.getElementById('articleBody').innerHTML = '<div class="generating-overlay"><div class="generating-spinner"></div><div>Generuji podcast script...</div></div>';

            fetch('/generate-podcast', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    run_id: currentRunIdForPodcast,
                    topic_index: currentTopicIndexForPodcast,
                    lang: lang
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    document.getElementById('articleBody').innerHTML = '<div class="generating-overlay" style="color: var(--terminal-red);">' + escapeHtml(data.error) + '</div>';
                    btn.disabled = false;
                    btn.textContent = 'PODCAST_SCRIPT';
                    return;
                }
                podcastPolling = setInterval(() => pollPodcastOutput(), 1500);
            });
        }

        function pollPodcastOutput() {
            fetch('/generate-podcast/output')
                .then(r => r.json())
                .then(data => {
                    if (data.running) return;

                    clearInterval(podcastPolling);
                    const btn = document.getElementById('btnPodcast');
                    btn.disabled = false;
                    btn.textContent = 'PODCAST_SCRIPT';

                    if (data.error) {
                        document.getElementById('articleBody').innerHTML = '<div class="generating-overlay" style="color: var(--terminal-red);">' + escapeHtml(data.error) + '</div>';
                        return;
                    }

                    if (data.result && data.result.script) {
                        articleResult.podcast = data.result.script;
                        showArticleTab('podcast');

                        const meta = document.getElementById('articleMeta');
                        const metaParts = [];
                        if (data.result.tokens_in) metaParts.push('In: ' + data.result.tokens_in);
                        if (data.result.tokens_out) metaParts.push('Out: ' + data.result.tokens_out);
                        if (data.result.cost) metaParts.push(data.result.cost);
                        meta.textContent = metaParts.join(' | ');
                    }
                });
        }

        function formatPodcastScript(script) {
            // Zvyrazni ALEX: a MAYA:
            let html = escapeHtml(script);
            html = html.replace(/^(ALEX:)/gm, '<span class="speaker-alex">$1</span>');
            html = html.replace(/^(MAYA:)/gm, '<span class="speaker-maya">$1</span>');
            return '<div class="podcast-content">' + html + '</div>';
        }

        /* ===== Feed Management ===== */

        let feedsData = [];

        function openFeedsModal() {
            document.getElementById('feedsModal').classList.add('active');
            loadFeeds();
        }

        function closeFeedsModal() {
            document.getElementById('feedsModal').classList.remove('active');
        }

        function loadFeeds() {
            fetch('/api/feeds')
                .then(r => r.json())
                .then(data => {
                    feedsData = data.feeds || [];
                    renderFeeds();
                    updateFeedsSummary();
                });
        }

        function updateFeedsSummary() {
            const enabled = feedsData.filter(f => f.enabled).length;
            const total = feedsData.length;
            document.getElementById('feedsSummary').textContent = enabled + '/' + total + ' aktivnich';
        }

        function renderFeeds() {
            const list = document.getElementById('feedsList');
            const enabled = feedsData.filter(f => f.enabled).length;
            document.getElementById('feedsCount').textContent = feedsData.length + ' feedu (' + enabled + ' aktivnich)';

            if (feedsData.length === 0) {
                list.innerHTML = '<div class="feeds-empty">Zadne feedy</div>';
                return;
            }

            list.innerHTML = feedsData.map(f => {
                const langClass = f.lang === 'cs' ? 'feed-lang-cs' : 'feed-lang-en';
                return `
                <div class="feed-row" id="feed-row-${f.id}">
                    <label class="feed-toggle">
                        <input type="checkbox" ${f.enabled ? 'checked' : ''} onchange="toggleFeed('${f.id}', this.checked)">
                        <span class="feed-toggle-slider"></span>
                    </label>
                    <span class="feed-name">${escapeHtml(f.name)}</span>
                    <span class="feed-url" title="${escapeHtml(f.url)}">${escapeHtml(f.url)}</span>
                    <span class="feed-lang-badge ${langClass}">${f.lang}</span>
                    <div class="feed-actions">
                        <button class="feed-btn" onclick="editFeed('${f.id}')">EDIT</button>
                        <button class="feed-btn feed-btn-del" onclick="deleteFeed('${f.id}', '${escapeHtml(f.name)}')">DEL</button>
                    </div>
                </div>`;
            }).join('');
        }

        function toggleFeed(feedId, enabled) {
            fetch('/api/feeds/' + feedId, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: enabled })
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    showFeedsMsg(data.error, true);
                    loadFeeds();
                    return;
                }
                // Update local data
                const f = feedsData.find(f => f.id === feedId);
                if (f) f.enabled = enabled;
                updateFeedsSummary();
                const enabledCount = feedsData.filter(f => f.enabled).length;
                document.getElementById('feedsCount').textContent = feedsData.length + ' feedu (' + enabledCount + ' aktivnich)';
            });
        }

        function addFeed() {
            const name = document.getElementById('feedAddName').value.trim();
            const url = document.getElementById('feedAddUrl').value.trim();
            const lang = document.getElementById('feedAddLang').value;

            if (!name || !url) {
                showFeedsMsg('Vyplnte Name a URL', true);
                return;
            }

            fetch('/api/feeds', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, url, lang })
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    showFeedsMsg(data.error, true);
                    return;
                }
                document.getElementById('feedAddName').value = '';
                document.getElementById('feedAddUrl').value = '';
                showFeedsMsg('Feed pridan: ' + name, false);
                loadFeeds();
            });
        }

        function editFeed(feedId) {
            const f = feedsData.find(f => f.id === feedId);
            if (!f) return;

            const row = document.getElementById('feed-row-' + feedId);
            row.innerHTML = `
                <label class="feed-toggle">
                    <input type="checkbox" ${f.enabled ? 'checked' : ''} disabled>
                    <span class="feed-toggle-slider"></span>
                </label>
                <input class="feed-edit-input" style="min-width:100px;width:120px;" value="${escapeHtml(f.name)}" id="edit-name-${feedId}">
                <input class="feed-edit-input" style="flex:1;min-width:150px;" value="${escapeHtml(f.url)}" id="edit-url-${feedId}">
                <select class="feed-edit-input" style="width:55px;" id="edit-lang-${feedId}">
                    <option value="en" ${f.lang === 'en' ? 'selected' : ''}>EN</option>
                    <option value="cs" ${f.lang === 'cs' ? 'selected' : ''}>CS</option>
                </select>
                <div class="feed-actions">
                    <button class="feed-btn feed-btn-save" onclick="saveEdit('${feedId}')">SAVE</button>
                    <button class="feed-btn feed-btn-cancel" onclick="renderFeeds()">CANCEL</button>
                </div>`;
        }

        function saveEdit(feedId) {
            const name = document.getElementById('edit-name-' + feedId).value.trim();
            const url = document.getElementById('edit-url-' + feedId).value.trim();
            const lang = document.getElementById('edit-lang-' + feedId).value;

            if (!name || !url) {
                showFeedsMsg('Vyplnte Name a URL', true);
                return;
            }

            fetch('/api/feeds/' + feedId, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, url, lang })
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    showFeedsMsg(data.error, true);
                    return;
                }
                showFeedsMsg('Feed ulozen', false);
                loadFeeds();
            });
        }

        function deleteFeed(feedId, feedName) {
            if (!confirm('Smazat feed "' + feedName + '"?')) return;

            fetch('/api/feeds/' + feedId, { method: 'DELETE' })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    showFeedsMsg(data.error, true);
                    return;
                }
                showFeedsMsg('Feed smazan', false);
                loadFeeds();
            });
        }

        function showFeedsMsg(text, isError) {
            const el = document.getElementById('feedsMsg');
            el.textContent = text;
            el.style.color = isError ? 'var(--terminal-red)' : 'var(--terminal-green)';
            setTimeout(() => { el.textContent = ''; }, 3000);
        }

        // Load feed summary on page load
        document.addEventListener('DOMContentLoaded', () => {
            fetch('/api/feeds')
                .then(r => r.json())
                .then(data => {
                    feedsData = data.feeds || [];
                    updateFeedsSummary();
                });
        });

        /* ===== WordPress Publishing ===== */

        let wpConfigured = false;
        let wpCategoriesCache = null;
        let wpStatusTagsLoaded = false;

        // Check WP status on page load
        document.addEventListener('DOMContentLoaded', () => {
            fetch('/api/wp/status')
                .then(r => r.json())
                .then(data => {
                    wpConfigured = data.configured;
                    if (wpConfigured) {
                        document.getElementById('btnWp').style.display = '';
                    }
                })
                .catch(() => {});
        });

        function toggleWpPanel() {
            const panel = document.getElementById('wpPublishPanel');
            const isVisible = panel.classList.contains('visible');

            if (isVisible) {
                panel.classList.remove('visible');
            } else {
                panel.classList.add('visible');
                wpLoadCategories();
                wpLoadStatusTags();
                wpPrefillFields();
            }
        }

        function wpLoadCategories() {
            wpLoadCategoriesForLang('cs', 'wpCategoriesCs');
            wpLoadCategoriesForLang('en', 'wpCategoriesEn');
        }

        function wpLoadCategoriesForLang(lang, containerId) {
            const cacheKey = 'cat_' + lang;
            if (wpCategoriesCache && wpCategoriesCache[cacheKey]) {
                wpRenderCategories(wpCategoriesCache[cacheKey], containerId);
                return;
            }

            const container = document.getElementById(containerId);
            container.innerHTML = 'Loading...';

            fetch('/api/wp/categories?lang=' + lang)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        container.innerHTML = 'Error: ' + escapeHtml(data.error);
                        return;
                    }
                    if (!wpCategoriesCache) wpCategoriesCache = {};
                    wpCategoriesCache[cacheKey] = data.categories;
                    wpRenderCategories(data.categories, containerId);
                })
                .catch(err => {
                    container.innerHTML = 'Error loading categories';
                });
        }

        function wpLoadStatusTags() {
            if (wpStatusTagsLoaded) return;

            fetch('/api/wp/status-tags')
                .then(r => r.json())
                .then(data => {
                    if (data.error) return;
                    wpStatusTagsLoaded = true;
                    let html = '<option value="">-- none --</option>';
                    for (const t of data.status_tags) {
                        html += '<option value="' + escapeHtml(t.id) + '" style="color:' + escapeHtml(t.color) + ';">' + escapeHtml(t.label) + '</option>';
                    }
                    document.getElementById('wpStatusTagCs').innerHTML = html;
                    document.getElementById('wpStatusTagEn').innerHTML = html;
                })
                .catch(() => {});
        }

        function wpRenderCategories(categories, containerId) {
            const container = document.getElementById(containerId);
            const parents = categories.filter(c => c.parent === 0);
            const children = categories.filter(c => c.parent !== 0);

            let html = '';
            for (const p of parents) {
                html += '<label class="wp-cat-item"><input type="checkbox" value="' + p.id + '"> ' + escapeHtml(p.name) + '</label>';
                for (const ch of children) {
                    if (ch.parent === p.id) {
                        html += '<label class="wp-cat-item child"><input type="checkbox" value="' + ch.id + '"> ' + escapeHtml(ch.name) + '</label>';
                    }
                }
            }
            const parentIds = parents.map(p => p.id);
            for (const ch of children) {
                if (!parentIds.includes(ch.parent)) {
                    html += '<label class="wp-cat-item"><input type="checkbox" value="' + ch.id + '"> ' + escapeHtml(ch.name) + '</label>';
                }
            }

            container.innerHTML = html || '<span style="color:#6b7280;">No categories</span>';
        }

        function wpGetSelectedCategories(lang) {
            const containerId = lang === 'en' ? 'wpCategoriesEn' : 'wpCategoriesCs';
            return Array.from(document.querySelectorAll('#' + containerId + ' input[type=checkbox]:checked')).map(cb => parseInt(cb.value));
        }

        function wpPrefillFields() {
            const ignoredTitles = ['Generovany clanek', 'Vygenerovany clanek', 'Ulozeny clanek', 'Generuji clanek...'];

            // 1) topic suggested title from metadata
            if (currentTopicData && currentTopicData.suggested_title) {
                document.getElementById('wpTitle').value = currentTopicData.suggested_title;
            } else {
                // 2) modal title (if not a placeholder)
                const titleEl = document.getElementById('articleModalTitle');
                const title = titleEl ? titleEl.textContent : '';
                if (title && !ignoredTitles.includes(title)) {
                    document.getElementById('wpTitle').value = title;
                } else {
                    // 3) first h2 from article body
                    const body = document.getElementById('articleBody');
                    const h2 = body ? body.querySelector('h2') : null;
                    document.getElementById('wpTitle').value = h2 ? h2.textContent : '';
                }
            }

            // Language from current tab
            const lang = currentArticleLang === 'podcast' ? 'cs' : currentArticleLang;
            document.getElementById('wpLang').textContent = lang.toUpperCase();

            // Show/hide publish both button
            const hasBoth = articleResult && articleResult.cs && articleResult.en;
            document.getElementById('wpBtnPublishBoth').style.display = hasBoth ? '' : 'none';

            // Auto-fill sources (all URLs, one per line)
            const sourceInput = document.getElementById('wpSourceInfo');
            if (currentTopicData && currentTopicData.sources && currentTopicData.sources.length > 0) {
                sourceInput.value = currentTopicData.sources.join('\\n');
            } else {
                sourceInput.value = '';
            }

            // Reset result area
            const resultEl = document.getElementById('wpResult');
            resultEl.classList.remove('visible', 'success', 'error');
            resultEl.innerHTML = '';
        }

        async function wpUploadImage() {
            const fileInput = document.getElementById('wpImageFile');
            if (!fileInput.files || !fileInput.files[0]) return null;

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            const caption = document.getElementById('wpImageCaption').value.trim();
            if (caption) {
                formData.append('caption', caption);
                formData.append('alt_text', caption);
            }

            const resp = await fetch('/api/wp/upload-media', { method: 'POST', body: formData });
            const data = await resp.json();
            if (data.error) throw new Error(data.error);
            return data.media_id;
        }

        async function wpPublishDraft() {
            const btn = document.getElementById('wpBtnPublish');
            btn.disabled = true;
            btn.textContent = 'PUBLISHING...';

            const lang = currentArticleLang === 'podcast' ? 'cs' : currentArticleLang;
            const content = articleResult ? (lang === 'cs' ? articleResult.cs : articleResult.en) : '';

            if (!content) {
                wpShowResult('No content for language: ' + lang.toUpperCase(), true);
                btn.disabled = false;
                btn.textContent = 'PUBLISH DRAFT';
                return;
            }

            try {
                let mediaId = null;
                const fileInput = document.getElementById('wpImageFile');
                if (fileInput.files && fileInput.files[0]) {
                    btn.textContent = 'UPLOADING IMAGE...';
                    mediaId = await wpUploadImage();
                }

                const selectedCats = wpGetSelectedCategories(lang);

                const resp = await fetch('/api/wp/publish', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title: document.getElementById('wpTitle').value,
                        content: content,
                        categories: selectedCats,
                        tags: document.getElementById('wpTags').value,
                        status_tag: document.getElementById(lang === 'en' ? 'wpStatusTagEn' : 'wpStatusTagCs').value,
                        lang: lang,
                        featured_media_id: mediaId,
                        score: parseInt(document.getElementById('wpScore').value) || 3,
                        topic_meta: currentTopicData,
                    })
                });
                const data = await resp.json();
                btn.disabled = false;
                btn.textContent = 'PUBLISH DRAFT';

                if (data.error) {
                    wpShowResult(data.error, true);
                    return;
                }

                wpShowResult(
                    'Draft created! <a href="' + escapeHtml(data.post.edit_url) + '" target="_blank">Edit in WP Admin</a>' +
                    ' | <a href="' + escapeHtml(data.post.view_url) + '" target="_blank">Preview</a>',
                    false
                );
            } catch (err) {
                btn.disabled = false;
                btn.textContent = 'PUBLISH DRAFT';
                wpShowResult('Error: ' + err.message, true);
            }
        }

        async function wpPublishBoth() {
            const btn = document.getElementById('wpBtnPublishBoth');
            btn.disabled = true;
            btn.textContent = 'PUBLISHING...';

            if (!articleResult || !articleResult.cs || !articleResult.en) {
                wpShowResult('Both CS and EN versions are required', true);
                btn.disabled = false;
                btn.textContent = 'PUBLISH CS+EN';
                return;
            }

            try {
                let mediaId = null;
                const fileInput = document.getElementById('wpImageFile');
                if (fileInput.files && fileInput.files[0]) {
                    btn.textContent = 'UPLOADING IMAGE...';
                    mediaId = await wpUploadImage();
                }

                // Extract title for EN — try to get from EN content h2
                const titleCs = document.getElementById('wpTitle').value;
                let titleEn = titleCs;
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = articleResult.en;
                const enH2 = tempDiv.querySelector('h2');
                if (enH2) titleEn = enH2.textContent;

                const selectedCatsCs = wpGetSelectedCategories('cs');
                const selectedCatsEn = wpGetSelectedCategories('en');

                btn.textContent = 'PUBLISHING...';
                const resp = await fetch('/api/wp/publish-both', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title_cs: titleCs,
                        title_en: titleEn,
                        content_cs: articleResult.cs,
                        content_en: articleResult.en,
                        categories_cs: selectedCatsCs,
                        categories_en: selectedCatsEn,
                        tags: document.getElementById('wpTags').value,
                        status_tag_cs: document.getElementById('wpStatusTagCs').value,
                        status_tag_en: document.getElementById('wpStatusTagEn').value,
                        featured_media_id: mediaId,
                        score: parseInt(document.getElementById('wpScore').value) || 3,
                        source_info: document.getElementById('wpSourceInfo').value,
                        topic_meta: currentTopicData,
                    })
                });
                const data = await resp.json();
                btn.disabled = false;
                btn.textContent = 'PUBLISH CS+EN';

                if (data.error) {
                    wpShowResult(data.error, true);
                    return;
                }

                let msg = 'CS draft: <a href="' + escapeHtml(data.post_cs.edit_url) + '" target="_blank">Edit</a>';
                msg += ' | EN draft: <a href="' + escapeHtml(data.post_en.edit_url) + '" target="_blank">Edit</a>';
                if (data.linked) {
                    msg += ' | Polylang linked';
                } else if (data.link_error) {
                    msg += ' | <span style="color:var(--terminal-yellow);">Link warning: ' + escapeHtml(data.link_error) + '</span>';
                }
                wpShowResult(msg, false);
            } catch (err) {
                btn.disabled = false;
                btn.textContent = 'PUBLISH CS+EN';
                wpShowResult('Error: ' + err.message, true);
            }
        }

        async function wpSkipArticle() {
            const btn = document.getElementById('wpBtnSkip');
            btn.disabled = true;
            btn.textContent = 'SKIPPING...';

            try {
                const resp = await fetch('/api/wp/log-skip', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        topic_meta: currentTopicData,
                    })
                });
                const data = await resp.json();
                btn.disabled = false;
                btn.textContent = 'SKIP';

                if (data.error) {
                    wpShowResult(data.error, true);
                    return;
                }

                wpShowResult('Skipped — logged to publish_log.jsonl', false);
            } catch (err) {
                btn.disabled = false;
                btn.textContent = 'SKIP';
                wpShowResult('Error: ' + err.message, true);
            }
        }

        function wpShowResult(html, isError) {
            const el = document.getElementById('wpResult');
            el.innerHTML = html;
            el.classList.remove('success', 'error');
            el.classList.add('visible', isError ? 'error' : 'success');
        }

        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') {
                closeFeedsModal();
                closeArticleModal();
                closeModal();
            }
        });
        document.getElementById('modal').addEventListener('click', e => { if (e.target.id === 'modal') closeModal(); });
        document.getElementById('articleModal').addEventListener('click', e => { if (e.target.id === 'articleModal') closeArticleModal(); });
        document.getElementById('feedsModal').addEventListener('click', e => { if (e.target.id === 'feedsModal') closeFeedsModal(); });
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

# Podcast writer state
podcast_writer_state = {
    'running': False,
    'result': None,
    'error': None,
}
podcast_writer_lock = threading.Lock()


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
    no_articles_path = os.path.join(run_path, 'no_new_articles.txt')
    if os.path.exists(report_path):
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                result['report'] = f.read()
        except:
            result['report'] = 'Chyba pri cteni reportu'
    elif os.path.exists(no_articles_path):
        try:
            with open(no_articles_path, 'r', encoding='utf-8') as f:
                result['report'] = f.read()
        except:
            result['report'] = 'Chyba pri cteni info souboru'

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
    article_length = data.get('length', 'medium')

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
            result = write_article(topic, source_texts, length=article_length)

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


@app.route('/generate-podcast', methods=['POST'])
def generate_podcast_endpoint():
    global podcast_writer_state

    data = request.get_json(force=True)
    run_id = data.get('run_id', '')
    topic_index = data.get('topic_index', 0)
    lang = data.get('lang', 'cs')

    if not re.match(r'^[\w\-]+$', run_id):
        return json_response({'error': 'Invalid run_id'}), 400

    if lang not in ['cs', 'en']:
        return json_response({'error': 'Invalid lang'}), 400

    with podcast_writer_lock:
        if podcast_writer_state['running']:
            return json_response({'error': 'Already generating podcast'}), 409

    # Nacti clanek
    run_dir = os.path.join(OUTPUT_DIR, run_id)
    article_path = os.path.join(run_dir, f'article_{topic_index}_{lang}.html')

    if not os.path.exists(article_path):
        return json_response({'error': 'Article not found. Generate article first.'}), 404

    try:
        with open(article_path, 'r', encoding='utf-8') as f:
            article_html = f.read()
    except Exception as e:
        return json_response({'error': str(e)}), 500

    # Reset state a spust na pozadi
    with podcast_writer_lock:
        podcast_writer_state = {
            'running': True,
            'result': None,
            'error': None,
        }

    def generate():
        try:
            result = generate_podcast_script(article_html, lang)

            if 'error' in result:
                with podcast_writer_lock:
                    podcast_writer_state['running'] = False
                    podcast_writer_state['error'] = result['error']
                return

            # Uloz soubor
            script_path = os.path.join(run_dir, f'podcast_{topic_index}_{lang}.txt')
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(result['script'])

            with podcast_writer_lock:
                podcast_writer_state['running'] = False
                podcast_writer_state['result'] = result

        except Exception as e:
            with podcast_writer_lock:
                podcast_writer_state['running'] = False
                podcast_writer_state['error'] = str(e)

    thread = threading.Thread(target=generate)
    thread.start()

    return json_response({'status': 'started'})


@app.route('/generate-podcast/output')
def generate_podcast_output():
    with podcast_writer_lock:
        state = dict(podcast_writer_state)
    return json_response(state)


@app.route('/podcast/<run_id>/<int:topic_index>/<lang>')
def get_saved_podcast(run_id, topic_index, lang):
    if not re.match(r'^[\w\-]+$', run_id):
        return json_response({'error': 'Invalid run_id'}), 400

    if lang not in ['cs', 'en']:
        return json_response({'error': 'Invalid lang'}), 400

    script_path = os.path.join(OUTPUT_DIR, run_id, f'podcast_{topic_index}_{lang}.txt')

    if not os.path.exists(script_path):
        return json_response({'error': 'Podcast script not found'}), 404

    with open(script_path, 'r', encoding='utf-8') as f:
        script = f.read()

    return json_response({'script': script})


## ===== Feed Management API =====

@app.route('/api/feeds', methods=['GET'])
def api_get_feeds():
    feeds = feed_manager.load_feeds()
    return json_response({'feeds': feeds})


@app.route('/api/feeds', methods=['POST'])
def api_add_feed():
    data = request.get_json(force=True)
    name = data.get('name', '')
    url = data.get('url', '')
    lang = data.get('lang', 'en')

    feed, error = feed_manager.add_feed(name, url, lang)
    if error:
        return json_response({'error': error}), 400

    return json_response({'feed': feed})


@app.route('/api/feeds/<feed_id>', methods=['PUT'])
def api_update_feed(feed_id):
    data = request.get_json(force=True)
    kwargs = {}
    for key in ('name', 'url', 'lang', 'enabled'):
        if key in data:
            kwargs[key] = data[key]

    feed, error = feed_manager.update_feed(feed_id, **kwargs)
    if error:
        return json_response({'error': error}), 400

    return json_response({'feed': feed})


@app.route('/api/feeds/<feed_id>', methods=['DELETE'])
def api_delete_feed(feed_id):
    deleted = feed_manager.delete_feed(feed_id)
    if not deleted:
        return json_response({'error': 'Feed not found'}), 404

    return json_response({'ok': True})


@app.route('/api/feeds/validate', methods=['POST'])
def api_validate_feed():
    import feedparser as fp
    data = request.get_json(force=True)
    url = data.get('url', '')

    if not url or not re.match(r'^https?://', url):
        return json_response({'valid': False, 'error': 'Invalid URL'})

    try:
        result = fp.parse(url)
        if result.bozo and not result.entries:
            return json_response({'valid': False, 'error': 'Not a valid RSS feed'})

        return json_response({
            'valid': True,
            'title': result.feed.get('title', ''),
            'entries': len(result.entries),
        })
    except Exception as e:
        return json_response({'valid': False, 'error': str(e)})


## ===== WordPress Publishing API =====

@app.route('/api/wp/status')
def api_wp_status():
    import config
    return json_response({
        'configured': wp_publisher.is_configured(),
        'url': config.WP_URL if wp_publisher.is_configured() else '',
    })


@app.route('/api/wp/categories')
def api_wp_categories():
    if not wp_publisher.is_configured():
        return json_response({'error': 'WordPress not configured'}), 400

    force_refresh = request.args.get('refresh') == '1'
    lang = request.args.get('lang')  # 'cs', 'en', or None
    categories, error = wp_publisher.get_categories(force_refresh=force_refresh, lang=lang)
    if error:
        return json_response({'error': error}), 500

    return json_response({'categories': categories})


@app.route('/api/wp/status-tags')
def api_wp_status_tags():
    if not wp_publisher.is_configured():
        return json_response({'error': 'WordPress not configured'}), 400

    force_refresh = request.args.get('refresh') == '1'
    tags, error = wp_publisher.get_status_tags(force_refresh=force_refresh)
    if error:
        return json_response({'error': error}), 500

    return json_response({'status_tags': tags})


@app.route('/api/wp/upload-media', methods=['POST'])
def api_wp_upload_media():
    if not wp_publisher.is_configured():
        return json_response({'error': 'WordPress not configured'}), 400

    if 'file' not in request.files:
        return json_response({'error': 'No file provided'}), 400

    f = request.files['file']
    if not f.filename:
        return json_response({'error': 'Empty filename'}), 400

    caption = request.form.get('caption', '').strip()
    alt_text = request.form.get('alt_text', '').strip()

    media_id, error = wp_publisher.upload_media_file(
        file_data=f.read(),
        filename=f.filename,
        content_type=f.content_type or 'image/jpeg',
        caption=caption,
        alt_text=alt_text,
    )

    if error:
        return json_response({'error': error}), 500

    return json_response({'media_id': media_id})


@app.route('/api/wp/publish', methods=['POST'])
def api_wp_publish():
    if not wp_publisher.is_configured():
        return json_response({'error': 'WordPress not configured'}), 400

    data = request.get_json(force=True)
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    categories = data.get('categories', [])
    tags_str = data.get('tags', '')
    status_tag = data.get('status_tag', '').strip()
    lang = data.get('lang', '')
    featured_media_id = data.get('featured_media_id')

    if not title or not content:
        return json_response({'error': 'Title and content are required'}), 400

    # Parse tagy
    tag_names = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []

    # Odstraň první heading (WP zobrazuje title zvlášť)
    content = wp_publisher.strip_first_heading(content)

    score = data.get('score', 3)
    source_info = data.get('source_info', '').strip()
    topic_meta = data.get('topic_meta') or {}

    # Vytvoř draft
    result, error = wp_publisher.create_draft(
        title=title,
        content=content,
        category_ids=categories if categories else None,
        tag_names=tag_names if tag_names else None,
        lang=lang if lang else None,
        featured_image_id=featured_media_id,
        status_tag=status_tag if status_tag else None,
        source_info=source_info if source_info else None,
    )

    if error:
        return json_response({'error': error}), 500

    # Log publish decision
    try:
        log_entry = {
            'action': 'published',
            'score': score,
            'run_id': topic_meta.get('run_id', ''),
            'topic_index': topic_meta.get('topic_index', 0),
            'topic': topic_meta.get('topic', ''),
            'suggested_title': topic_meta.get('suggested_title', ''),
            'published_title': title,
            'virality_score': topic_meta.get('virality_score', 0),
            'seo_keywords': topic_meta.get('seo_keywords', ''),
            'sources': topic_meta.get('sources', []),
            'source_count': topic_meta.get('source_count', 0),
            'categories_cs': categories if lang == 'cs' else [],
            'categories_en': categories if lang == 'en' else [],
            'status_tag': status_tag,
            'tags': tags_str,
            'lang': lang,
            'has_image': featured_media_id is not None,
            'wp_post_cs': result.get('id') if lang == 'cs' else None,
            'wp_post_en': result.get('id') if lang == 'en' else None,
        }
        publish_log.log_decision(log_entry)
    except Exception:
        pass  # Don't fail the publish on logging error

    return json_response({'post': result})


@app.route('/api/wp/publish-both', methods=['POST'])
def api_wp_publish_both():
    if not wp_publisher.is_configured():
        return json_response({'error': 'WordPress not configured'}), 400

    data = request.get_json(force=True)
    title_cs = data.get('title_cs', '').strip()
    title_en = data.get('title_en', '').strip()
    content_cs = data.get('content_cs', '').strip()
    content_en = data.get('content_en', '').strip()
    categories_cs = data.get('categories_cs', data.get('categories', []))
    categories_en = data.get('categories_en', data.get('categories', []))
    tags_str = data.get('tags', '')
    status_tag_cs = data.get('status_tag_cs', data.get('status_tag', '')).strip()
    status_tag_en = data.get('status_tag_en', data.get('status_tag', '')).strip()
    featured_media_id = data.get('featured_media_id')
    score = data.get('score', 3)
    source_info = data.get('source_info', '').strip()
    topic_meta = data.get('topic_meta') or {}

    print(f"[publish-both] categories_cs={categories_cs}, categories_en={categories_en}, tags={tags_str}")

    if not title_cs or not content_cs or not title_en or not content_en:
        return json_response({'error': 'Both CS and EN title+content are required'}), 400

    tag_names = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []

    # Odstraň první heading z obou verzí
    content_cs = wp_publisher.strip_first_heading(content_cs)
    content_en = wp_publisher.strip_first_heading(content_en)

    # Vytvoř CS draft
    result_cs, error_cs = wp_publisher.create_draft(
        title=title_cs,
        content=content_cs,
        category_ids=categories_cs if categories_cs else None,
        tag_names=tag_names if tag_names else None,
        lang='cs',
        featured_image_id=featured_media_id,
        status_tag=status_tag_cs if status_tag_cs else None,
        source_info=source_info if source_info else None,
    )
    if error_cs:
        return json_response({'error': f'CS draft failed: {error_cs}'}), 500

    # Vytvoř EN draft
    result_en, error_en = wp_publisher.create_draft(
        title=title_en,
        content=content_en,
        category_ids=categories_en if categories_en else None,
        tag_names=tag_names if tag_names else None,
        lang='en',
        featured_image_id=featured_media_id,
        status_tag=status_tag_en if status_tag_en else None,
        source_info=source_info if source_info else None,
    )
    if error_en:
        return json_response({'error': f'EN draft failed: {error_en}. CS draft was created: {result_cs["edit_url"]}'}), 500

    # Propoj překlady přes Polylang
    link_result, link_error = wp_publisher.link_translations(result_cs['id'], result_en['id'])

    # Log publish decision
    try:
        log_entry = {
            'action': 'published',
            'score': score,
            'run_id': topic_meta.get('run_id', ''),
            'topic_index': topic_meta.get('topic_index', 0),
            'topic': topic_meta.get('topic', ''),
            'suggested_title': topic_meta.get('suggested_title', ''),
            'published_title': title_cs,
            'virality_score': topic_meta.get('virality_score', 0),
            'seo_keywords': topic_meta.get('seo_keywords', ''),
            'sources': topic_meta.get('sources', []),
            'source_count': topic_meta.get('source_count', 0),
            'categories_cs': categories_cs if categories_cs else [],
            'categories_en': categories_en if categories_en else [],
            'status_tag_cs': status_tag_cs,
            'status_tag_en': status_tag_en,
            'tags': tags_str,
            'lang': 'both',
            'has_image': featured_media_id is not None,
            'wp_post_cs': result_cs.get('id'),
            'wp_post_en': result_en.get('id'),
        }
        publish_log.log_decision(log_entry)
    except Exception:
        pass

    return json_response({
        'post_cs': result_cs,
        'post_en': result_en,
        'linked': link_result is not None,
        'link_error': link_error,
    })


@app.route('/api/wp/log-skip', methods=['POST'])
def api_wp_log_skip():
    data = request.get_json(force=True)
    topic_meta = data.get('topic_meta') or {}

    try:
        log_entry = {
            'action': 'skipped',
            'score': 0,
            'run_id': topic_meta.get('run_id', ''),
            'topic_index': topic_meta.get('topic_index', 0),
            'topic': topic_meta.get('topic', ''),
            'suggested_title': topic_meta.get('suggested_title', ''),
            'virality_score': topic_meta.get('virality_score', 0),
            'seo_keywords': topic_meta.get('seo_keywords', ''),
            'sources': topic_meta.get('sources', []),
            'source_count': topic_meta.get('source_count', 0),
        }
        publish_log.log_decision(log_entry)
    except Exception as e:
        return json_response({'error': str(e)}), 500

    return json_response({'ok': True})


@app.route('/api/wp/publish-stats')
def api_wp_publish_stats():
    try:
        stats = publish_log.get_stats()
        return json_response(stats)
    except Exception as e:
        return json_response({'error': str(e)}), 500


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
