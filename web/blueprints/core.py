"""Core routes: /, /health, /start, /output, /status."""

import os
import re
import sys
import time
import subprocess
import threading

from flask import Blueprint, render_template

from web.auth import require_auth
from web.helpers import (
    json_response, output_lock, output_lines,
)
import web.helpers as state

core_bp = Blueprint('core', __name__)

_start_time = time.time()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Regex pro odstranění log prefixu: "2026-02-19 11:52:01,631 [INFO] " → ""
_LOG_PREFIX_RE = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \[(INFO|WARNING|ERROR|DEBUG)\]\s*')


def _strip_log_prefix(line: str) -> str:
    """Odstraní timestamp a log level prefix z řádku."""
    return _LOG_PREFIX_RE.sub('', line)


def _rate_limit(limit_string):
    """Rate limit dekorátor — no-op pokud flask-limiter není dostupný."""
    try:
        from flask import current_app
        limiter = current_app.extensions.get('limiter')
        if limiter:
            return limiter.limit(limit_string)
    except Exception:
        pass
    return lambda f: f


def run_agent_process():
    """Spustí main.py jako subprocess a zachytává výstup."""
    state.run_success = False

    with state.output_lock:
        state.agent_running = True
        state.output_lines.clear()
        state.articles_count = 0
        state.sources_count = 0

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
                except Exception:
                    line = str(line_buffer)

                if line:
                    clean_line = _strip_log_prefix(line)
                    with state.output_lock:
                        state.output_lines.append(clean_line)

                        if 'Analyzováno:' in line or 'Analyzovano:' in line:
                            try:
                                parts = line.replace('Analyzováno:', 'Analyzovano:').split('Analyzovano:')
                                state.articles_count = int(parts[1].split()[0])
                            except Exception:
                                pass
                        elif 'Zdroje:' in line:
                            try:
                                state.sources_count = int(line.split('Zdroje:')[1].split()[0])
                            except Exception:
                                pass
                        elif 'Nalezeno' in line and 'článků' in line:
                            try:
                                parts = line.split()
                                for i, part in enumerate(parts):
                                    if part == 'Nalezeno':
                                        state.articles_count = int(parts[i + 1])
                                        break
                            except Exception:
                                pass

                line_buffer = b''
            else:
                line_buffer += byte

        process.wait()
        state.run_success = (process.returncode == 0)

        with state.output_lock:
            if state.run_success:
                state.output_lines.append("=" * 70)
                state.output_lines.append("HOTOVO! Agent dokoncil praci.")
                state.output_lines.append("=" * 70)
            else:
                state.output_lines.append(f"Agent skoncil s chybou (kod {process.returncode})")

    except Exception as e:
        with state.output_lock:
            state.output_lines.append(f"CHYBA: {str(e)}")
    finally:
        with state.output_lock:
            state.agent_running = False


@core_bp.route('/')
def index():
    return render_template('dashboard.html')


@core_bp.route('/health')
def healthcheck():
    return json_response({
        'status': 'ok',
        'uptime': round(time.time() - _start_time, 1),
        'version': '1.0',
    })


@core_bp.route('/start')
@require_auth
def start():
    with state.output_lock:
        if state.agent_running:
            return json_response({'status': 'already_running'})
        state.sent_line_index = 0

    state.agent_thread = threading.Thread(target=run_agent_process)
    state.agent_thread.start()

    return json_response({'status': 'started'})


@core_bp.route('/output')
def get_output():
    with state.output_lock:
        new_lines = state.output_lines[state.sent_line_index:]
        state.sent_line_index = len(state.output_lines)

        return json_response({
            'lines': new_lines,
            'running': state.agent_running,
            'success': state.run_success,
            'articles': state.articles_count,
            'sources': state.sources_count,
        })


@core_bp.route('/status')
def status():
    with state.output_lock:
        running = state.agent_running
    return json_response({'running': running})
