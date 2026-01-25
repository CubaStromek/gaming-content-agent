<?php
/**
 * Front page template
 * This template is used when a static front page is set
 * It shows the latest posts regardless of settings
 *
 * @package GameInfo_Terminal
 */

get_header();

// Get current page number
$paged = (get_query_var('paged')) ? get_query_var('paged') : 1;

// Force query for latest posts with pagination
$args = array(
    'post_type'      => 'post',
    'post_status'    => 'publish',
    'posts_per_page' => get_option('posts_per_page', 10),
    'orderby'        => 'date',
    'order'          => 'DESC',
    'paged'          => $paged,
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

<?php if ($latest_posts->max_num_pages > 1) : ?>
<nav class="navigation pagination" aria-label="<?php esc_attr_e('Posts navigation', 'gameinfo-terminal'); ?>">
    <div class="nav-links">
        <?php
        echo paginate_links(array(
            'total'        => $latest_posts->max_num_pages,
            'current'      => $paged,
            'prev_text'    => '<span class="material-symbols-outlined" style="font-size: 1rem; vertical-align: middle;">chevron_left</span> PREV',
            'next_text'    => 'NEXT <span class="material-symbols-outlined" style="font-size: 1rem; vertical-align: middle;">chevron_right</span>',
            'type'         => 'plain',
            'end_size'     => 1,
            'mid_size'     => 1,
        ));
        ?>
    </div>
</nav>
<?php endif; ?>

<?php
get_footer();
