<?php
/**
 * GameInfo Terminal Theme Functions
 *
 * @package GameInfo_Terminal
 */

if (!defined('ABSPATH')) {
    exit;
}

define('GAMEINFO_VERSION', '1.5.2');

/**
 * Theme Setup
 */
function gameinfo_setup() {
    // Add theme support
    add_theme_support('title-tag');
    add_theme_support('post-thumbnails');
    add_theme_support('html5', array(
        'search-form',
        'comment-form',
        'comment-list',
        'gallery',
        'caption',
        'style',
        'script',
    ));
    add_theme_support('custom-logo', array(
        'height'      => 50,
        'width'       => 200,
        'flex-height' => true,
        'flex-width'  => true,
    ));
    add_theme_support('automatic-feed-links');

    // Gutenberg/Block editor support
    add_theme_support('wp-block-styles');
    add_theme_support('responsive-embeds');
    add_theme_support('align-wide');

    // Register navigation menus
    register_nav_menus(array(
        'primary'   => __('Primary Menu', 'gameinfo-terminal'),
        'footer'    => __('Footer Menu', 'gameinfo-terminal'),
        'category'  => __('Category Tabs', 'gameinfo-terminal'),
    ));

    // Set content width
    if (!isset($content_width)) {
        $content_width = 1200;
    }
}
add_action('after_setup_theme', 'gameinfo_setup');

/**
 * Enqueue Scripts and Styles
 */
function gameinfo_scripts() {
    // Google Fonts
    wp_enqueue_style(
        'gameinfo-google-fonts',
        'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fira+Code:wght@400;500;700&subset=latin-ext&display=swap',
        array(),
        null
    );

    // Material Symbols
    wp_enqueue_style(
        'gameinfo-material-symbols',
        'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap',
        array(),
        null
    );

    // WordPress Block styles (for Gutenberg embeds, etc.)
    wp_enqueue_style('wp-block-library');

    // Main stylesheet
    wp_enqueue_style(
        'gameinfo-style',
        get_stylesheet_uri(),
        array('wp-block-library'),
        GAMEINFO_VERSION
    );

    // Theme JavaScript
    wp_enqueue_script(
        'gameinfo-scripts',
        get_template_directory_uri() . '/assets/js/main.js',
        array(),
        GAMEINFO_VERSION,
        true
    );

    // Comment reply script
    if (is_singular() && comments_open() && get_option('thread_comments')) {
        wp_enqueue_script('comment-reply');
    }
}
add_action('wp_enqueue_scripts', 'gameinfo_scripts');

/**
 * Register Sidebars/Widget Areas
 */
function gameinfo_widgets_init() {
    register_sidebar(array(
        'name'          => __('Sidebar', 'gameinfo-terminal'),
        'id'            => 'sidebar-1',
        'description'   => __('Add widgets here.', 'gameinfo-terminal'),
        'before_widget' => '<section id="%1$s" class="widget %2$s">',
        'after_widget'  => '</section>',
        'before_title'  => '<h2 class="widget-title">',
        'after_title'   => '</h2>',
    ));

    register_sidebar(array(
        'name'          => __('Footer Widget Area', 'gameinfo-terminal'),
        'id'            => 'footer-1',
        'description'   => __('Footer widgets.', 'gameinfo-terminal'),
        'before_widget' => '<section id="%1$s" class="widget %2$s">',
        'after_widget'  => '</section>',
        'before_title'  => '<h2 class="widget-title">',
        'after_title'   => '</h2>',
    ));
}
add_action('widgets_init', 'gameinfo_widgets_init');

/**
 * Custom Walker for Primary Navigation with Dropdown Support
 */
class GameInfo_Walker_Nav_Menu extends Walker_Nav_Menu {
    public function start_el(&$output, $item, $depth = 0, $args = null, $id = 0) {
        $classes = empty($item->classes) ? array() : (array) $item->classes;
        $has_children = in_array('menu-item-has-children', $classes);
        $active_class = in_array('current-menu-item', $classes) ? ' active' : '';
        $parent_class = $has_children ? ' has-dropdown' : '';

        if ($depth === 0) {
            $output .= '<div class="nav-item' . $parent_class . '">';
            $output .= '<a class="nav-link text-gray-500 hover:text-white transition-colors' . $active_class . '" href="' . esc_url($item->url) . '">';
            $output .= '[' . esc_html($item->title) . ']';
            if ($has_children) {
                $output .= ' <span class="dropdown-arrow">▼</span>';
            }
            $output .= '</a>';
        } else {
            $output .= '<a class="dropdown-link' . $active_class . '" href="' . esc_url($item->url) . '">';
            $output .= esc_html($item->title);
            $output .= '</a>';
        }
    }

    public function end_el(&$output, $item, $depth = 0, $args = null) {
        if ($depth === 0) {
            $output .= '</div>';
        }
    }

