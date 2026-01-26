<?php
/**
 * Plugin Name: GameFo Push Notifications
 * Description: Handles device tokens and sends push notifications via Expo when new posts are published.
 * Version: 1.0.0
 * Author: GAMEfo Team
 * Text Domain: gamefo-push
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * 1. Create DB Table for Tokens on plugin activation
 */
function gamefo_create_device_table() {
    global $wpdb;
    $table_name = $wpdb->prefix . 'gamefo_devices';
    $charset_collate = $wpdb->get_charset_collate();

    $sql = "CREATE TABLE $table_name (
        id mediumint(9) NOT NULL AUTO_INCREMENT,
        token varchar(255) NOT NULL,
        platform varchar(20) DEFAULT 'unknown',
        created_at datetime DEFAULT CURRENT_TIMESTAMP NOT NULL,
        last_used datetime DEFAULT CURRENT_TIMESTAMP NOT NULL,
        PRIMARY KEY (id),
        UNIQUE KEY token (token)
    ) $charset_collate;";

    require_once(ABSPATH . 'wp-admin/includes/upgrade.php');
    dbDelta($sql);

    add_option('gamefo_push_db_version', '1.0');
}
register_activation_hook(__FILE__, 'gamefo_create_device_table');

// Also create table when theme is switched (for theme-bundled version)
add_action('after_switch_theme', 'gamefo_create_device_table');

/**
 * 2. REST API Endpoint to Register Token
 */
add_action('rest_api_init', function () {
    // Register device token
    register_rest_route('gamefo/v1', '/devices', array(
        'methods' => 'POST',
        'callback' => 'gamefo_register_device',
        'permission_callback' => '__return_true'
    ));

    // Unregister device token
    register_rest_route('gamefo/v1', '/devices', array(
        'methods' => 'DELETE',
        'callback' => 'gamefo_unregister_device',
        'permission_callback' => '__return_true'
    ));

    // Get device count (for admin)
    register_rest_route('gamefo/v1', '/devices/count', array(
        'methods' => 'GET',
        'callback' => 'gamefo_get_device_count',
        'permission_callback' => function() {
            return current_user_can('manage_options');
        }
    ));
});

/**
 * Register a device token
 */
function gamefo_register_device(WP_REST_Request $request) {
    global $wpdb;
    $token = sanitize_text_field($request->get_param('token'));
    $platform = sanitize_text_field($request->get_param('platform') ?: 'unknown');

    // Validate Expo token format (compatible with PHP 7.4+)
    if (!$token || strpos($token, 'ExponentPushToken') !== 0) {
        return new WP_Error(
            'invalid_token',
            'Valid Expo push token required (must start with ExponentPushToken)',
            array('status' => 400)
        );
    }

    $table_name = $wpdb->prefix . 'gamefo_devices';

    $result = $wpdb->replace(
        $table_name,
        array(
            'token' => $token,
            'platform' => $platform,
            'created_at' => current_time('mysql'),
            'last_used' => current_time('mysql')
        ),
        array('%s', '%s', '%s', '%s')
    );

    if ($result === false) {
        return new WP_Error(
            'db_error',
            'Failed to save token',
            array('status' => 500)
        );
    }

    return new WP_REST_Response(array(
        'success' => true,
        'message' => 'Device registered successfully'
    ), 200);
}

/**
 * Unregister a device token
 */
function gamefo_unregister_device(WP_REST_Request $request) {
    global $wpdb;
    $token = sanitize_text_field($request->get_param('token'));

    if (!$token) {
        return new WP_Error('invalid_token', 'Token required', array('status' => 400));
    }

    $table_name = $wpdb->prefix . 'gamefo_devices';
    $wpdb->delete($table_name, array('token' => $token), array('%s'));

    return new WP_REST_Response(array(
        'success' => true,
        'message' => 'Device unregistered'
    ), 200);
}

/**
 * Get registered device count
 */
function gamefo_get_device_count() {
    global $wpdb;
    $table_name = $wpdb->prefix . 'gamefo_devices';
    $count = $wpdb->get_var("SELECT COUNT(*) FROM $table_name");

    return new WP_REST_Response(array(
        'count' => (int) $count
    ), 200);
}

/**
 * 3. Send Notification on Post Publish
 */
add_action('transition_post_status', 'gamefo_send_push_on_publish', 10, 3);

function gamefo_send_push_on_publish($new_status, $old_status, $post) {
    // Only trigger when post transitions TO 'publish' FROM something else
    if ($new_status !== 'publish' || $old_status === 'publish') {
        return;
    }

    // Only for 'post' post type
    if ($post->post_type !== 'post') {
        return;
    }

    // Skip autosaves and revisions
    if (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE) {
        return;
    }

    if (wp_is_post_revision($post->ID)) {
        return;
    }

    // Prevent duplicate sends using transient
    $transient_key = 'gamefo_push_sent_' . $post->ID;
    if (get_transient($transient_key)) {
        return;
    }
    set_transient($transient_key, true, 60); // Prevent re-send for 60 seconds

    // Send the notification
    gamefo_send_push_notification($post);
}

/**
 * Send push notification to all registered devices
 */
