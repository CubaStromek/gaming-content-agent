<!DOCTYPE html>
<html <?php language_attributes(); ?>>
<head>
    <meta charset="<?php bloginfo('charset'); ?>">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script>
        // Prevent flash of wrong theme
        (function() {
            const theme = localStorage.getItem('theme') ||
                (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
            document.documentElement.setAttribute('data-theme', theme);
        })();
    </script>
    <?php wp_head(); ?>
</head>
<body <?php body_class('bg-background-light dark:bg-background-dark font-display text-gray-300 antialiased selection:bg-primary/30'); ?>>
<?php wp_body_open(); ?>

<div class="site-wrapper">
    <div class="console-container">
        <header class="site-header">
            <div class="header-left">
                <div class="window-controls">
                    <div class="window-dot red"></div>
                    <div class="window-dot yellow"></div>
                    <div class="window-dot green"></div>
                </div>
                <div class="terminal-info">
                    <a href="<?php echo esc_url(home_url('/')); ?>" class="site-title-link">
                        <span class="site-title"><?php echo esc_html(gameinfo_get_option('site_title', 'game_info')); ?></span>
                    </a>
                    <span class="path"><?php echo esc_html(gameinfo_get_option('path', '~/news')); ?></span>
                    <span class="separator">|</span>
                    <div class="system-status">
                        <span class="status-dot"></span>
                        <?php esc_html_e('System Online', 'gameinfo-terminal'); ?>
                    </div>
                </div>
            </div>

            <div class="header-actions">
                <?php echo gameinfo_get_facebook_button(); ?>
                <?php echo gameinfo_get_rss_button(); ?>
                <?php echo gameinfo_get_language_switcher(); ?>
                <button class="theme-toggle" id="theme-toggle" aria-label="<?php esc_attr_e('Toggle theme', 'gameinfo-terminal'); ?>">
                    <span class="material-symbols-outlined icon-dark">light_mode</span>
                    <span class="material-symbols-outlined icon-light">dark_mode</span>
                </button>
                <?php get_search_form(); ?>
                <button class="terminal-btn" aria-label="<?php esc_attr_e('Terminal', 'gameinfo-terminal'); ?>">
                    <span class="material-symbols-outlined">terminal</span>
                </button>
            </div>
        </header>

        <main class="site-main">
