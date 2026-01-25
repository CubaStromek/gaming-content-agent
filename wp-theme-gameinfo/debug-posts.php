<?php
/**
 * Debug template - upload to theme folder and visit: yoursite.com/?debug_posts=1
 * Delete after debugging!
 */

if (isset($_GET['debug_posts']) && current_user_can('manage_options')) {
    add_action('wp_head', 'gameinfo_debug_posts');
}

function gameinfo_debug_posts() {
    global $wp_query;

    echo '<div style="background:#1a1a2e;color:#0f0;padding:20px;font-family:monospace;position:fixed;top:0;left:0;right:0;z-index:99999;max-height:50vh;overflow:auto;">';
    echo '<h2 style="color:#0ff;">[DEBUG] WordPress Query Info</h2>';

    // Reading settings
    $show_on_front = get_option('show_on_front');
    $page_on_front = get_option('page_on_front');
    $page_for_posts = get_option('page_for_posts');

    echo '<p><strong>Reading Settings:</strong></p>';
    echo '<ul>';
    echo '<li>show_on_front: ' . esc_html($show_on_front) . '</li>';
    echo '<li>page_on_front (ID): ' . esc_html($page_on_front) . '</li>';
    echo '<li>page_for_posts (ID): ' . esc_html($page_for_posts) . '</li>';
    echo '</ul>';

    // Current template
    echo '<p><strong>Current Template:</strong> ' . esc_html(get_page_template_slug() ?: 'default') . '</p>';

    // Query info
    echo '<p><strong>Query Type:</strong></p>';
    echo '<ul>';
    echo '<li>is_home: ' . (is_home() ? 'YES' : 'NO') . '</li>';
    echo '<li>is_front_page: ' . (is_front_page() ? 'YES' : 'NO') . '</li>';
    echo '<li>is_singular: ' . (is_singular() ? 'YES' : 'NO') . '</li>';
    echo '<li>is_page: ' . (is_page() ? 'YES' : 'NO') . '</li>';
    echo '</ul>';

    // Post count
    $post_count = wp_count_posts();
    echo '<p><strong>Post Counts:</strong></p>';
    echo '<ul>';
    echo '<li>Published: ' . esc_html($post_count->publish) . '</li>';
    echo '<li>Draft: ' . esc_html($post_count->draft) . '</li>';
    echo '<li>Private: ' . esc_html($post_count->private) . '</li>';
    echo '</ul>';

    // Current query
    echo '<p><strong>Current Query:</strong></p>';
    echo '<ul>';
    echo '<li>Posts found: ' . esc_html($wp_query->found_posts) . '</li>';
    echo '<li>Posts per page: ' . esc_html($wp_query->query_vars['posts_per_page']) . '</li>';
    echo '</ul>';

    // Test query
    $test_query = new WP_Query(array(
        'post_type' => 'post',
        'post_status' => 'publish',
        'posts_per_page' => 5,
    ));

    echo '<p><strong>Test Query (latest 5 published posts):</strong></p>';
    if ($test_query->have_posts()) {
        echo '<ul>';
        while ($test_query->have_posts()) {
            $test_query->the_post();
            echo '<li>' . esc_html(get_the_title()) . ' (ID: ' . get_the_ID() . ', Status: ' . get_post_status() . ')</li>';
        }
        echo '</ul>';
        wp_reset_postdata();
    } else {
        echo '<p style="color:red;">NO POSTS FOUND!</p>';
    }

    echo '<p style="color:#ff0;"><strong>Instructions:</strong> Delete debug-posts.php from theme after debugging!</p>';
    echo '</div>';
}