    public function start_lvl(&$output, $depth = 0, $args = null) {
        $output .= '<div class="dropdown-menu">';
    }

    public function end_lvl(&$output, $depth = 0, $args = null) {
        $output .= '</div>';
    }
}

/**
 * Custom Walker for Category Tabs with Dropdown Support
 */
class GameInfo_Walker_Category_Tabs extends Walker_Nav_Menu {
    public function start_el(&$output, $item, $depth = 0, $args = null, $id = 0) {
        $classes = empty($item->classes) ? array() : (array) $item->classes;
        $has_children = in_array('menu-item-has-children', $classes);
        $active_class = in_array('current-menu-item', $classes) ? ' active' : '';

        $icon = 'database';
        $title_lower = strtolower($item->title);
        if (strpos($title_lower, 'indie') !== false) {
            $icon = 'token';
        } elseif (strpos($title_lower, 'triple') !== false || strpos($title_lower, 'aaa') !== false) {
            $icon = 'rocket_launch';
        } elseif (strpos($title_lower, 'hardware') !== false) {
            $icon = 'memory';
        } elseif (strpos($title_lower, 'tech') !== false || strpos($title_lower, 'hardware') !== false) {
            $icon = 'memory';
        } elseif (strpos($title_lower, 'zpráv') !== false || strpos($title_lower, 'news') !== false) {
            $icon = 'newspaper';
        } elseif (strpos($title_lower, 'recenz') !== false || strpos($title_lower, 'review') !== false) {
            $icon = 'rate_review';
        }

        if ($depth === 0) {
            $parent_class = $has_children ? ' has-dropdown' : '';
            $output .= '<div class="category-tab-wrapper' . $parent_class . '">';
            $output .= '<a class="category-tab' . $active_class . '" href="' . esc_url($item->url) . '">';
            $output .= '<span class="material-symbols-outlined">' . esc_html($icon) . '</span>';
            $output .= esc_html(strtoupper($item->title));
            if ($has_children) {
                $output .= ' <span class="dropdown-arrow">▼</span>';
            }
            $output .= '</a>';
        } else {
            $output .= '<a class="dropdown-link' . $active_class . '" href="' . esc_url($item->url) . '">';
            $output .= esc_html($item->title);
            $output .= '</a>';
        }
    }

    public function end_el(&$output, $item, $depth = 0, $args = null) {
        if ($depth === 0) {
            $output .= '</div>';
        }
    }

    public function start_lvl(&$output, $depth = 0, $args = null) {
        $output .= '<div class="dropdown-menu">';
    }

    public function end_lvl(&$output, $depth = 0, $args = null) {
        $output .= '</div>';
    }
}

/**
 * Get post tag type for styling
 */
function gameinfo_get_post_tag_type($post_id = null) {
    if (!$post_id) {
        $post_id = get_the_ID();
    }

    $categories = get_the_category($post_id);
    if (!empty($categories)) {
        $cat_name = strtolower($categories[0]->name);
        if (strpos($cat_name, 'leak') !== false || strpos($cat_name, 'critical') !== false) {
            return 'critical';
        }
    }

    $tags = get_the_tags($post_id);
    if ($tags) {
        foreach ($tags as $tag) {
            $tag_name = strtolower($tag->name);
            if (strpos($tag_name, 'leak') !== false || strpos($tag_name, 'critical') !== false) {
                return 'critical';
            }
        }
    }

    return 'normal';
}

/**
 * Get post status prefix with type
 * Returns array with 'label' and 'type' for styling
 */
function gameinfo_get_post_status_data($post_id = null) {
    if (!$post_id) {
        $post_id = get_the_ID();
    }

    $categories = get_the_category($post_id);
    $tags = get_the_tags($post_id);

    $all_terms = array();
    if (!empty($categories)) {
        foreach ($categories as $cat) {
            $all_terms[] = strtolower($cat->name);
        }
    }
    if ($tags) {
        foreach ($tags as $tag) {
            $all_terms[] = strtolower($tag->name);
        }
    }

    foreach ($all_terms as $term) {
        if (strpos($term, 'leak') !== false) return array('label' => '[LEAK]', 'type' => 'leak');
        if (strpos($term, 'success') !== false) return array('label' => '[SUCCESS]', 'type' => 'success');
        if (strpos($term, 'critical') !== false) return array('label' => '[CRITICAL]', 'type' => 'critical');
        if (strpos($term, 'indie') !== false) return array('label' => '[INDIE]', 'type' => 'indie');
        if (strpos($term, 'review') !== false) return array('label' => '[REVIEW]', 'type' => 'review');
        if (strpos($term, 'trailer') !== false) return array('label' => '[TRAILER]', 'type' => 'trailer');
        if (strpos($term, 'rumor') !== false || strpos($term, 'rumour') !== false) return array('label' => '[RUMOR]', 'type' => 'rumor');
        if (strpos($term, 'update') !== false) return array('label' => '[UPDATE]', 'type' => 'update');
        if (strpos($term, 'news') !== false) return array('label' => '[NEWS]', 'type' => 'news');
    }

    return array('label' => '[INFO]', 'type' => 'info');
}

