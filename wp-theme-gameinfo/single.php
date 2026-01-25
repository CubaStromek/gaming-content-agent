<?php
/**
 * Single post template
 *
 * @package GameInfo_Terminal
 */

get_header();

while (have_posts()) :
    the_post();
    ?>

    <article id="post-<?php the_ID(); ?>" <?php post_class('single-post-content'); ?>>
        <header class="post-header">
            <div class="post-meta-top mono-text">
                <span class="news-timestamp"><?php echo esc_html(gameinfo_format_date()); ?></span>
                <span class="news-tag <?php echo gameinfo_get_post_tag_type() === 'critical' ? 'critical' : ''; ?>">
                    <?php echo esc_html(gameinfo_get_category_tag()); ?>
                </span>
                <?php
                $source_url = gameinfo_get_source_url();
                if (!empty($source_url)) : ?>
                    <span class="source-link">
                        <?php esc_html_e('SOURCE', 'gameinfo-terminal'); ?>
                        <a href="<?php echo esc_url($source_url); ?>" target="_blank" rel="noopener noreferrer" title="<?php echo esc_attr(gameinfo_get_source()); ?>">
                            <span class="material-symbols-outlined">open_in_new</span>
                        </a>
                    </span>
                <?php else : ?>
                    <span><?php echo esc_html(gameinfo_get_source()); ?></span>
                <?php endif; ?>
            </div>

            <h1 class="entry-title">
                <?php echo esc_html(gameinfo_get_post_status_prefix()); ?> <?php the_title(); ?>
            </h1>

            <?php if (has_post_thumbnail()) : ?>
                <div class="post-thumbnail" style="margin-bottom: 2rem;">
                    <?php the_post_thumbnail('large', array('style' => 'width: 100%; height: auto; border-radius: 0.25rem;')); ?>
                </div>
            <?php endif; ?>
        </header>

        <div class="entry-content">
            <?php
            the_content();

            wp_link_pages(array(
                'before' => '<div class="page-links mono-text">' . __('Pages:', 'gameinfo-terminal'),
                'after'  => '</div>',
            ));
            ?>
        </div>

        <footer class="entry-footer" style="margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid rgba(255,255,255,0.05);">
            <div class="mono-text" style="font-size: 0.75rem; color: #6b7280;">
                <?php
                $tags_list = get_the_tag_list('', ', ');
                if ($tags_list) {
                    echo '<div style="margin-bottom: 0.5rem;">TAGS: ' . $tags_list . '</div>';
                }
                ?>
                <div>
                    AUTHOR: <?php echo esc_html(strtoupper(get_the_author())); ?> |
                    MODIFIED: <?php echo esc_html(get_the_modified_date('d/m/Y')); ?>
                </div>
            </div>
        </footer>
    </article>

    <nav class="post-navigation" style="margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid rgba(255,255,255,0.05);">
        <div style="display: flex; justify-content: space-between; font-family: 'JetBrains Mono', monospace; font-size: 0.875rem;">
            <div>
                <?php
                $prev_post = get_previous_post();
                if ($prev_post) :
                ?>
                    <a href="<?php echo esc_url(get_permalink($prev_post)); ?>" style="color: #9ca3af;">
                        &laquo; PREV_LOG
                    </a>
                <?php endif; ?>
            </div>
            <div>
                <a href="<?php echo esc_url(home_url('/')); ?>" style="color: var(--primary);">
                    [RETURN_TO_INDEX]
                </a>
            </div>
            <div>
                <?php
                $next_post = get_next_post();
                if ($next_post) :
                ?>
                    <a href="<?php echo esc_url(get_permalink($next_post)); ?>" style="color: #9ca3af;">
                        NEXT_LOG &raquo;
                    </a>
                <?php endif; ?>
            </div>
        </div>
    </nav>

    <?php
    if (comments_open() || get_comments_number()) :
        comments_template();
    endif;

endwhile;

get_footer();
