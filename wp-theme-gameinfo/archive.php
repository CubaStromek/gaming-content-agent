<?php
/**
 * Archive template
 *
 * @package GameInfo_Terminal
 */

get_header();
?>

<div class="page-header">
    <h1 class="page-title mono-text">
        <?php
        if (is_category()) {
            echo 'FILTER_BY: [' . esc_html(mb_strtoupper(single_cat_title('', false), 'UTF-8')) . ']';
        } elseif (is_tag()) {
            echo 'TAG_SEARCH: [' . esc_html(mb_strtoupper(single_tag_title('', false), 'UTF-8')) . ']';
        } elseif (is_author()) {
            echo 'AUTHOR_LOGS: [' . esc_html(mb_strtoupper(get_the_author(), 'UTF-8')) . ']';
        } elseif (is_date()) {
            if (is_year()) {
                echo 'YEAR_ARCHIVE: [' . esc_html(get_the_date('Y')) . ']';
            } elseif (is_month()) {
                echo 'MONTH_ARCHIVE: [' . esc_html(get_the_date('Y-m')) . ']';
            } elseif (is_day()) {
                echo 'DAY_ARCHIVE: [' . esc_html(get_the_date('Y-m-d')) . ']';
            }
        } else {
            echo 'ARCHIVE_QUERY';
        }
        ?>
    </h1>
    <p class="last-indexed mono-text">
        <?php
        $archive_description = get_the_archive_description();
        if ($archive_description) {
            echo wp_kses_post($archive_description);
        } else {
            ?>
            <?php esc_html_e('Results found:', 'gameinfo-terminal'); ?>
            <span class="time"><?php echo esc_html($wp_query->found_posts); ?> entries</span>
            <?php
        }
        ?>
    </p>
</div>

<nav class="category-tabs">
    <a class="category-tab" href="<?php echo esc_url(home_url('/')); ?>">
        <span class="material-symbols-outlined">database</span> ALL_LOGS
    </a>
    <?php
    // Vyloučit "Nezařazeno" / "Uncategorized" ve všech jazycích
    $exclude_ids = array(1);
    $uncategorized_en = get_category_by_slug('uncategorized');
    if ($uncategorized_en) {
        $exclude_ids[] = $uncategorized_en->term_id;
    }

    $categories = get_categories(array(
        'number'     => 4,
        'hide_empty' => true,
        'orderby'    => 'count',
        'order'      => 'DESC',
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
            <?php echo esc_html(mb_strtoupper($category->name, 'UTF-8')); ?>
        </a>
        <?php
        $i++;
    }
    ?>
</nav>

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
                    [ERROR] <?php esc_html_e('No entries match current filter', 'gameinfo-terminal'); ?>
                </h2>
                <div class="news-meta">
                    <span>EMPTY_RESULT_SET</span>
                </div>
            </div>
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
