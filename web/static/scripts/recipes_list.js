$(document).ready(function () {

    // Recipe data, injected server-side (see recipes_list.html)
    const recipes = JSON.parse(document.getElementById('recipesData').textContent);
    const archivedRecipes = JSON.parse(document.getElementById('archivedRecipesData').textContent);

    // Build the markup for one recipe row (shared list-group item look with
    // the editor page; see recipe_grouping.js for the grouping/search logic itself)
    function renderRecipeItem(recipe) {
        return $(`
            <div class="recipe-item d-flex align-items-center justify-content-between" data-recipename="${recipe.name}" data-status="saved" data-category="${recipe.category}" data-meal="${recipe.meal}">
                <span>${recipe.name}</span>
                <button
                    type="button"
                    class="btn ${recipe.selected ? 'btn-primary' : 'btn-success'} btn-sm add-recipe"
                    data-id="${recipe.slug}"
                    data-selected="${recipe.selected}"
                    data-bs-toggle="tooltip"
                    data-bs-placement="top"
                    title="Add this recipe">
                        ${recipe.selected ? '✔' : '+'}
                </button>
            </div>
        `);
    }

    // Archived recipes are out of rotation and can't be selected - just a
    // clickable row to view their content, no add-recipe button.
    function renderArchivedRecipeItem(recipe) {
        return $(`
            <div class="recipe-item d-flex align-items-center justify-content-between" data-recipename="${recipe.name}" data-slug="${recipe.slug}" data-status="archived" data-category="${recipe.category}" data-meal="${recipe.meal}">
                <span>${recipe.name}</span>
            </div>
        `);
    }

    // Re-render both group views from the current search query, then restore
    // active highlight and (re-)init tooltips on the freshly created buttons.
    function renderAll() {
        const query = $('#recipeSearch').val().toLowerCase().trim();
        const filtered = recipes.filter(r => recipeMatchesSearch(r, query, ['name']));
        const filteredArchived = archivedRecipes.filter(r => recipeMatchesSearch(r, query, ['name']));

        renderGroupedRecipes($('#categoryGroups'), filtered, 'category', renderRecipeItem, 'No matching recipes');
        renderGroupedRecipes($('#mealGroups'), filtered, 'meal', renderRecipeItem, 'No matching recipes');
        renderGroupedRecipes($('#archivedCategoryGroups'), filteredArchived, 'category', renderArchivedRecipeItem, 'No matching recipes');
        renderGroupedRecipes($('#archivedMealGroups'), filteredArchived, 'meal', renderArchivedRecipeItem, 'No matching recipes');

        const lastSelected = localStorage.getItem('lastSelectedRecipeOnList');
        const lastSelectedStatus = localStorage.getItem('lastSelectedRecipeStatusOnList') || 'saved';
        if (lastSelected) {
            $(`.recipe-item[data-recipename="${lastSelected}"][data-status="${lastSelectedStatus}"]`).addClass('active');
        }

        [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]')).forEach(function (el) {
            new bootstrap.Tooltip(el);
        });
    }

    renderAll();

    // Search recipes (fuzzy match on name)
    $('#recipeSearch').on('input', renderAll);

    // Handle grouping toggle
    $('input[name="groupBy"]').change(function () {
        const groupBy = $(this).val();
        if (groupBy === 'category') {
            $('#categoryGroups, #archivedCategoryGroups').show();
            $('#mealGroups, #archivedMealGroups').hide();
        } else if (groupBy === 'meal') {
            $('#categoryGroups, #archivedCategoryGroups').hide();
            $('#mealGroups, #archivedMealGroups').show();
        }
    });

    // Render markdown when a recipe row is clicked
    const contentDiv = document.getElementById('markdownContent');

    function loadRecipe(recipename, $item) {
        $('.recipe-item').removeClass('active');
        $item.addClass('active');

        const status = $item.data('status') || 'saved';
        const slug = $item.data('slug');

        // Save to localStorage
        localStorage.setItem('lastSelectedRecipeOnList', recipename);
        localStorage.setItem('lastSelectedRecipeStatusOnList', status);

        const request = status === 'archived'
            // Archived recipes aren't served by /markdown/recipe (saved-only), so
            // reuse the editor's preview endpoint, keyed by slug instead of name.
            ? fetch(`/editor/recipe/archived/${slug}`).then(res => res.json()).then(data => data.preview_html || '')
            : fetch(`/markdown/recipe/${recipename}`).then(res => res.json()).then(data => data.content);

        request
            .then(content => {
                contentDiv.innerHTML = content;
            })
            .catch(() => {
                contentDiv.innerHTML = '<p style="color:red;">Failed to load recipe.</p>';
            });
    }

    // Use event delegation since recipe items are in multiple groups
    $(document).on('click', '.recipe-item', function(e) {
        // Don't trigger when clicking the button
        if ($(e.target).closest('.add-recipe').length) {
            return;
        }

        const recipename = $(this).data('recipename');
        loadRecipe(recipename, $(this));
    });

    // Load last selected recipe on page load (without scrolling the page to it),
    // switching to the Archive tab first if that's where it lives. A
    // ?recipe=<name> query param (e.g. from the shopping list's ingredient
    // detail popup, linking to the saved recipe an ingredient came from)
    // takes priority over localStorage.
    const linkedRecipe = new URLSearchParams(window.location.search).get('recipe');
    const lastSelected = linkedRecipe || localStorage.getItem('lastSelectedRecipeOnList');
    const lastSelectedStatus = linkedRecipe ? 'saved' : (localStorage.getItem('lastSelectedRecipeStatusOnList') || 'saved');
    if (lastSelected) {
        const $item = $(`.recipe-item[data-recipename="${lastSelected}"][data-status="${lastSelectedStatus}"]`);
        if ($item.length) {
            if (lastSelectedStatus === 'archived') {
                $('#archived-tab').tab('show');
            }
            loadRecipe(lastSelected, $item);
        }
    }

    // Prefetch every saved recipe so the whole book is readable offline.
    if (navigator.serviceWorker && navigator.onLine) {
        navigator.serviceWorker.ready.then((reg) => {
            const urls = recipes.map(r => `/markdown/recipe/${r.name}`);
            reg.active.postMessage({ type: 'WARM_CACHE', urls });
        });
    }

    // Toggle selected state (use event delegation)
    $(document).on('click', '.add-recipe', function (e) {
        e.stopPropagation(); // Prevent triggering recipe-item click
        const button = $(this);
        const recipeSlug = button.data('id');

        $.post(`/recipes_list/toggle/${recipeSlug}`, function (data) {
            if (data.success) {
                const selected = data.selected;

                // Keep the underlying data in sync so a later re-render
                // (search, group-by toggle) reflects the new state.
                const recipe = recipes.find(r => r.slug === recipeSlug);
                if (recipe) recipe.selected = selected;

                // Recipe appears once in the category groups and once in the
                // meal groups, so update every matching button, not just the one clicked.
                const $buttons = $(`.add-recipe[data-id="${recipeSlug}"]`);
                $buttons.text(selected ? '✔' : '+');
                $buttons.toggleClass('btn-primary', selected);
                $buttons.toggleClass('btn-success', !selected);
                $buttons.data('selected', selected);
            } else {
                alert('Toggle failed.');
            }
        });
    });

});
