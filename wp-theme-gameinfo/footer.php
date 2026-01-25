        </main><!-- .site-main -->

        <footer class="site-footer">
            <div class="footer-prompt">
                <span>&gt;</span>
                <span class="cursor">_</span>
                <span class="help-text"><?php esc_html_e('Type /help for navigation commands', 'gameinfo-terminal'); ?></span>
            </div>
            <div class="footer-info">
                <div>
                    <span class="encoding">UTF-8</span>
                </div>
                <div>
                    <span>L: <?php echo wp_count_posts()->publish; ?></span>
                    <span>C: <?php echo wp_count_terms('category'); ?></span>
                </div>
                <div class="sync">
                    <span class="material-symbols-outlined">cloud_done</span>
                    <span><?php esc_html_e('SYNCED', 'gameinfo-terminal'); ?></span>
                </div>
            </div>
        </footer>
    </div><!-- .console-container -->

    <div class="bottom-bar">
        <div><?php echo esc_html(gameinfo_get_option('site_title', 'game_info')); ?> build <?php echo esc_html(gameinfo_get_option('build_version', '2.4.0-stable')); ?></div>
        <div class="bottom-links">
            <?php
            if (has_nav_menu('footer')) {
                wp_nav_menu(array(
                    'theme_location' => 'footer',
                    'container'      => false,
                    'items_wrap'     => '%3$s',
                    'depth'          => 1,
                ));
            } else {
                ?>
                <a class="hover:text-primary" href="<?php echo esc_url(get_privacy_policy_url()); ?>">PRIVACY_PROTOCOL</a>
                <?php
            }
            ?>
        </div>
    </div>
</div><!-- .site-wrapper -->

<?php wp_footer(); ?>
</body>
</html>
