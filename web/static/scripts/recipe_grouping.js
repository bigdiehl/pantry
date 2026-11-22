// Shared recipe grouping/rendering logic used by both the Recipes browse page
// (recipes_list.js) and the Recipe Editor page (editor.html), so "group by
// category/meal" behaves identically everywhere it appears.

const RECIPE_CATEGORY_ORDER = ['ENTREE', 'SALAD', 'SIDE', 'DESSERT', 'Other'];
const RECIPE_MEAL_ORDER = ['BREAKFAST', 'LUNCH', 'DINNER', 'Other'];

function recipeGroupTitleCase(str) {
    return str.replace(/\w\S*/g, txt => txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase());
}

/**
 * Fuzzy-finder style match: true if every character of `query` appears in
 * `text`, in order, allowing gaps (case-insensitive) - the same matching
 * style used by fzf/command palettes. An empty query matches everything.
 */
function fuzzyMatch(query, text) {
    if (!query) return true;
    if (!text) return false;
    query = query.toLowerCase();
    text = text.toLowerCase();

    let qi = 0;
    for (let ti = 0; ti < text.length && qi < query.length; ti++) {
        if (text[ti] === query[qi]) qi++;
    }
    return qi === query.length;
}

/**
 * True if `query` fuzzy-matches any of the given recipe fields (e.g. name, slug).
 */
function recipeMatchesSearch(recipe, query, fields) {
    if (!query) return true;
    return fields.some(field => fuzzyMatch(query, recipe[field] || ''));
}

/**
 * Group `recipes` by the given field ('category' or 'meal') in the standard
 * display order (with an "Other" bucket for anything unrecognized/missing),
 * and render each non-empty group into `$container`.
 *
 * @param {jQuery} $container - element to render groups into (cleared first)
 * @param {Array<Object>} recipes - recipe objects with a `category`/`meal` field
 * @param {'category'|'meal'} groupBy - which field to group by
 * @param {(recipe: Object) => (string|jQuery)} renderItem - builds the markup for one recipe
 * @param {string} [emptyMessage] - shown when there are no recipes at all
 */
function renderGroupedRecipes($container, recipes, groupBy, renderItem, emptyMessage) {
    $container.empty();

    if (!recipes || recipes.length === 0) {
        $container.append(`<div class="text-center p-3 text-muted">${emptyMessage || 'No recipes'}</div>`);
        return;
    }

    const order = groupBy === 'meal' ? RECIPE_MEAL_ORDER : RECIPE_CATEGORY_ORDER;
    const groups = {};
    recipes.forEach(recipe => {
        const raw = (recipe[groupBy] || '').toString();
        const key = order.includes(raw) ? raw : 'Other';
        (groups[key] = groups[key] || []).push(recipe);
    });

    order.forEach(groupName => {
        const items = groups[groupName];
        if (!items || items.length === 0) return;

        const $group = $(`
            <div class="recipe-group mb-3">
                <h5 class="text-muted">${recipeGroupTitleCase(groupName)}</h5>
                <div class="list-group"></div>
            </div>
        `);
        const $list = $group.find('.list-group');
        items.forEach(recipe => $list.append(renderItem(recipe)));
        $container.append($group);
    });
}