/**
 * Get post status prefix (backward compatible)
 */
function gameinfo_get_post_status_prefix($post_id = null) {
    $data = gameinfo_get_post_status_data($post_id);
    return $data['label'];
}

/**
 * Get category tag for display
 */
function gameinfo_get_category_tag($post_id = null) {
    if (!$post_id) {
        $post_id = get_the_ID();
    }

    $categories = get_the_category($post_id);
    if (!empty($categories)) {
        return strtoupper($categories[0]->name);
    }

    return 'GENERAL';
}

/**
 * Custom excerpt length
 */
function gameinfo_excerpt_length($length) {
    return 30;
}
add_filter('excerpt_length', 'gameinfo_excerpt_length', 999);

/**
 * Custom excerpt more
 */
function gameinfo_excerpt_more($more) {
    return '...';
}
add_filter('excerpt_more', 'gameinfo_excerpt_more');

/**
 * Add custom body classes
 */
function gameinfo_body_classes($classes) {
    $classes[] = 'dark';

    if (is_singular()) {
        $classes[] = 'singular';
    }

    return $classes;
}
add_filter('body_class', 'gameinfo_body_classes');

/**
 * Customize search form
 */
function gameinfo_search_form($form) {
    $form = '<form role="search" method="get" class="search-form" action="' . esc_url(home_url('/')) . '">
        <div class="search-wrapper">
            <span class="material-symbols-outlined search-icon">search</span>
            <input type="search" class="search-field" placeholder="' . esc_attr__('QUERY_SYSTEM...', 'gameinfo-terminal') . '" value="' . get_search_query() . '" name="s" />
        </div>
    </form>';

    return $form;
}
add_filter('get_search_form', 'gameinfo_search_form');

/**
 * Get current timestamp for display
 */
function gameinfo_get_current_timestamp() {
    return date('d/m/Y');
}

/**
 * Format post date as terminal timestamp
 */
function gameinfo_format_date($post_id = null) {
    if (!$post_id) {
        $post_id = get_the_ID();
    }

    return get_the_date('d/m/Y', $post_id);
}

/**
 * Get source tag (custom field or default)
 * If source is a URL, extracts just the domain (e.g. PCGAMER.COM)
 */
function gameinfo_get_source($post_id = null) {
    if (!$post_id) {
        $post_id = get_the_ID();
    }

    $source = get_post_meta($post_id, 'gameinfo_source', true);
    if (!empty($source)) {
        // If source is a URL, extract just the domain
        if (filter_var($source, FILTER_VALIDATE_URL)) {
            $parsed = parse_url($source);
            if (isset($parsed['host'])) {
                $host = $parsed['host'];
                // Remove www. prefix
                $host = preg_replace('/^www\./', '', $host);
                return strtoupper($host);
            }
        }
        return strtoupper($source);
    }

    $author = get_the_author_meta('display_name', get_post_field('post_author', $post_id));
    return 'SOURCE: ' . strtoupper(str_replace(' ', '_', $author));
}

/**
 * Get raw source URL (returns URL if source is a valid URL, otherwise empty string)
 */
function gameinfo_get_source_url($post_id = null) {
    if (!$post_id) {
        $post_id = get_the_ID();
    }

    $source = get_post_meta($post_id, 'gameinfo_source', true);
    if (!empty($source) && filter_var($source, FILTER_VALIDATE_URL)) {
        return $source;
    }

    return '';
}

/**
 * Add custom meta boxes for source field and audio URL
 */
function gameinfo_add_meta_boxes() {
    add_meta_box(
        'gameinfo_source_meta',
        __('Source Information', 'gameinfo-terminal'),
        'gameinfo_source_meta_callback',
        'post',
        'side',
        'high'
    );

    add_meta_box(
        'gameinfo_audio_meta',
        __('Audio Version', 'gameinfo-terminal'),
        'gameinfo_audio_meta_callback',
        'post',
        'side',
        'high'
    );
}
add_action('add_meta_boxes', 'gameinfo_add_meta_boxes');

/**
 * Audio URL meta box callback
 */
function gameinfo_audio_meta_callback($post) {
    wp_nonce_field('gameinfo_save_audio', 'gameinfo_audio_nonce');
    $value = get_post_meta($post->ID, 'gameinfo_audio_url', true);
    echo '<label for="gameinfo_audio_url">' . __('Audio URL:', 'gameinfo-terminal') . '</label>';
    echo '<input type="url" id="gameinfo_audio_url" name="gameinfo_audio_url" value="' . esc_attr($value) . '" style="width:100%;margin-top:5px;" placeholder="https://example.com/audio.mp3" />';
    echo '<p class="description" style="margin-top:5px;">' . __('Link to audio version of this article (MP3, podcast, etc.)', 'gameinfo-terminal') . '</p>';
}

