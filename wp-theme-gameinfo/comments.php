<?php
/**
 * Comments template
 *
 * @package GameInfo_Terminal
 */

if (post_password_required()) {
    return;
}
?>

<div id="comments" class="comments-area">
    <?php if (have_comments()) : ?>
        <h2 class="comments-title mono-text">
            COMMENTS_LOG: <?php comments_number('0 entries', '1 entry', '%s entries'); ?>
        </h2>

        <ol class="comment-list">
            <?php
            wp_list_comments(array(
                'style'       => 'ol',
                'short_ping'  => true,
                'avatar_size' => 0,
                'callback'    => 'gameinfo_comment_callback',
            ));
            ?>
        </ol>

        <?php
        the_comments_navigation(array(
            'prev_text' => __('&laquo; PREV_PAGE', 'gameinfo-terminal'),
            'next_text' => __('NEXT_PAGE &raquo;', 'gameinfo-terminal'),
        ));

    endif;

    if (!comments_open() && get_comments_number() && post_type_supports(get_post_type(), 'comments')) :
        ?>
        <p class="no-comments mono-text" style="color: #6b7280; font-size: 0.875rem;">
            [INFO] Comments are closed for this entry.
        </p>
    <?php endif; ?>

    <?php
    comment_form(array(
        'title_reply'          => __('SUBMIT_COMMENT', 'gameinfo-terminal'),
        'title_reply_to'       => __('REPLY_TO: %s', 'gameinfo-terminal'),
        'cancel_reply_link'    => __('[CANCEL]', 'gameinfo-terminal'),
        'label_submit'         => __('TRANSMIT', 'gameinfo-terminal'),
        'comment_field'        => '<p class="comment-form-comment"><label for="comment" class="mono-text" style="display: block; margin-bottom: 0.5rem; font-size: 0.75rem; color: #9ca3af;">MESSAGE_BODY *</label><textarea id="comment" name="comment" rows="6" required></textarea></p>',
        'class_form'           => 'comment-form',
        'class_submit'         => 'submit',
    ));
    ?>
</div>

<?php
/**
 * Custom comment callback
 */
function gameinfo_comment_callback($comment, $args, $depth) {
    $tag = ($args['style'] === 'div') ? 'div' : 'li';
    ?>
    <<?php echo $tag; ?> id="comment-<?php comment_ID(); ?>" <?php comment_class('comment'); ?>>
        <article class="comment-body">
            <header class="comment-meta">
                <span class="comment-author mono-text" style="color: var(--primary);">
                    <?php echo esc_html(strtoupper(get_comment_author())); ?>
                </span>
                <span class="mono-text" style="color: #6b7280; font-size: 0.75rem; margin-left: 0.5rem;">
                    @ <?php echo esc_html(get_comment_date('d/m/Y')); ?>
                </span>
            </header>
            <div class="comment-content" style="margin-top: 0.5rem;">
                <?php comment_text(); ?>
            </div>
            <?php if ($depth < $args['max_depth']) : ?>
                <div class="reply mono-text" style="margin-top: 0.5rem; font-size: 0.75rem;">
                    <?php
                    comment_reply_link(array_merge($args, array(
                        'reply_text' => __('[REPLY]', 'gameinfo-terminal'),
                        'depth'      => $depth,
                        'max_depth'  => $args['max_depth'],
                    )));
                    ?>
                </div>
            <?php endif; ?>
        </article>
    <?php
}
