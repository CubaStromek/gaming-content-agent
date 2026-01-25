<?php
/**
 * Page template
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
                <span class="news-timestamp"><?php echo esc_html(get_the_modified_date('d/m/Y')); ?></span>
                <span class="news-tag">PAGE</span>
            </div>

            <h1 class="entry-title">
                [DOC] <?php the_title(); ?>
            </h1>
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
    </article>

    <?php
    if (comments_open() || get_comments_number()) :
        comments_template();
    endif;

endwhile;

get_footer();