/**
 * Save audio URL meta
 */
function gameinfo_save_audio_meta($post_id) {
    if (!isset($_POST['gameinfo_audio_nonce'])) {
        return;
    }
    if (!wp_verify_nonce($_POST['gameinfo_audio_nonce'], 'gameinfo_save_audio')) {
        return;
    }
    if (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE) {
        return;
    }
    if (!current_user_can('edit_post', $post_id)) {
        return;
    }
    if (isset($_POST['gameinfo_audio_url'])) {
        update_post_meta($post_id, 'gameinfo_audio_url', esc_url_raw($_POST['gameinfo_audio_url']));
    }
}
add_action('save_post', 'gameinfo_save_audio_meta');

/**
 * Get audio URL for a post
 */
function gameinfo_get_audio_url($post_id = null) {
    if (!$post_id) {
        $post_id = get_the_ID();
    }
    return get_post_meta($post_id, 'gameinfo_audio_url', true);
}

function gameinfo_source_meta_callback($post) {
    wp_nonce_field('gameinfo_save_source', 'gameinfo_source_nonce');
    $value = get_post_meta($post->ID, 'gameinfo_source', true);
    echo '<label for="gameinfo_source">' . __('Source Tag:', 'gameinfo-terminal') . '</label>';
    echo '<input type="text" id="gameinfo_source" name="gameinfo_source" value="' . esc_attr($value) . '" style="width:100%;margin-top:5px;" placeholder="e.g., OFFICIAL_PR, LEAK_SOURCE" />';
}

function gameinfo_save_source_meta($post_id) {
    if (!isset($_POST['gameinfo_source_nonce'])) {
        return;
    }
    if (!wp_verify_nonce($_POST['gameinfo_source_nonce'], 'gameinfo_save_source')) {
        return;
    }
    if (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE) {
        return;
    }
    if (!current_user_can('edit_post', $post_id)) {
        return;
    }
    if (isset($_POST['gameinfo_source'])) {
        update_post_meta($post_id, 'gameinfo_source', sanitize_text_field($_POST['gameinfo_source']));
    }
}
add_action('save_post', 'gameinfo_save_source_meta');

/**
 * AJAX Load More Posts
 */
function gameinfo_load_more_posts() {
    check_ajax_referer('gameinfo_loadmore', 'nonce');

    $args = array(
        'post_type'      => 'post',
        'posts_per_page' => 6,
        'paged'          => isset($_POST['page']) ? intval($_POST['page']) : 1,
        'post_status'    => 'publish',
    );

    if (isset($_POST['category']) && !empty($_POST['category'])) {
        $args['category_name'] = sanitize_text_field($_POST['category']);
    }

    $query = new WP_Query($args);

    if ($query->have_posts()) {
        while ($query->have_posts()) {
            $query->the_post();
            get_template_part('template-parts/content', 'news-item');
        }
    }

    wp_die();
}
add_action('wp_ajax_gameinfo_loadmore', 'gameinfo_load_more_posts');
add_action('wp_ajax_nopriv_gameinfo_loadmore', 'gameinfo_load_more_posts');

/**
 * Localize script for AJAX
 */
function gameinfo_localize_scripts() {
    wp_localize_script('gameinfo-scripts', 'gameinfo_ajax', array(
        'ajax_url' => admin_url('admin-ajax.php'),
        'nonce'    => wp_create_nonce('gameinfo_loadmore'),
    ));
}
add_action('wp_enqueue_scripts', 'gameinfo_localize_scripts');

/**
 * Theme Customizer
 */
