<?php
/**
 * Plugin Name: GameFo Kill Switch
 * Description: Remote kill switch for the GameFo mobile app. Allows disabling the app or enforcing a minimum version.
 * Version: 1.0.0
 * Author: GameFo
 */

if (!defined('ABSPATH')) {
    exit;
}

// Register REST API endpoint
add_action('rest_api_init', function () {
    register_rest_route('gamefo/v1', '/app-status', [
        'methods' => 'GET',
        'callback' => 'gamefo_kill_switch_status',
        'permission_callback' => '__return_true',
    ]);
});

function gamefo_kill_switch_status() {
    return rest_ensure_response([
        'enabled' => (bool) get_option('gamefo_app_enabled', true),
        'minVersion' => get_option('gamefo_app_min_version', '1.0.0'),
        'message' => get_option('gamefo_app_message', ''),
    ]);
}

// Admin menu
add_action('admin_menu', function () {
    add_options_page(
        'App Kill Switch',
        'App Kill Switch',
        'manage_options',
        'gamefo-kill-switch',
        'gamefo_kill_switch_page'
    );
});

// Register settings
add_action('admin_init', function () {
    register_setting('gamefo_kill_switch', 'gamefo_app_enabled', [
        'type' => 'boolean',
        'default' => true,
        'sanitize_callback' => 'rest_sanitize_boolean',
    ]);
    register_setting('gamefo_kill_switch', 'gamefo_app_min_version', [
        'type' => 'string',
        'default' => '1.0.0',
        'sanitize_callback' => 'sanitize_text_field',
    ]);
    register_setting('gamefo_kill_switch', 'gamefo_app_message', [
        'type' => 'string',
        'default' => '',
        'sanitize_callback' => 'sanitize_textarea_field',
    ]);
});

function gamefo_kill_switch_page() {
    if (!current_user_can('manage_options')) {
        return;
    }
    ?>
    <div class="wrap">
        <h1>App Kill Switch</h1>
        <form method="post" action="options.php">
            <?php settings_fields('gamefo_kill_switch'); ?>
            <table class="form-table">
                <tr>
                    <th scope="row">App Enabled</th>
                    <td>
                        <label>
                            <input type="checkbox" name="gamefo_app_enabled" value="1"
                                <?php checked(get_option('gamefo_app_enabled', true)); ?> />
                            Allow the app to function normally
                        </label>
                        <p class="description">Uncheck to block the app for all users immediately.</p>
                    </td>
                </tr>
                <tr>
                    <th scope="row">Minimum Version</th>
                    <td>
                        <input type="text" name="gamefo_app_min_version"
                            value="<?php echo esc_attr(get_option('gamefo_app_min_version', '1.0.0')); ?>"
                            placeholder="1.0.0" class="regular-text" />
                        <p class="description">Users with an older app version will be blocked (semver format: X.Y.Z).</p>
                    </td>
                </tr>
                <tr>
                    <th scope="row">Message</th>
                    <td>
                        <textarea name="gamefo_app_message" rows="4" class="large-text"
                            placeholder="Optional message shown to blocked users"><?php echo esc_textarea(get_option('gamefo_app_message', '')); ?></textarea>
                        <p class="description">Custom message displayed on the blocking screen. Leave empty for default.</p>
                    </td>
                </tr>
            </table>
            <?php submit_button(); ?>
        </form>
        <hr />
        <h2>API Preview</h2>
        <p>Endpoint: <code><?php echo esc_url(rest_url('gamefo/v1/app-status')); ?></code></p>
        <pre style="background: #f0f0f0; padding: 12px; border-radius: 4px;"><?php
            echo esc_html(wp_json_encode([
                'enabled' => (bool) get_option('gamefo_app_enabled', true),
                'minVersion' => get_option('gamefo_app_min_version', '1.0.0'),
                'message' => get_option('gamefo_app_message', ''),
            ], JSON_PRETTY_PRINT));
        ?></pre>
    </div>
    <?php
}
