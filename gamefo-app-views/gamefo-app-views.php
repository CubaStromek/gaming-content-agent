<?php
/**
 * Plugin Name: GAMEfo App Views
 * Description: Anonymous article view counter from the GAMEfo mobile app.
 * Version: 1.0.0
 * Author: GAMEfo
 * License: GPL-2.0-or-later
 */

if (!defined('ABSPATH')) {
    exit;
}

add_action('rest_api_init', function () {
    register_rest_route('gamefo/v1', '/views', [
        'methods'             => 'POST',
        'callback'            => 'gamefo_track_app_view',
        'permission_callback' => '__return_true',
        'args'                => [
            'post_id' => [
                'required'          => true,
                'type'              => 'integer',
                'sanitize_callback' => 'absint',
            ],
        ],
    ]);
});

/**
 * Increment the app view counter for a given post.
 */
function gamefo_track_app_view(WP_REST_Request $request): WP_REST_Response {
    $post_id = $request->get_param('post_id');

    $post = get_post($post_id);
    if (!$post || $post->post_status !== 'publish') {
        return new WP_REST_Response(['error' => 'Invalid post'], 404);
    }

    $current = (int) get_post_meta($post_id, 'gamefo_app_views', true);
    update_post_meta($post_id, 'gamefo_app_views', $current + 1);

    return new WP_REST_Response(['views' => $current + 1], 200);
}

// --- Admin Dashboard ---

add_action('admin_menu', function () {
    add_submenu_page(
        'tools.php',
        'App Views',
        'App Views',
        'manage_options',
        'gamefo-app-views',
        'gamefo_app_views_admin_page'
    );
});

/**
 * Render the App Views admin dashboard.
 */
function gamefo_app_views_admin_page(): void {
    global $wpdb;

    // Query all posts that have at least 1 app view, ordered by views desc, top 50
    $results = $wpdb->get_results(
        "SELECT p.ID, p.post_title, p.post_date, pm.meta_value AS views
         FROM {$wpdb->postmeta} pm
         INNER JOIN {$wpdb->posts} p ON p.ID = pm.post_id
         WHERE pm.meta_key = 'gamefo_app_views'
           AND CAST(pm.meta_value AS UNSIGNED) > 0
           AND p.post_status = 'publish'
         ORDER BY CAST(pm.meta_value AS UNSIGNED) DESC
         LIMIT 50"
    );

    $total_views    = 0;
    $tracked_posts  = count($results);

    foreach ($results as $row) {
        $total_views += (int) $row->views;
    }

    // For accurate tracked posts count (beyond top 50), query separately
    $full_tracked = (int) $wpdb->get_var(
        "SELECT COUNT(DISTINCT pm.post_id)
         FROM {$wpdb->postmeta} pm
         INNER JOIN {$wpdb->posts} p ON p.ID = pm.post_id
         WHERE pm.meta_key = 'gamefo_app_views'
           AND CAST(pm.meta_value AS UNSIGNED) > 0
           AND p.post_status = 'publish'"
    );

    $full_total_views = (int) $wpdb->get_var(
        "SELECT COALESCE(SUM(CAST(pm.meta_value AS UNSIGNED)), 0)
         FROM {$wpdb->postmeta} pm
         INNER JOIN {$wpdb->posts} p ON p.ID = pm.post_id
         WHERE pm.meta_key = 'gamefo_app_views'
           AND CAST(pm.meta_value AS UNSIGNED) > 0
           AND p.post_status = 'publish'"
    );

    $avg_views = $full_tracked > 0 ? round($full_total_views / $full_tracked, 1) : 0;

    ?>
    <div class="wrap">
        <h1>App Views</h1>
        <p>Article view statistics from the GAMEfo mobile app.</p>

        <div style="display: flex; gap: 16px; margin: 20px 0;">
            <div class="card" style="margin: 0; padding: 16px 24px; flex: 1; max-width: 280px;">
                <h2 style="margin: 0 0 4px; font-size: 28px; color: #1d2327;">
                    <?php echo esc_html(number_format_i18n($full_total_views)); ?>
                </h2>
                <p style="margin: 0; color: #646970;">Total App Views</p>
            </div>
            <div class="card" style="margin: 0; padding: 16px 24px; flex: 1; max-width: 280px;">
                <h2 style="margin: 0 0 4px; font-size: 28px; color: #1d2327;">
                    <?php echo esc_html(number_format_i18n($full_tracked)); ?>
                </h2>
                <p style="margin: 0; color: #646970;">Tracked Articles</p>
            </div>
            <div class="card" style="margin: 0; padding: 16px 24px; flex: 1; max-width: 280px;">
                <h2 style="margin: 0 0 4px; font-size: 28px; color: #1d2327;">
                    <?php echo esc_html($avg_views); ?>
                </h2>
                <p style="margin: 0; color: #646970;">Avg Views / Article</p>
            </div>
        </div>

        <?php if (empty($results)) : ?>
            <p>No app views recorded yet.</p>
        <?php else : ?>
            <table class="wp-list-table widefat fixed striped" style="margin-top: 12px;">
                <thead>
                    <tr>
                        <th style="width: 50px;">#</th>
                        <th>Article</th>
                        <th style="width: 100px;">Views</th>
                        <th style="width: 160px;">Published</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($results as $i => $row) :
                        $edit_link = get_edit_post_link($row->ID);
                    ?>
                        <tr>
                            <td><?php echo (int) ($i + 1); ?></td>
                            <td>
                                <?php if ($edit_link) : ?>
                                    <a href="<?php echo esc_url($edit_link); ?>">
                                        <?php echo esc_html($row->post_title); ?>
                                    </a>
                                <?php else : ?>
                                    <?php echo esc_html($row->post_title); ?>
                                <?php endif; ?>
                            </td>
                            <td><strong><?php echo esc_html(number_format_i18n((int) $row->views)); ?></strong></td>
                            <td><?php echo esc_html(date_i18n('Y-m-d H:i', strtotime($row->post_date))); ?></td>
                        </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
            <?php if ($full_tracked > 50) : ?>
                <p style="color: #646970; margin-top: 8px;">
                    Showing top 50 of <?php echo esc_html(number_format_i18n($full_tracked)); ?> tracked articles.
                </p>
            <?php endif; ?>
        <?php endif; ?>
    </div>
    <?php
}