function gameinfo_customize_register($wp_customize) {
    // Theme Options Section
    $wp_customize->add_section('gameinfo_options', array(
        'title'    => __('Theme Options', 'gameinfo-terminal'),
        'priority' => 30,
    ));

    // Site Title Display
    $wp_customize->add_setting('gameinfo_site_title', array(
        'default'           => 'game_info',
        'sanitize_callback' => 'sanitize_text_field',
    ));

    $wp_customize->add_control('gameinfo_site_title', array(
        'label'   => __('Terminal Title', 'gameinfo-terminal'),
        'section' => 'gameinfo_options',
        'type'    => 'text',
    ));

    // Path Display
    $wp_customize->add_setting('gameinfo_path', array(
        'default'           => '~/news',
        'sanitize_callback' => 'sanitize_text_field',
    ));

    $wp_customize->add_control('gameinfo_path', array(
        'label'   => __('Terminal Path', 'gameinfo-terminal'),
        'section' => 'gameinfo_options',
        'type'    => 'text',
    ));

    // Build Version
    $wp_customize->add_setting('gameinfo_build_version', array(
        'default'           => '2.4.0-stable',
        'sanitize_callback' => 'sanitize_text_field',
    ));

    $wp_customize->add_control('gameinfo_build_version', array(
        'label'   => __('Build Version', 'gameinfo-terminal'),
        'section' => 'gameinfo_options',
        'type'    => 'text',
    ));

    // Facebook URL
    $wp_customize->add_setting('gameinfo_facebook_url', array(
        'default'           => '',
        'sanitize_callback' => 'esc_url_raw',
    ));

    $wp_customize->add_control('gameinfo_facebook_url', array(
        'label'       => __('Facebook Page URL', 'gameinfo-terminal'),
        'description' => __('Link to your Facebook page (displayed in header)', 'gameinfo-terminal'),
        'section'     => 'gameinfo_options',
        'type'        => 'url',
    ));
}
add_action('customize_register', 'gameinfo_customize_register');

/**
 * Get theme option with default
 */
function gameinfo_get_option($option, $default = '') {
    return get_theme_mod('gameinfo_' . $option, $default);
}

/**
 * Load theme textdomain for translations
 */
function gameinfo_load_textdomain() {
    load_theme_textdomain('gameinfo-terminal', get_template_directory() . '/languages');
}
add_action('after_setup_theme', 'gameinfo_load_textdomain');

/**
 * Language Switcher for Polylang
 * Returns HTML for language switcher buttons
 */
function gameinfo_language_switcher() {
    // Check if Polylang is active
    if (!function_exists('pll_the_languages')) {
        return '';
    }

    $output = '<div class="language-switcher">';

    $languages = pll_the_languages(array(
        'show_flags' => 0,
        'show_names' => 0,
        'display_names_as' => 'slug',
        'hide_current' => 0,
        'raw' => 1,
    ));

    if ($languages) {
        foreach ($languages as $lang) {
            $active_class = $lang['current_lang'] ? ' active' : '';
            $slug = strtoupper($lang['slug']);
            $output .= '<a href="' . esc_url($lang['url']) . '" class="lang-btn' . $active_class . '" lang="' . esc_attr($lang['locale']) . '">';
            $output .= esc_html($slug);
            $output .= '</a>';
        }
    }

    $output .= '</div>';

    return $output;
}

/**
 * Fallback language switcher when Polylang is not active
 * Shows static CZ/EN buttons for preview purposes
 */
function gameinfo_language_switcher_fallback() {
    $current_locale = get_locale();
    $is_czech = (strpos($current_locale, 'cs') === 0);

    $output = '<div class="language-switcher">';
    $output .= '<span class="lang-btn' . ($is_czech ? ' active' : '') . '">CZ</span>';
    $output .= '<span class="lang-btn' . (!$is_czech ? ' active' : '') . '">EN</span>';
    $output .= '</div>';

    return $output;
}

/**
 * Get language switcher (with fallback)
 */
function gameinfo_get_language_switcher() {
    if (function_exists('pll_the_languages')) {
        return gameinfo_language_switcher();
    }
    return gameinfo_language_switcher_fallback();
}

/**
 * Get Facebook button for header
 * Returns HTML for Facebook link button
 */
function gameinfo_get_facebook_button() {
    $facebook_url = get_theme_mod('gameinfo_facebook_url', '');

    if (empty($facebook_url)) {
        return '';
    }

    $output = '<a href="' . esc_url($facebook_url) . '" class="social-btn facebook-btn" target="_blank" rel="noopener noreferrer" aria-label="' . esc_attr__('Facebook', 'gameinfo-terminal') . '">';
    $output .= '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>';
    $output .= '</a>';

    return $output;
}

/**
 * Get RSS button for header
 * Returns HTML for RSS feed link button
 * Respects Polylang language if active
 */
function gameinfo_get_rss_button() {
    // Get language-specific feed URL if Polylang is active
    if (function_exists('pll_current_language')) {
        $lang = pll_current_language();
        $feed_url = home_url('/feed/?lang=' . $lang);
    } else {
        $feed_url = get_bloginfo('rss2_url');
    }

    $output = '<a href="' . esc_url($feed_url) . '" class="social-btn rss-btn" target="_blank" rel="noopener noreferrer" aria-label="' . esc_attr__('RSS Feed', 'gameinfo-terminal') . '">';
    $output .= '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M6.18 15.64a2.18 2.18 0 1 1 0 4.36 2.18 2.18 0 0 1 0-4.36m12.03 4.36a14.2 14.2 0 0 0-14.2-14.2V3.62A16.4 16.4 0 0 1 20.4 20h-2.19m-5.45 0a8.75 8.75 0 0 0-8.75-8.75V9.07A10.94 10.94 0 0 1 14.94 20h-2.18z"/></svg>';
    $output .= '</a>';

    return $output;
}

