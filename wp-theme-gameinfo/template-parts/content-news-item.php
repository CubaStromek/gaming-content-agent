<?php
/**
 * Template part for displaying news items in the list
 *
 * @package GameInfo_Terminal
 */

$tag_type = gameinfo_get_post_tag_type();
$status_data = gameinfo_get_post_status_data();
$category_tag = gameinfo_get_category_tag();
$source = gameinfo_get_source();
$audio_url = gameinfo_get_audio_url();
?>

<article id="post-<?php the_ID(); ?>" <?php post_class('news-item'); ?>>
    <span class="news-timestamp"><?php echo esc_html(gameinfo_format_date()); ?></span>
    <div class="news-content">
        <h2 class="news-title">
            <a href="<?php the_permalink(); ?>">
                <span class="status-tag status-<?php echo esc_attr($status_data['type']); ?>"><?php echo esc_html($status_data['label']); ?></span> <?php the_title(); ?>
            </a>
        </h2>
        <div class="news-meta">
            <span class="news-tag<?php echo $tag_type === 'critical' ? ' critical' : ''; ?>">
                <?php echo esc_html($category_tag); ?>
            </span>
            <span><?php echo esc_html($source); ?></span>
            <span class="read-more"><?php esc_html_e('Read full report...', 'gameinfo-terminal'); ?></span>
        </div>
    </div>
    <?php if (!empty($audio_url)) : ?>
        <a href="<?php echo esc_url($audio_url); ?>" class="audio-link" target="_blank" title="<?php esc_attr_e('Listen to audio version', 'gameinfo-terminal'); ?>">
            <span class="material-symbols-outlined">headphones</span>
        </a>
    <?php endif; ?>
</article>
