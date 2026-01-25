/**
 * GameInfo Terminal Theme JavaScript
 *
 * @package GameInfo_Terminal
 */

(function() {
    'use strict';

    // DOM Ready
    document.addEventListener('DOMContentLoaded', function() {
        initThemeToggle();
        initLoadMore();
        initTerminalEffects();
        initSearchFocus();
        initDropdownMenus();
    });

    /**
     * Load More Posts via AJAX
     */
    function initLoadMore() {
        const loadMoreBtn = document.getElementById('gameinfo-load-more');

        if (!loadMoreBtn) return;

        loadMoreBtn.addEventListener('click', function() {
            const button = this;
            const currentPage = parseInt(button.dataset.page);
            const maxPages = parseInt(button.dataset.max);
            const newsList = document.querySelector('.news-list');

            // Update button state
            button.disabled = true;
            button.innerHTML = '<span class="material-symbols-outlined" style="animation: spin 1s linear infinite;">sync</span> FETCHING...';

            // Get current category if on archive page
            const categorySlug = document.body.classList.contains('category')
                ? document.body.className.match(/category-([^\s]+)/)?.[1] || ''
                : '';

            // Create form data
            const formData = new FormData();
            formData.append('action', 'gameinfo_loadmore');
            formData.append('page', currentPage + 1);
            formData.append('category', categorySlug);
            formData.append('nonce', gameinfo_ajax.nonce);

            // Fetch new posts
            fetch(gameinfo_ajax.ajax_url, {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            })
            .then(response => response.text())
            .then(html => {
                if (html.trim()) {
                    // Find the end of logs element and insert before it
                    const endOfLogs = newsList.querySelector('.news-item:last-child');
                    if (endOfLogs) {
                        endOfLogs.insertAdjacentHTML('beforebegin', html);
                    } else {
                        newsList.insertAdjacentHTML('beforeend', html);
                    }

                    button.dataset.page = currentPage + 1;

                    // Check if we've reached the end
                    if (currentPage + 1 >= maxPages) {
                        button.style.display = 'none';
                    } else {
                        button.disabled = false;
                        button.innerHTML = '<span class="material-symbols-outlined">refresh</span> FETCH_MORE_DATA';
                    }

                    // Initialize effects on new items
                    initTerminalEffects();
                } else {
                    button.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Load more error:', error);
                button.disabled = false;
                button.innerHTML = '<span class="material-symbols-outlined">error</span> ERROR_RETRY';
            });
        });
    }

    /**
     * Terminal Cursor Effects
     */
    function initTerminalEffects() {
        // Add cursor effect to news titles on hover
        const newsTitles = document.querySelectorAll('.news-title');

        newsTitles.forEach(title => {
            title.addEventListener('mouseenter', function() {
                if (!this.querySelector('.cursor-blink')) {
                    const cursor = document.createElement('span');
                    cursor.className = 'cursor-blink';
                    cursor.textContent = ' \u2588';
                    cursor.style.cssText = 'color: var(--primary); animation: blink 1s step-end infinite;';
                    this.appendChild(cursor);
                }
            });

            title.addEventListener('mouseleave', function() {
                const cursor = this.querySelector('.cursor-blink');
                if (cursor) {
                    cursor.remove();
                }
            });
        });

        // Typing effect for system status (optional)
        const systemStatus = document.querySelector('.system-status');
        if (systemStatus && !systemStatus.dataset.initialized) {
            systemStatus.dataset.initialized = 'true';
        }
    }

    /**
     * Search Field Focus Effects
     */
    function initSearchFocus() {
        const searchField = document.querySelector('.search-field');

        if (!searchField) return;

        searchField.addEventListener('focus', function() {
            this.placeholder = '';
        });

        searchField.addEventListener('blur', function() {
            this.placeholder = 'QUERY_SYSTEM...';
        });

        // Handle keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            // Ctrl/Cmd + K to focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                searchField.focus();
            }

            // Escape to blur search
            if (e.key === 'Escape' && document.activeElement === searchField) {
                searchField.blur();
            }
        });
    }

    /**
     * Theme Toggle (Light/Dark Mode)
     */
    function initThemeToggle() {
        const toggleBtn = document.getElementById('theme-toggle');

        if (!toggleBtn) return;

        toggleBtn.addEventListener('click', function() {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';

            // Update DOM
            document.documentElement.setAttribute('data-theme', newTheme);

            // Save preference
            localStorage.setItem('theme', newTheme);

            // Add rotation animation to icon
            const icon = this.querySelector('.material-symbols-outlined:not([style*="display: none"])');
            if (icon) {
                icon.style.transform = 'rotate(360deg)';
                setTimeout(() => {
                    icon.style.transform = '';
                }, 300);
            }
        });

        // Listen for system theme changes
        window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', function(e) {
            // Only update if user hasn't set a preference
            if (!localStorage.getItem('theme')) {
                document.documentElement.setAttribute('data-theme', e.matches ? 'light' : 'dark');
            }
        });
    }

    /**
     * Dropdown Menus (Mobile Support)
     */
    function initDropdownMenus() {
        const dropdownItems = document.querySelectorAll('.nav-item.has-dropdown, .category-tab-wrapper.has-dropdown');

        if (!dropdownItems.length) return;

        // Check if mobile
        const isMobile = () => window.innerWidth <= 768;

        dropdownItems.forEach(item => {
            const link = item.querySelector('.nav-link, .category-tab');

            if (!link) return;

            link.addEventListener('click', function(e) {
                if (isMobile()) {
                    // On mobile, toggle dropdown on click
                    e.preventDefault();

                    // Close other dropdowns
                    dropdownItems.forEach(other => {
                        if (other !== item) {
                            other.classList.remove('open');
                        }
                    });

                    // Toggle current dropdown
                    item.classList.toggle('open');
                }
            });
        });

        // Close dropdowns when clicking outside
        document.addEventListener('click', function(e) {
            if (isMobile() && !e.target.closest('.nav-item, .category-tab-wrapper')) {
                dropdownItems.forEach(item => {
                    item.classList.remove('open');
                });
            }
        });

        // Handle window resize
        window.addEventListener('resize', function() {
            if (!isMobile()) {
                dropdownItems.forEach(item => {
                    item.classList.remove('open');
                });
            }
        });
    }

    /**
     * Add CSS animation for loading spinner
     */
    const style = document.createElement('style');
    style.textContent = `
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);

})();