function gamefo_send_push_notification($post) {
    global $wpdb;
    $table_name = $wpdb->prefix . 'gamefo_devices';
    $tokens = $wpdb->get_col("SELECT token FROM $table_name");

    if (empty($tokens)) {
        return;
    }

    $api_url = 'https://exp.host/--/api/v2/push/send';

    // Prepare notification content
    $title = 'NOVY LOG PRIJAT';
    $body = wp_strip_all_tags($post->post_title);
    $data = array(
        'postId' => $post->ID,
        'url' => get_permalink($post->ID),
        'type' => 'new_post'
    );

    // Get featured image if available
    $image = null;
    if (has_post_thumbnail($post->ID)) {
        $image = get_the_post_thumbnail_url($post->ID, 'medium');
    }

    // Chunking for Expo API (max 100 per request)
    $chunks = array_chunk($tokens, 100);

    foreach ($chunks as $chunk) {
        $messages = array();

        foreach ($chunk as $token) {
            $message = array(
                'to' => $token,
                'title' => $title,
                'body' => $body,
                'data' => $data,
                'sound' => 'default',
                'priority' => 'high',
            );

            // Add image for rich notifications (Android)
            if ($image) {
                $message['image'] = $image;
            }

            $messages[] = $message;
        }

        if (!empty($messages)) {
            $response = wp_remote_post($api_url, array(
                'headers' => array(
                    'Content-Type' => 'application/json',
                    'Accept' => 'application/json',
                    'Accept-Encoding' => 'gzip, deflate',
                ),
                'body' => wp_json_encode($messages),
                'timeout' => 30,
                'blocking' => true
            ));

            // Log errors for debugging (optional)
            if (is_wp_error($response)) {
                error_log('GameFo Push Error: ' . $response->get_error_message());
            }
        }
    }

    // Log successful send
    error_log('GameFo Push: Sent notification for post ' . $post->ID . ' to ' . count($tokens) . ' devices');
}

/**
 * Admin menu page for managing devices
 */
add_action('admin_menu', function() {
    add_submenu_page(
        'options-general.php',
        'Push Notifications',
        'Push Notifications',
        'manage_options',
        'gamefo-push',
        'gamefo_push_admin_page'
    );
});

function gamefo_push_admin_page() {
    global $wpdb;
    $table_name = $wpdb->prefix . 'gamefo_devices';

    // Handle token deletion
    if (isset($_POST['delete_token']) && wp_verify_nonce($_POST['_wpnonce'], 'gamefo_delete_token')) {
        $token_id = intval($_POST['token_id']);
        $wpdb->delete($table_name, array('id' => $token_id), array('%d'));
        echo '<div class="notice notice-success"><p>Token deleted.</p></div>';
    }

    // Handle test notification
    if (isset($_POST['send_test']) && wp_verify_nonce($_POST['_wpnonce'], 'gamefo_send_test')) {
        $test_post = (object) array(
            'ID' => 0,
            'post_title' => 'Test Notification',
            'post_type' => 'post'
        );
        gamefo_send_push_notification($test_post);
        echo '<div class="notice notice-success"><p>Test notification sent!</p></div>';
    }

    $devices = $wpdb->get_results("SELECT * FROM $table_name ORDER BY last_used DESC LIMIT 100");
    $total = $wpdb->get_var("SELECT COUNT(*) FROM $table_name");
    ?>
    <div class="wrap">
        <h1>Push Notifications</h1>

        <div class="card" style="max-width: 400px; padding: 20px; margin-bottom: 20px;">
            <h2 style="margin-top: 0;">Statistics</h2>
            <p><strong>Registered devices:</strong> <?php echo esc_html($total); ?></p>
            <form method="post" style="margin-top: 15px;">
                <?php wp_nonce_field('gamefo_send_test'); ?>
                <button type="submit" name="send_test" class="button button-secondary">
                    Send Test Notification
                </button>
            </form>
        </div>

        <h2>Registered Devices</h2>
        <table class="wp-list-table widefat fixed striped">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Token</th>
                    <th>Platform</th>
                    <th>Registered</th>
                    <th>Last Used</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                <?php if (empty($devices)) : ?>
                    <tr><td colspan="6">No devices registered yet.</td></tr>
                <?php else : ?>
                    <?php foreach ($devices as $device) : ?>
                        <tr>
                            <td><?php echo esc_html($device->id); ?></td>
                            <td><code style="font-size: 11px;"><?php echo esc_html(substr($device->token, 0, 40) . '...'); ?></code></td>
                            <td><?php echo esc_html($device->platform); ?></td>
                            <td><?php echo esc_html($device->created_at); ?></td>
                            <td><?php echo esc_html($device->last_used); ?></td>
                            <td>
                                <form method="post" style="display: inline;">
                                    <?php wp_nonce_field('gamefo_delete_token'); ?>
                                    <input type="hidden" name="token_id" value="<?php echo esc_attr($device->id); ?>">
                                    <button type="submit" name="delete_token" class="button button-small" onclick="return confirm('Delete this token?');">
                                        Delete
                                    </button>
                                </form>
                            </td>
                        </tr>
                    <?php endforeach; ?>
                <?php endif; ?>
            </tbody>
        </table>

        <div class="card" style="max-width: 600px; padding: 20px; margin-top: 20px;">
            <h3 style="margin-top: 0;">API Endpoints</h3>
            <p><code>POST /wp-json/gamefo/v1/devices</code> - Register token</p>
            <pre style="background: #f1f1f1; padding: 10px;">{"token": "ExponentPushToken[xxx]", "platform": "ios"}</pre>
            <p><code>DELETE /wp-json/gamefo/v1/devices</code> - Unregister token</p>
            <pre style="background: #f1f1f1; padding: 10px;">{"token": "ExponentPushToken[xxx]"}</pre>
        </div>
    </div>
    <?php
}