/**
 * Include debug file if exists
 */
if (file_exists(get_template_directory() . '/debug-posts.php')) {
    require_once get_template_directory() . '/debug-posts.php';
}

/**
 * Custom Login Page - Terminal Style
 */
function gameinfo_login_styles() {
    $site_title = get_theme_mod('gameinfo_site_title', 'game_info');
    ?>
    <style type="text/css">
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');

        body.login {
            background-color: #101c22;
            font-family: 'Fira Code', monospace;
        }

        .login #login {
            background-color: #1e1e1e;
            padding: 2rem;
            border-radius: 0.5rem;
            border: 1px solid rgba(255, 255, 255, 0.05);
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            width: 360px;
        }

        /* Terminal header bar */
        .login #login::before {
            content: '';
            display: block;
            background: #181818;
            margin: -2rem -2rem 1.5rem -2rem;
            padding: 1rem 1.5rem;
            border-radius: 0.5rem 0.5rem 0 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        /* Window dots */
        .login #login::after {
            content: '● ● ●';
            position: absolute;
            top: 0.85rem;
            left: 1.5rem;
            font-size: 0.75rem;
            letter-spacing: 0.35rem;
            background: linear-gradient(90deg, rgba(239, 68, 68, 0.8) 0%, rgba(239, 68, 68, 0.8) 33%, rgba(234, 179, 8, 0.8) 33%, rgba(234, 179, 8, 0.8) 66%, rgba(34, 197, 94, 0.8) 66%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .login #login {
            position: relative;
        }

        /* Logo */
        .login h1 a {
            background-image: none !important;
            text-indent: 0 !important;
            width: auto !important;
            height: auto !important;
            font-size: 1.5rem !important;
            font-weight: 700;
            color: #fff;
            font-family: 'Fira Code', monospace;
        }

        .login h1 a::before {
            content: '> ';
            color: #13a4ec;
        }

        .login h1 a::after {
            content: ' █';
            color: #13a4ec;
            animation: blink 1s step-end infinite;
        }

        @keyframes blink {
            50% { opacity: 0; }
        }

        /* Form */
        .login form {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
            margin-top: 1.5rem !important;
        }

        .login form .input,
        .login form input[type="text"],
        .login form input[type="password"] {
            background-color: #282828 !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            color: #d1d5db !important;
            font-family: 'Fira Code', monospace !important;
            font-size: 0.875rem !important;
            padding: 0.75rem !important;
            border-radius: 0.125rem !important;
            box-shadow: none !important;
        }

        .login form .input:focus,
        .login form input[type="text"]:focus,
        .login form input[type="password"]:focus {
            border-color: #13a4ec !important;
            box-shadow: 0 0 0 1px #13a4ec !important;
            outline: none !important;
        }

        .login form .input::placeholder {
            color: #4b5563 !important;
        }

        /* Labels */
        .login label {
            color: #9ca3af !important;
            font-family: 'Fira Code', monospace !important;
            font-size: 0.75rem !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .login label::before {
            content: '$ ';
            color: #4ade80;
        }

        /* Submit button */
        .login .submit .button,
        .login #wp-submit {
            background-color: #13a4ec !important;
            border: none !important;
            color: #fff !important;
            font-family: 'Fira Code', monospace !important;
            font-size: 0.875rem !important;
            font-weight: 600 !important;
            padding: 0.75rem 1.5rem !important;
            border-radius: 0.125rem !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            width: 100%;
            margin-top: 1rem !important;
            cursor: pointer;
            transition: all 0.2s ease;
            text-shadow: none !important;
            box-shadow: none !important;
        }

        .login .submit .button:hover,
        .login #wp-submit:hover {
            background-color: #0d8fd4 !important;
        }

        .login .submit .button:focus,
        .login #wp-submit:focus {
            box-shadow: 0 0 0 2px #13a4ec !important;
        }

        /* Remember me */
        .login .forgetmenot {
            margin-top: 1rem !important;
        }

        .login .forgetmenot label {
            color: #6b7280 !important;
            font-size: 0.75rem !important;
        }

        .login .forgetmenot label::before {
            content: none;
        }

        .login input[type="checkbox"] {
            background-color: #282828 !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
        }

        .login input[type="checkbox"]:checked {
            background-color: #13a4ec !important;
            border-color: #13a4ec !important;
        }

        /* Links */
        .login #nav,
        .login #backtoblog {
            text-align: center;
            margin-top: 1rem !important;
        }

        .login #nav a,
        .login #backtoblog a {
            color: #6b7280 !important;
            font-family: 'Fira Code', monospace !important;
            font-size: 0.75rem !important;
            text-decoration: none;
            transition: color 0.2s ease;
        }

        .login #nav a:hover,
        .login #backtoblog a:hover {
            color: #13a4ec !important;
        }

        /* Error messages */
        .login .message,
        .login #login_error {
            background-color: #282828 !important;
            border-left: 3px solid #13a4ec !important;
            color: #d1d5db !important;
            font-family: 'Fira Code', monospace !important;
            font-size: 0.75rem !important;
            padding: 0.75rem 1rem !important;
            margin-bottom: 1rem !important;
            box-shadow: none !important;
        }

        .login #login_error {
            border-left-color: #ef4444 !important;
        }

        .login #login_error a {
            color: #13a4ec !important;
        }

        /* Privacy policy */
        .login .privacy-policy-page-link {
            text-align: center;
            margin-top: 1rem;
        }

        .login .privacy-policy-page-link a {
            color: #4b5563 !important;
            font-family: 'Fira Code', monospace !important;
            font-size: 0.625rem !important;
        }

        /* System status line */
        .login #login h1::after {
            content: 'SYSTEM: AUTHENTICATION_REQUIRED';
            display: block;
            font-size: 0.625rem;
            color: rgba(74, 222, 128, 0.7);
            font-weight: 400;
            margin-top: 0.5rem;
            letter-spacing: 0.1em;
        }

        /* Language switcher */
        .language-switcher {
            text-align: center;
            margin-top: 1rem;
        }

        .language-switcher a {
            color: #6b7280;
            font-size: 0.75rem;
            margin: 0 0.25rem;
        }
    </style>
    <?php
}
add_action('login_enqueue_scripts', 'gameinfo_login_styles');

