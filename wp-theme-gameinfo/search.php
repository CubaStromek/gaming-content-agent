<?php
/**
 * Search results template
 *
 * @package GameInfo_Terminal
 */

get_header();
?>

<div class="page-header">
    <h1 class="page-title mono-text">
        QUERY_RESULT: "<?php echo esc_html(get_search_query()); ?>"
    </h1>
    <p class="last-indexed mono-text">
        <?php
        if (have_posts()) {
            printf(
                esc_html__('Found %d matching entries', 'gameinfo-terminal'),
                $wp_query->found_posts
            );
        } else {
            esc_html_e('No matching entries found', 'gameinfo-terminal');
        }
        ?>
    </p>
</div>

<div class="news-list">
    <?php
    if (have_posts()) :
        while (have_posts()) :
            the_post();
            get_template_part('template-parts/content', 'news-item');
        endwhile;
    else :
        ?>
        <div class="news-item">
            <span class="news-timestamp"><?php echo esc_html(date('d/m/Y')); ?></span>
            <div class="news-content">
                <h2 class="news-title">
                    [ERROR] <?php esc_html_e('Query returned no results', 'gameinfo-terminal'); ?>
                </h2>
                <div class="news-meta">
                    <span>NULL_RESPONSE</span>
                    <span><?php esc_html_e('Try different search terms...', 'gameinfo-terminal'); ?></span>
                </div>
            </div>
        </div>

        <div style="margin-top: 2rem;">
            <?php get_search_form(); ?>
        </div>
    <?php endif; ?>
</div>

<?php
the_posts_pagination(array(
    'mid_size'  => 2,
    'prev_text' => __('&laquo; PREV', 'gameinfo-terminal'),
    'next_text' => __('NEXT &raquo;', 'gameinfo-terminal'),
));

get_footer();
