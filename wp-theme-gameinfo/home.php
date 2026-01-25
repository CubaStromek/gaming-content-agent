<?php
/**
 * The home/blog template file
 * Displays latest posts on the blog page
 *
 * @package GameInfo_Terminal
 */

get_header();
?>

<div class="page-header">
    <h1 class="page-title mono-text">ROOT_ACCESS: <?php esc_html_e('Latest Game Intel', 'gameinfo-terminal'); ?></h1>
    <p class="last-indexed mono-text">
        <?php esc_html_e('Last indexed:', 'gameinfo-terminal'); ?>
        <span class="time"><?php echo esc_html(gameinfo_get_current_timestamp()); ?></span>
    </p>
</div>

<nav class="category-tabs">
    <a class="category-tab<?php echo is_home() && !is_category() ? ' active' : ''; ?>" href="<?php echo esc_url(home_url('/')); ?>">
        <span class="material-symbols-outlined">database</span> ALL_LOGS
    </a>
    <?php
    if (has_nav_menu('category')) {
        wp_nav_menu(array(
            'theme_location' => 'category',
            'container'      => false,
            'items_wrap'     => '%3$s',
            'walker'         => new GameInfo_Walker_Category_Tabs(),
        ));
    } else {
        // Vyloučit "Nezařazeno" / "Uncategorized" ve všech jazycích
        $exclude_ids = array(1);
        $uncategorized_en = get_category_by_slug('uncategorized');
        if ($uncategorized_en) {
            $exclude_ids[] = $uncategorized_en->term_id;
        }

        $categories = get_categories(array(
            'number'     => 4,
            'hide_empty' => false, // Show even empty categories
            'orderby'    => 'name',
            'order'      => 'ASC',
            'exclude'    => $exclude_ids,
        ));

        $icons = array('token', 'rocket_launch', 'memory', 'sports_esports');
        $i = 0;

        foreach ($categories as $category) {
            $is_active = is_category($category->term_id) ? ' active' : '';
            $icon = isset($icons[$i]) ? $icons[$i] : 'folder';
            ?>
            <a class="category-tab<?php echo $is_active; ?>" href="<?php echo esc_url(get_category_link($category->term_id)); ?>">
                <span class="material-symbols-outlined"><?php echo esc_html($icon); ?></span>
                <?php echo esc_html(strtoupper($category->name)); ?>
            </a>
            <?php
            $i++;
        }
    }
    ?>
</nav>

<div class="news-list">
    <?php
    // Debug info (remove in production)
    $post_count = wp_count_posts();
    ?>

    <?php if (have_posts()) : ?>
        <?php while (have_posts()) : the_post(); ?>
            <?php get_template_part('template-parts/content', 'news-item'); ?>
        <?php endwhile; ?>

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
                    [ERROR] <?php esc_html_e('No posts found', 'gameinfo-terminal'); ?>
                </h2>
                <div class="news-meta">
                    <span>EMPTY_RESULT_SET</span>
                    <span>Published: <?php echo esc_html($post_count->publish); ?></span>
                    <span>Draft: <?php echo esc_html($post_count->draft); ?></span>
                </div>
            </div>
        </div>
    <?php endif; ?>
</div>

<?php
// Pagination
the_posts_pagination(array(
    'mid_size'  => 2,
    'prev_text' => __('&laquo; PREV', 'gameinfo-terminal'),
    'next_text' => __('NEXT &raquo;', 'gameinfo-terminal'),
));

get_footer();