/**
 * Custom login logo URL
 */
function gameinfo_login_logo_url() {
    return home_url('/');
}
add_filter('login_headerurl', 'gameinfo_login_logo_url');

/**
 * Custom login logo title
 */
function gameinfo_login_logo_title() {
    return get_theme_mod('gameinfo_site_title', 'game_info');
}
add_filter('login_headertext', 'gameinfo_login_logo_title');

/**
 * Register meta fields for REST API
 */
function gameinfo_register_meta_for_rest() {
    register_post_meta('post', 'gameinfo_source', array(
        'show_in_rest' => true,
        'single' => true,
        'type' => 'string',
        'sanitize_callback' => 'sanitize_text_field',
        'auth_callback' => function() {
            return current_user_can('edit_posts');
        }
    ));

    register_post_meta('post', 'gameinfo_audio_url', array(
        'show_in_rest' => true,
        'single' => true,
        'type' => 'string',
        'sanitize_callback' => 'esc_url_raw',
        'auth_callback' => function() {
            return current_user_can('edit_posts');
        }
    ));
}
add_action('init', 'gameinfo_register_meta_for_rest');

/**
 * Category color mapping
 * Maps category/tag types to their colors
 */
function gameinfo_get_category_colors() {
    return array(
        'leak'     => '#f97316',  // Orange
        'critical' => '#ef4444',  // Red
        'success'  => '#4ade80',  // Green
        'indie'    => '#a78bfa',  // Purple
        'review'   => '#38bdf8',  // Light blue
        'trailer'  => '#fbbf24',  // Yellow
        'rumor'    => '#fb923c',  // Light orange
        'update'   => '#2dd4bf',  // Teal
        'news'     => '#13a4ec',  // Primary blue
        'info'     => '#6b7280',  // Gray
    );
}

/**
 * Get color for a specific type
 */
function gameinfo_get_type_color($type) {
    $colors = gameinfo_get_category_colors();
    return isset($colors[$type]) ? $colors[$type] : $colors['info'];
}

/**
 * Category name to type mapping (EN + CZ)
 * Maps category names to their type for color assignment
 */
function gameinfo_get_category_type_mapping() {
    return array(
        // English
        'leak'     => 'leak',
        'critical' => 'critical',
        'success'  => 'success',
        'indie'    => 'indie',
        'review'   => 'review',
        'trailer'  => 'trailer',
        'rumor'    => 'rumor',
        'rumour'   => 'rumor',
        'update'   => 'update',
        'news'     => 'news',
        'info'     => 'info',

        // Czech
        'únik'     => 'leak',
        'unik'     => 'leak',
        'kritické' => 'critical',
        'kriticke' => 'critical',
        'úspěch'   => 'success',
        'uspech'   => 'success',
        'recenze'  => 'review',
        'upoutávka'=> 'trailer',
        'upoutavka'=> 'trailer',
        'fáma'     => 'rumor',
        'fama'     => 'rumor',
        'drby'     => 'rumor',
        'aktualizace' => 'update',
        'zprávy'   => 'news',
        'zpravy'   => 'news',
        'novinky'  => 'news',
        'aktuality'=> 'news',
        'obecné'   => 'info',
        'obecne'   => 'info',
        'ostatní'  => 'info',
        'ostatni'  => 'info',
    );
}

