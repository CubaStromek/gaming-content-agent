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

<?php get_template_part('template-parts/category', 'tabs'); ?>

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
