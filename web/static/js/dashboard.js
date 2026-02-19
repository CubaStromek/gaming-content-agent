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
            const modal = document.getElementById('wpPublishPanel');
            const isVisible = modal.classList.contains('visible');

            if (isVisible) {
                modal.classList.remove('visible');
            } else {
                modal.classList.add('visible');
                wpLoadCategories();
                wpLoadStatusTags();
                wpPrefillFields();
                wpClearImage();
                wpAutoSearchImage();
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

            // 0) corrected title from article writer (factual accuracy fix)
            if (articleResult && articleResult.corrected_title) {
                document.getElementById('wpTitle').value = articleResult.corrected_title;
            // 1) topic suggested title from metadata
            } else if (currentTopicData && currentTopicData.suggested_title) {
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

        let wpSelectedImageUrl = null;
        let wpSelectedImageAlt = '';

        async function wpAutoSearchImage() {
            if (!currentTopicData) return;
            const query = currentTopicData.seo_keywords
                || currentTopicData.topic
                || currentTopicData.suggested_title;
            if (!query) return;
            document.getElementById('wpRawgQuery').value = query;
            await wpSearchRawg();
        }

        async function wpSearchRawg() {
            const query = document.getElementById('wpRawgQuery').value.trim();
            if (!query) return;
            const container = document.getElementById('wpRawgResults');
            container.innerHTML = '<div style="color:#6b7280;font-size:0.65rem;">Searching...</div>';

            try {
                const resp = await fetch('/api/rawg/search?q=' + encodeURIComponent(query));
                const data = await resp.json();
                if (data.error) { container.innerHTML = '<div style="color:var(--terminal-red);font-size:0.65rem;">' + escapeHtml(data.error) + '</div>'; return; }

                if (!data.games || data.games.length === 0) {
                    container.innerHTML = '<div style="color:#6b7280;font-size:0.65rem;">No results</div>';
                    return;
                }

                container.innerHTML = '';
                let firstImg = null;
                data.games.forEach(game => {
                    const gameDiv = document.createElement('div');
                    gameDiv.className = 'wp-rawg-game';

                    const nameDiv = document.createElement('div');
                    nameDiv.className = 'wp-rawg-game-name';
                    nameDiv.textContent = game.name;
                    gameDiv.appendChild(nameDiv);

                    const grid = document.createElement('div');
                    grid.className = 'wp-rawg-screenshots';
                    game.screenshots.forEach(url => {
                        const img = document.createElement('img');
                        img.src = url;
                        img.alt = game.name;
                        img.dataset.url = url;
                        img.dataset.gameName = game.name;
                        img.onclick = () => wpSelectImage(img);
                        grid.appendChild(img);
                        if (!firstImg) firstImg = img;
                    });
                    gameDiv.appendChild(grid);
                    container.appendChild(gameDiv);
                });

                if (firstImg && !wpSelectedImageUrl) {
                    wpSelectImage(firstImg);
                }
            } catch (err) {
                container.innerHTML = '<div style="color:var(--terminal-red);font-size:0.65rem;">Error: ' + escapeHtml(err.message) + '</div>';
            }
        }

        function wpSelectImage(img) {
            document.querySelectorAll('.wp-rawg-screenshots img').forEach(i => i.classList.remove('selected'));
            img.classList.add('selected');

            wpSelectedImageUrl = img.dataset.url;
            wpSelectedImageAlt = img.dataset.gameName || '';

            document.getElementById('wpImageFile').value = '';

            const preview = document.getElementById('wpSelectedImage');
            preview.innerHTML = '<img src="' + escapeHtml(img.src) + '"> '
                + escapeHtml(img.dataset.gameName || '')
                + ' <span class="wp-img-remove" onclick="wpClearImage()">[x]</span>';

            if (!document.getElementById('wpImageCaption').value.trim()) {
                document.getElementById('wpImageCaption').value = img.dataset.gameName || '';
            }
        }

        function wpShowLocalFile() {
            const fileInput = document.getElementById('wpImageFile');
            if (!fileInput.files || !fileInput.files[0]) return;

            wpSelectedImageUrl = null;
            wpSelectedImageAlt = '';
            document.querySelectorAll('.wp-rawg-screenshots img').forEach(i => i.classList.remove('selected'));

            const preview = document.getElementById('wpSelectedImage');
            const url = URL.createObjectURL(fileInput.files[0]);
            preview.innerHTML = '<img src="' + url + '"> '
                + escapeHtml(fileInput.files[0].name)
                + ' <span class="wp-img-remove" onclick="wpClearImage()">[x]</span>';
        }

        function wpClearImage() {
            wpSelectedImageUrl = null;
            wpSelectedImageAlt = '';
            document.getElementById('wpImageFile').value = '';
            document.getElementById('wpSelectedImage').innerHTML = '';
            document.querySelectorAll('.wp-rawg-screenshots img').forEach(i => i.classList.remove('selected'));
        }

        async function wpUploadImage() {
            const caption = document.getElementById('wpImageCaption').value.trim();

            if (wpSelectedImageUrl) {
                const resp = await fetch('/api/wp/upload-from-url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        url: wpSelectedImageUrl,
                        caption: caption,
                        alt_text: caption || wpSelectedImageAlt,
                    })
                });
                const data = await resp.json();
                if (data.error) throw new Error(data.error);
                return data.media_id;
            }

            const fileInput = document.getElementById('wpImageFile');
            if (!fileInput.files || !fileInput.files[0]) return null;

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
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
                if (wpSelectedImageUrl || (document.getElementById('wpImageFile').files && document.getElementById('wpImageFile').files[0])) {
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
                if (wpSelectedImageUrl || (document.getElementById('wpImageFile').files && document.getElementById('wpImageFile').files[0])) {
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