/**
 * Get type from category name
 */
function gameinfo_get_type_from_name($name) {
    $name_lower = strtolower($name);
    $mapping = gameinfo_get_category_type_mapping();

    // Exact match first
    if (isset($mapping[$name_lower])) {
        return $mapping[$name_lower];
    }

    // Partial match
    foreach ($mapping as $keyword => $type) {
        if (strpos($name_lower, $keyword) !== false) {
            return $type;
        }
    }

    return 'info';
}

/**
 * Add color field to category REST API response
 */
function gameinfo_add_category_color_to_rest() {
    register_rest_field('category', 'color', array(
        'get_callback' => function($category) {
            // First check if category has custom color meta
            $custom_color = get_term_meta($category['id'], 'gameinfo_category_color', true);
            if (!empty($custom_color)) {
                return $custom_color;
            }

            // Otherwise, try to match by name (EN + CZ)
            $type = gameinfo_get_type_from_name($category['name']);
            return gameinfo_get_type_color($type);
        },
        'schema' => array(
            'description' => 'Category color in HEX format',
            'type'        => 'string',
        ),
    ));
}
add_action('rest_api_init', 'gameinfo_add_category_color_to_rest');

/**
 * Add category color meta field in admin
 */
function gameinfo_add_category_color_field($term) {
    $color = '';
    if (is_object($term)) {
        $color = get_term_meta($term->term_id, 'gameinfo_category_color', true);
    }
    ?>
    <tr class="form-field">
        <th scope="row"><label for="gameinfo_category_color"><?php _e('Category Color', 'gameinfo-terminal'); ?></label></th>
        <td>
            <input type="color" name="gameinfo_category_color" id="gameinfo_category_color" value="<?php echo esc_attr($color ? $color : '#6b7280'); ?>" />
            <p class="description"><?php _e('Select a color for this category (displayed in API and frontend).', 'gameinfo-terminal'); ?></p>
        </td>
    </tr>
    <?php
}
add_action('category_edit_form_fields', 'gameinfo_add_category_color_field');

/**
 * Add category color field on new category form
 */
function gameinfo_add_category_color_field_new($taxonomy) {
    ?>
    <div class="form-field">
        <label for="gameinfo_category_color"><?php _e('Category Color', 'gameinfo-terminal'); ?></label>
        <input type="color" name="gameinfo_category_color" id="gameinfo_category_color" value="#6b7280" />
        <p class="description"><?php _e('Select a color for this category.', 'gameinfo-terminal'); ?></p>
    </div>
    <?php
}
add_action('category_add_form_fields', 'gameinfo_add_category_color_field_new');

/**
 * Save category color meta
 */
function gameinfo_save_category_color($term_id) {
    if (isset($_POST['gameinfo_category_color'])) {
        update_term_meta($term_id, 'gameinfo_category_color', sanitize_hex_color($_POST['gameinfo_category_color']));
    }
}
add_action('created_category', 'gameinfo_save_category_color');
add_action('edited_category', 'gameinfo_save_category_color');

/**
 * Add status data (type + color) to posts REST API response
 */
function gameinfo_add_status_to_posts_rest() {
    register_rest_field('post', 'status_data', array(
        'get_callback' => function($post) {
            $data = gameinfo_get_post_status_data($post['id']);
            $data['color'] = gameinfo_get_type_color($data['type']);
            return $data;
        },
        'schema' => array(
            'description' => 'Post status data with label, type and color',
            'type'        => 'object',
            'properties'  => array(
                'label' => array('type' => 'string'),
                'type'  => array('type' => 'string'),
                'color' => array('type' => 'string'),
            ),
        ),
    ));
}
add_action('rest_api_init', 'gameinfo_add_status_to_posts_rest');

/**
 * Include subcategory posts in parent category archives
 *
 * When viewing a category archive, this includes posts from all child categories.
 * Example: "Technologie" shows posts from Technologie + Zprávy + Hardware
 */
function gameinfo_include_subcategory_posts($query) {
    // Only modify main query on category archives (frontend only)
    if (is_admin() || !$query->is_main_query() || !$query->is_category()) {
        return;
    }

    $category = $query->get_queried_object();

    if (!$category || !isset($category->term_id)) {
        return;
    }

    // Get all child category IDs
    $child_categories = get_term_children($category->term_id, 'category');

    if (!empty($child_categories) && !is_wp_error($child_categories)) {
        // Include parent + all children
        $all_categories = array_merge(array($category->term_id), $child_categories);

        // Set category__in to include all
        $query->set('category__in', $all_categories);

        // Remove the original cat parameter to avoid conflicts
        $query->set('cat', '');
    }
}
add_action('pre_get_posts', 'gameinfo_include_subcategory_posts');
