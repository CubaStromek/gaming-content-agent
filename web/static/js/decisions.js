/* Decision Transparency view logic.
 *
 * Načítá data z /api/decisions/* a vykresluje:
 *  - Decision header + per-topic karty (verdikt, virality, dedup match, failed sources)
 *  - Trends — daily stacked bars (published/skipped) + line avg virality
 *  - Skoring — scatter virality × verdikt
 *
 * Frontend předpokládá, že auth_bootstrap.js doplnil Bearer token do fetch().
 */

(function () {
    let currentRunId = null;
    let runsListLoaded = false;

    function escapeHtml(s) {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // ── Tab switching ───────────────────────────────────────────────────────
    window.switchView = function (view) {
        document.querySelectorAll('.view-tab').forEach(b => {
            b.classList.toggle('active', b.dataset.view === view);
        });
        const sectionMap = {
            decision: 'viewDecision',
            trends: 'viewTrends',
            scoring: 'viewScoring',
            manual: 'viewManual',
        };
        Object.entries(sectionMap).forEach(([k, id]) => {
            const el = document.getElementById(id);
            if (el) el.hidden = (k !== view);
        });

        if (view === 'trends') loadTrends();
        else if (view === 'scoring') loadScoring();
    };

    // ── Decision Report ─────────────────────────────────────────────────────
    function pickLatestRun() {
        return fetch('/api/decisions/runs?limit=1')
            .then(r => r.json())
            .then(data => {
                if (data.runs && data.runs.length > 0) return data.runs[0].run_id;
                return null;
            });
    }

    function loadRunDecisions(runId) {
        currentRunId = runId;
        if (!runId) {
            renderDecisionEmpty('Žádný běh s instrumentací run_id zatím neexistuje. Spusť agenta a vrať se.');
            return;
        }
        fetch('/api/decisions/run/' + encodeURIComponent(runId))
            .then(r => r.json())
            .then(renderDecisions)
            .catch(err => renderDecisionEmpty('Chyba: ' + err.message));
    }

    function renderDecisionEmpty(msg) {
        document.getElementById('decisionHeader').innerHTML =
            '<div class="dh-loading">' + escapeHtml(msg) + '</div>';
        document.getElementById('decisionTopics').innerHTML = '';
    }

    function renderDecisions(data) {
        const decisions = data.decisions || [];
        const proposed = data.proposed_topics || [];

        // Najdi „proposed" log entry pro RSS count, fallback na articles_count.
        const proposedEntry = decisions.find(d => d.action === 'proposed');
        const rssCount = (proposedEntry && proposedEntry.data && proposedEntry.data.rss_articles_count)
            || data.articles_count || 0;

        const published = decisions.filter(d => d.action === 'published').length;
        const skipped = decisions.filter(d => d.action === 'skipped').length;
        const proposedCount = (proposedEntry && proposedEntry.data && proposedEntry.data.topics)
            ? proposedEntry.data.topics.length
            : proposed.length;

        const lastTs = decisions.length ? decisions[decisions.length - 1].timestamp : '';

        document.getElementById('decisionHeader').innerHTML = `
            <div class="dh-meta">
              <div><strong>${escapeHtml(formatTs(lastTs))}</strong>
                   <div class="dh-meta-label">last activity</div></div>
              <div><strong>${rssCount}</strong>
                   <div class="dh-meta-label">RSS articles</div></div>
              <div><strong>${proposedCount}</strong>
                   <div class="dh-meta-label">topics proposed</div></div>
              <div><strong style="color:#86efac;">${published}</strong>
                   <div class="dh-meta-label">published</div></div>
              <div><strong style="color:#fca5a5;">${skipped}</strong>
                   <div class="dh-meta-label">skipped</div></div>
            </div>
            <div class="dh-runid">run_id: ${escapeHtml(data.run_id)}</div>
        `;

        // Postav per-topic verdict mapu — proposed_topics je single source of truth
        // pro virality / hook (z report.txt). Decisions říká, jak to dopadlo.
        const verdictByTopic = {};
        for (const d of decisions) {
            if (d.action === 'proposed') continue;
            const key = (d.topic || '').toLowerCase();
            verdictByTopic[key] = d;
        }

        const cards = [];
        for (const topic of proposed) {
            const key = (topic.topic || '').toLowerCase();
            const verdict = verdictByTopic[key];
            cards.push(renderTopicCard(topic, verdict));
        }

        // Témata, která NEJSOU v report.txt, ale jsou v decisions (např. dedup
        // skipy, kde Claude navrhl jiný název) — přidej fallbackové karty.
        const proposedKeys = new Set(proposed.map(t => (t.topic || '').toLowerCase()));
        for (const d of decisions) {
            if (d.action === 'proposed') continue;
            const key = (d.topic || '').toLowerCase();
            if (proposedKeys.has(key)) continue;
            cards.push(renderTopicCard({ topic: d.topic, virality_score: d.score, sources: [] }, d));
        }

        document.getElementById('decisionTopics').innerHTML = cards.join('') ||
            '<div class="dh-loading">Žádná témata pro tento běh.</div>';
    }

    function renderTopicCard(topic, verdict) {
        const virality = topic.virality_score || (verdict && verdict.score) || 0;
        const verdictClass = verdict
            ? (verdict.action === 'published' ? 'verdict-published' : 'verdict-skipped')
            : 'verdict-pending';
        const badgeClass = verdict
            ? (verdict.action === 'published' ? 'published' : 'skipped')
            : 'pending';
        const badgeText = verdict ? verdict.action : '— pending —';

        let reasonHtml = '';
        if (verdict && verdict.action === 'skipped') {
            const reason = (verdict.data && verdict.data.reason) || 'unknown';
            reasonHtml = `<div class="verdict-reason">${escapeHtml(reason)}</div>`;
        }

        let dedupHtml = '';
        if (verdict && verdict.data && verdict.data.dedup_match) {
            const m = verdict.data.dedup_match;
            const ts = (m.timestamp || '').slice(0, 16).replace('T', ' ');
            dedupHtml = `
              <div class="dedup-match">
                Podobné: „${escapeHtml(m.topic)}" (${escapeHtml(ts)})<br>
                <span class="sim">sim ${(m.sim_score || 0).toFixed(2)}</span> · ${escapeHtml(m.match_type || '')}
              </div>`;
        }

        let failedHtml = '';
        if (verdict && verdict.data && verdict.data.failed_sources && verdict.data.failed_sources.length) {
            const f = verdict.data.failed_sources;
            failedHtml = `<span class="failed-src">${f.length} zdroj${f.length === 1 ? '' : 'e'} selhal${f.length === 1 ? '' : 'y'}</span>`;
        }

        const sourcesOk = (topic.sources || []).length;
        const statusTag = topic.status_tag || (verdict && verdict.data && verdict.data.status_tag) || '';

        return `
          <div class="topic-card ${verdictClass}">
            <div class="topic-virality">
              <div class="num">${virality}</div>
              <div class="bar"><div class="bar-fill" style="width:${Math.min(100, virality)}%;"></div></div>
            </div>
            <div class="topic-main">
              <div class="topic-title">${escapeHtml(topic.title || topic.topic)}</div>
              <div class="topic-meta-row">
                ${statusTag ? `<span class="status-tag">${escapeHtml(statusTag)}</span>` : ''}
                ${topic.game_name ? `<span>${escapeHtml(topic.game_name)}</span>` : ''}
                <span>· ${sourcesOk} source${sourcesOk === 1 ? '' : 's'}</span>
                ${failedHtml ? '<span>· ' + failedHtml + '</span>' : ''}
              </div>
              ${topic.hook ? `<div class="topic-hook">${escapeHtml(topic.hook)}</div>` : ''}
              ${topic.angle ? `<div class="topic-detail"><span class="label">angle:</span> ${escapeHtml(topic.angle)}</div>` : ''}
            </div>
            <div class="topic-verdict">
              <span class="verdict-badge ${badgeClass}">${escapeHtml(badgeText)}</span>
              ${reasonHtml}
              ${dedupHtml}
            </div>
          </div>
        `;
    }

    function formatTs(ts) {
        if (!ts) return '—';
        // 2026-05-10T14:05:21 → 10.05 14:05
        const m = ts.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
        if (!m) return ts;
        return `${m[3]}.${m[2]} ${m[4]}:${m[5]}`;
    }

    // ── Trends canvas ───────────────────────────────────────────────────────
    function loadTrends() {
        Promise.all([
            fetch('/api/decisions/timeline?days=14').then(r => r.json()),
            fetch('/api/decisions/skip-reasons?days=30&limit=3').then(r => r.json()),
        ]).then(([timeline, reasons]) => {
            drawTimeline(timeline.buckets || []);
            renderSkipReasons(reasons.reasons || {});
        });
    }

    function drawTimeline(buckets) {
        const canvas = document.getElementById('trendsCanvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const W = canvas.width, H = canvas.height;
        ctx.clearRect(0, 0, W, H);

        if (!buckets.length) {
            ctx.fillStyle = '#9ca3af';
            ctx.font = '14px JetBrains Mono';
            ctx.fillText('Žádná data za posledních 14 dní.', 20, 40);
            return;
        }

        const padL = 50, padR = 20, padT = 20, padB = 40;
        const plotW = W - padL - padR;
        const plotH = H - padT - padB;
        const barW = plotW / buckets.length * 0.65;
        const slot = plotW / buckets.length;

        const maxY = Math.max(1, ...buckets.map(b => b.published + b.skipped));
        const yScale = plotH / maxY;

        // Y axis lines
        ctx.strokeStyle = 'rgba(255,255,255,0.06)';
        ctx.fillStyle = '#6b7280';
        ctx.font = '10px JetBrains Mono';
        for (let i = 0; i <= 4; i++) {
            const y = padT + plotH - (i / 4) * plotH;
            ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(W - padR, y); ctx.stroke();
            ctx.fillText(String(Math.round((i / 4) * maxY)), 10, y + 3);
        }

        // Bars
        buckets.forEach((b, i) => {
            const x = padL + i * slot + (slot - barW) / 2;
            const totalH = (b.published + b.skipped) * yScale;
            const pubH = b.published * yScale;
            const skipH = b.skipped * yScale;

            // skipped (top)
            ctx.fillStyle = '#f87171';
            ctx.fillRect(x, padT + plotH - totalH, barW, skipH);
            // published (bottom)
            ctx.fillStyle = '#4ade80';
            ctx.fillRect(x, padT + plotH - pubH, barW, pubH);

            // Date label
            ctx.fillStyle = '#9ca3af';
            ctx.fillText(b.date.slice(5), x, padT + plotH + 14);
        });

        // Avg virality line
        const maxV = 100;
        ctx.strokeStyle = '#fbbf24';
        ctx.lineWidth = 2;
        ctx.beginPath();
        let started = false;
        buckets.forEach((b, i) => {
            if (!b.avg_virality) return;
            const x = padL + i * slot + slot / 2;
            const y = padT + plotH - (b.avg_virality / maxV) * plotH;
            if (!started) { ctx.moveTo(x, y); started = true; }
            else ctx.lineTo(x, y);
        });
        ctx.stroke();
    }

    function renderSkipReasons(reasons) {
        const wrap = document.getElementById('skipReasonsList');
        if (!wrap) return;
        const entries = Object.entries(reasons);
        if (!entries.length) {
            wrap.innerHTML = '<div class="dh-loading">Žádné skipy v posledních 30 dnech.</div>';
            return;
        }
        wrap.innerHTML = entries.map(([reason, info]) => {
            const ex = (info.examples || []).map(e => escapeHtml(e.topic || '')).join(' · ');
            return `
              <div class="skip-reason-row">
                <div class="reason">${escapeHtml(reason)}</div>
                <div class="count">${info.count}</div>
                <div class="examples">${ex || '—'}</div>
              </div>`;
        }).join('');
    }

    // ── Scoring scatter ─────────────────────────────────────────────────────
    let scoringPoints = []; // [{x, y, data}, ...] — pro hover lookup

    function loadScoring() {
        fetch('/api/decisions/scoring?days=30')
            .then(r => r.json())
            .then(data => {
                drawScoring(data.points || []);
                initScoringHover();
            });
    }

    function drawScoring(points) {
        const canvas = document.getElementById('scoringCanvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const W = canvas.width, H = canvas.height;
        ctx.clearRect(0, 0, W, H);
        scoringPoints = [];

        if (!points.length) {
            ctx.fillStyle = '#9ca3af';
            ctx.font = '14px JetBrains Mono';
            ctx.fillText('Žádné scored entries za posledních 30 dní.', 20, 40);
            return;
        }

        const padL = 50, padR = 20, padT = 20, padB = 50;
        const plotW = W - padL - padR;
        const plotH = H - padT - padB;

        ctx.strokeStyle = 'rgba(255,255,255,0.06)';
        ctx.fillStyle = '#6b7280';
        ctx.font = '10px JetBrains Mono';
        for (let i = 0; i <= 5; i++) {
            const y = padT + plotH - (i / 5) * plotH;
            const v = (i / 5) * 100;
            ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(W - padR, y); ctx.stroke();
            ctx.fillText(String(Math.round(v)), 18, y + 3);
        }
        ctx.fillText('virality', 18, padT - 6);

        const slot = plotW / Math.max(points.length, 1);
        points.forEach((p, i) => {
            const x = padL + i * slot + slot / 2;
            const y = padT + plotH - (p.virality_score / 100) * plotH;
            ctx.fillStyle = (p.action === 'published') ? '#4ade80' : '#f87171';
            ctx.beginPath();
            ctx.arc(x, y, 4, 0, Math.PI * 2);
            ctx.fill();
            scoringPoints.push({ x, y, data: p });
        });

        ctx.fillStyle = '#6b7280';
        ctx.font = '10px JetBrains Mono';
        ctx.fillText('time →', padL, padT + plotH + 30);
    }

    function ensureScoringTooltip() {
        let tip = document.getElementById('scoringTooltip');
        if (tip) return tip;
        tip = document.createElement('div');
        tip.id = 'scoringTooltip';
        Object.assign(tip.style, {
            position: 'absolute',
            display: 'none',
            background: 'rgba(17,24,39,0.96)',
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: '0.3rem',
            padding: '0.5rem 0.7rem',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '0.7rem',
            color: '#e5e7eb',
            pointerEvents: 'none',
            zIndex: '100',
            maxWidth: '320px',
            lineHeight: '1.4',
        });
        document.body.appendChild(tip);
        return tip;
    }

    function initScoringHover() {
        const canvas = document.getElementById('scoringCanvas');
        if (!canvas || canvas.dataset.hoverInit === '1') return;
        canvas.dataset.hoverInit = '1';

        const tip = ensureScoringTooltip();
        const HIT_RADIUS = 6;

        canvas.addEventListener('mousemove', e => {
            if (!scoringPoints.length) return;
            const rect = canvas.getBoundingClientRect();
            // Canvas má width=900 (atribut) ale je rendrovaný responsivně —
            // přepočet poměru je nutný.
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;
            const cx = (e.clientX - rect.left) * scaleX;
            const cy = (e.clientY - rect.top) * scaleY;

            let closest = null, closestDist = Infinity;
            for (const p of scoringPoints) {
                const dx = p.x - cx, dy = p.y - cy;
                const d = dx * dx + dy * dy;
                if (d < closestDist) { closestDist = d; closest = p; }
            }
            if (closest && closestDist <= HIT_RADIUS * HIT_RADIUS * scaleX * scaleX) {
                const d = closest.data;
                const ts = (d.timestamp || '').slice(0, 16).replace('T', ' ');
                const verdictColor = d.action === 'published' ? '#86efac' : '#fca5a5';
                tip.innerHTML = `
                    <div style="font-weight:600;margin-bottom:0.25rem;">${escapeHtml(d.topic)}</div>
                    <div>virality <strong style="color:#fbbf24;">${d.virality_score}</strong></div>
                    <div style="color:${verdictColor};">${escapeHtml(d.action)}${d.reason ? ' · ' + escapeHtml(d.reason) : ''}</div>
                    <div style="color:#6b7280;margin-top:0.2rem;">${escapeHtml(ts)}</div>
                `;
                tip.style.display = 'block';
                tip.style.left = (e.clientX + 12) + 'px';
                tip.style.top = (e.clientY + 12) + 'px';
            } else {
                tip.style.display = 'none';
            }
        });
        canvas.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
    }

    // ── Init ────────────────────────────────────────────────────────────────
    function initDecisionView() {
        pickLatestRun().then(loadRunDecisions);
    }

    // Hook do existující historie — pokud uživatel klikne na run_id v sidebaru,
    // přepneme do Decision view a načteme jeho rozhodnutí.
    window.loadRunDecisionsFromHistory = function (runId) {
        switchView('decision');
        loadRunDecisions(runId);
    };

    document.addEventListener('DOMContentLoaded', initDecisionView);
})();
