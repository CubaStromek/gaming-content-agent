<?php
/**
 * Front page template
 * This template is used when a static front page is set
 * It shows the latest posts regardless of settings
 *
 * @package GameInfo_Terminal
 */

get_header();

// Force query for latest posts
$args = array(
    'post_type'      => 'post',
    'post_status'    => 'publish',
    'posts_per_page' => get_option('posts_per_page', 10),
    'orderby'        => 'date',
    'order'          => 'DESC',
);

$latest_posts = new WP_Query($args);
?>

<div class="page-header">
    <h1 class="page-title mono-text">ROOT_ACCESS: <?php esc_html_e('Latest Game Intel', 'gameinfo-terminal'); ?></h1>
    <p class="last-indexed mono-text">
        <?php esc_html_e('Last indexed:', 'gameinfo-terminal'); ?>
        <span class="time"><?php echo esc_html(gameinfo_get_current_timestamp()); ?></span>
    </p>
</div>

<?php get_template_part('template-parts/category', 'tabs'); ?>

<div class="news-list">
    <?php if ($latest_posts->have_posts()) : ?>
        <?php while ($latest_posts->have_posts()) : $latest_posts->the_post(); ?>
            <?php get_template_part('template-parts/content', 'news-item'); ?>
        <?php endwhile; ?>
        <?php wp_reset_postdata(); ?>

        <div class="news-item" style="opacity: 0.5;">
            <span class="news-timestamp"><?php echo esc_html(date('d/m/Y', strtotime('-1 day'))); ?></span>
            <div class="news-content">
                <h2 class="news-title" style="color: #6b7280;">
                    [END_OF_LOGS] <?php esc_html_e('No further entries for previous session', 'gameinfo-terminal'); ?>
                </h2>
                <div class="news-meta">
                    <span>TERMINAL_REACHED</span>
                </div>
            </div>
        </div>

    <?php else : ?>
        <div class="news-item">
            <span class="news-timestamp"><?php echo esc_html(date('d/m/Y')); ?></span>
            <div class="news-content">
                <h2 class="news-title">
                    [ERROR] <?php esc_html_e('No posts found in database', 'gameinfo-terminal'); ?>
                </h2>
                <div class="news-meta">
                    <span>EMPTY_RESULT_SET</span>
                    <span>Check: Dashboard > Posts</span>
                </div>
            </div>
        </div>
    <?php endif; ?>
</div>

<?php
get_footer();
