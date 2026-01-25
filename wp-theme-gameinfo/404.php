<?php
/**
 * 404 template
 *
 * @package GameInfo_Terminal
 */

get_header();
?>

<div class="page-header" style="text-align: center; padding: 4rem 0;">
    <h1 class="page-title mono-text" style="font-size: 4rem; margin-bottom: 1rem;">
        <span style="color: #ef4444;">ERROR</span> 404
    </h1>
    <p class="mono-text" style="font-size: 1.5rem; color: #6b7280; margin-bottom: 2rem;">
        FILE_NOT_FOUND
    </p>

    <div class="mono-text" style="max-width: 32rem; margin: 0 auto; text-align: left; background: var(--input-bg); padding: 1.5rem; border-radius: 0.25rem;">
        <p style="color: var(--terminal-green); margin-bottom: 0.5rem;">$ cat /error.log</p>
        <p style="color: #9ca3af; margin-bottom: 1rem;">
            > Requested resource could not be located<br>
            > Path: <?php echo esc_html($_SERVER['REQUEST_URI']); ?><br>
            > Status: 404 Not Found<br>
            > Timestamp: <?php echo esc_html(date('d/m/Y')); ?>
        </p>
        <p style="color: var(--primary);">$ suggest --action</p>
        <p style="color: #d1d5db;">
            > Return to <a href="<?php echo esc_url(home_url('/')); ?>" style="color: var(--primary);">[HOME_INDEX]</a><br>
            > Try searching the database below
        </p>
    </div>

    <div style="margin-top: 2rem;">
        <?php get_search_form(); ?>
    </div>
</div>

<?php
get_footer();
