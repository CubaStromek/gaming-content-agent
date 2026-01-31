<?php
/**
 * Plugin Name: GameFo Polylang REST
 * Description: REST API endpoints for Polylang free — language assignment, translation linking, language-filtered categories, and status tags.
 * Version: 1.3.0
 * Author: GameFo
 *
 * Changelog:
 *  1.3.0 - GET /gamefo/v1/status-tags — vrací status tagy z theme (gameinfo_get_status_tags)
 *  1.2.0 - GET /gamefo/v1/categories?lang=cs|en — kategorie filtrované podle jazyka (pll_get_term_language)
 *  1.1.0 - Refaktor: sdílený gamefo_filter_terms_by_lang() helper
 *  1.0.0 - POST /gamefo/v1/link-translations, rest_after_insert_post lang assignment
 */

if (!defined('ABSPATH')) exit;

/**
 * After a post is created/updated via REST API, set its Polylang language
 * if a "lang" param was included in the request body.
 */
add_action('rest_after_insert_post', function ($post, $request) {
    if (!function_exists('pll_set_post_language')) return;

    $lang = $request->get_param('lang');
    if ($lang && in_array($lang, ['cs', 'en'], true)) {
        pll_set_post_language($post->ID, $lang);
    }
}, 10, 2);

/**
 * Custom REST endpoint: POST /gamefo/v1/link-translations
 * Body: { "cs": <post_id>, "en": <post_id> }
 */
add_action('rest_api_init', function () {
    register_rest_route('gamefo/v1', '/link-translations', [
        'methods'  => 'POST',
        'callback' => 'gamefo_link_translations',
        'permission_callback' => function () {
            return current_user_can('edit_posts');
        },
    ]);

    register_rest_route('gamefo/v1', '/categories', [
        'methods'  => 'GET',
        'callback' => 'gamefo_get_terms_by_lang',
        'permission_callback' => function () {
            return current_user_can('edit_posts');
        },
        'args' => [
            'lang' => [
                'required' => false,
                'type'     => 'string',
                'enum'     => ['cs', 'en'],
            ],
        ],
    ]);

    register_rest_route('gamefo/v1', '/status-tags', [
        'methods'  => 'GET',
        'callback' => 'gamefo_get_status_tags',
        'permission_callback' => function () {
            return current_user_can('edit_posts');
        },
    ]);
});

function gamefo_filter_terms_by_lang($taxonomy, $lang) {
    $args = [
        'taxonomy'   => $taxonomy,
        'hide_empty' => false,
        'number'     => 0,
    ];

    if ($lang && function_exists('pll_get_term_language')) {
        $all_terms = get_terms($args);
        if (is_wp_error($all_terms)) {
            return new WP_Error('term_error', $all_terms->get_error_message(), ['status' => 500]);
        }

        $filtered = [];
        foreach ($all_terms as $term) {
            $term_lang = pll_get_term_language($term->term_id, 'slug');
            if ($term_lang === $lang) {
                $filtered[] = $term;
            }
        }
        return $filtered;
    }

    $terms = get_terms($args);
    if (is_wp_error($terms)) {
        return new WP_Error('term_error', $terms->get_error_message(), ['status' => 500]);
    }
    return $terms;
}

function gamefo_get_terms_by_lang($request) {
    $lang = $request->get_param('lang');
    $terms = gamefo_filter_terms_by_lang('category', $lang);
    if (is_wp_error($terms)) return $terms;

    $result = [];
    foreach ($terms as $term) {
        $result[] = [
            'id'     => $term->term_id,
            'name'   => $term->name,
            'slug'   => $term->slug,
            'parent' => $term->parent,
            'count'  => $term->count,
        ];
    }
    return rest_ensure_response($result);
}

function gamefo_get_status_tags() {
    if (!function_exists('gameinfo_get_status_tags')) {
        return new WP_Error('no_theme_function', 'gameinfo_get_status_tags() not available', ['status' => 500]);
    }
    return rest_ensure_response(gameinfo_get_status_tags());
}

function gamefo_link_translations($request) {
    if (!function_exists('pll_save_post_translations')) {
        return new WP_Error('no_polylang', 'Polylang is not active', ['status' => 400]);
    }

    $cs_id = absint($request->get_param('cs'));
    $en_id = absint($request->get_param('en'));

    if (!$cs_id || !$en_id) {
        return new WP_Error('missing_ids', 'Both cs and en post IDs are required', ['status' => 400]);
    }

    // Verify posts exist
    if (!get_post($cs_id) || !get_post($en_id)) {
        return new WP_Error('invalid_posts', 'One or both posts not found', ['status' => 404]);
    }

    // Set languages (in case they weren't set during creation)
    pll_set_post_language($cs_id, 'cs');
    pll_set_post_language($en_id, 'en');

    // Link translations
    pll_save_post_translations([
        'cs' => $cs_id,
        'en' => $en_id,
    ]);

    return rest_ensure_response([
        'linked' => true,
        'cs'     => $cs_id,
        'en'     => $en_id,
    ]);
}
