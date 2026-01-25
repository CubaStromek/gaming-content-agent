<?php
/**
 * Template part for displaying category tabs navigation
 * Uses WordPress menu system with dropdown support
 *
 * @package GameInfo_Terminal
 */

$is_home_active = (is_home() || is_front_page()) && !is_category();
?>
<nav class="category-tabs">
    <a class="category-tab<?php echo $is_home_active ? ' active' : ''; ?>" href="<?php echo esc_url(home_url('/')); ?>">
        <span class="material-symbols-outlined">database</span> ALL_LOGS
    </a>
    <?php
    if (has_nav_menu('category')) {
        // Use dynamic WordPress menu with walker for dropdown support
        wp_nav_menu(array(
            'theme_location' => 'category',
            'container'      => false,
            'items_wrap'     => '%3$s',
            'walker'         => new GameInfo_Walker_Category_Tabs(),
        ));
    } else {
        // Fallback: show top-level categories (no dropdown support)
        $exclude_ids = array(1);
        $uncategorized = get_category_by_slug('uncategorized');
        if ($uncategorized) {
            $exclude_ids[] = $uncategorized->term_id;
        }

        $categories = get_categories(array(
            'number'     => 4,
            'hide_empty' => false,
            'orderby'    => 'name',
            'order'      => 'ASC',
            'exclude'    => $exclude_ids,
            'parent'     => 0, // Only top-level
        ));

        $icons = array('newspaper', 'rate_review', 'memory', 'sports_esports');
        $i = 0;

        foreach ($categories as $category) {
            $is_active = is_category($category->term_id) ? ' active' : '';
            $icon = isset($icons[$i]) ? $icons[$i] : 'folder';
            ?>
            <div class="category-tab-wrapper">
                <a class="category-tab<?php echo $is_active; ?>" href="<?php echo esc_url(get_category_link($category->term_id)); ?>">
                    <span class="material-symbols-outlined"><?php echo esc_html($icon); ?></span>
                    <?php echo esc_html(mb_strtoupper($category->name, 'UTF-8')); ?>
                </a>
            </div>
            <?php
            $i++;
        }
    }
    ?>
</nav>
