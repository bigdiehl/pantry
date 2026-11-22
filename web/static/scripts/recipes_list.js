// Recipes page: searchable, grouped list; tap a recipe to read it (full-screen
// sheet on mobile, side panel on desktop); add/remove it from the shopping list.
(function () {
    const saved = JSON.parse(document.getElementById('recipesData').textContent);
    const archived = JSON.parse(document.getElementById('archivedRecipesData').textContent);

    const CATEGORY_ORDER = ['ENTREE', 'SALAD', 'SIDE', 'DESSERT'];
    const MEAL_ORDER = ['BREAKFAST', 'LUNCH', 'DINNER'];
    const DESKTOP = window.matchMedia('(min-width: 992px)');
    const CHECK = '<svg viewBox="0 0 24 24" width="14" height="14"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>';

    const state = {
        status: 'saved',
        groupBy: localStorage.getItem('recipesGroupBy') || 'category',
        query: '',
        current: null,   // {slug, status}
    };

    const $ = (id) => document.getElementById(id);
    const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
    const title = (s) => (s || '').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());

    // fzf-style: all query characters appear in order
    function fuzzy(query, text) {
        if (!query) return true;
        text = (text || '').toLowerCase();
        let qi = 0;
        for (let i = 0; i < text.length && qi < query.length; i++) if (text[i] === query[qi]) qi++;
        return qi === query.length;
    }

    function toggleLabel(selected) {
        return selected ? `${CHECK} On list` : '+ Add';
    }

    function rowHtml(r, status) {
        const active = state.current && state.current.slug === r.slug && state.current.status === status;
        const meta = [title(r.category), title(r.meal)].filter(Boolean).join(' / ');
        const btn = status === 'saved'
            ? `<button class="pill-btn add-btn${r.selected ? ' on' : ''}" data-slug="${esc(r.slug)}">${toggleLabel(r.selected)}</button>`
            : '';
        return `
            <div class="recipe-row${active ? ' active' : ''}" data-slug="${esc(r.slug)}" data-status="${status}">
                <div class="recipe-row-text">
                    <div class="recipe-row-name">${esc(r.name)}</div>
                    ${meta ? `<div class="recipe-row-meta">${esc(meta)}</div>` : ''}
                </div>
                ${btn}
            </div>`;
    }

    function render() {
        const list = state.status === 'saved' ? saved : archived;
        const q = state.query.toLowerCase();
        const items = list.filter(r => fuzzy(q, r.name)).sort((a, b) => a.name.localeCompare(b.name));
        const order = state.groupBy === 'meal' ? MEAL_ORDER : CATEGORY_ORDER;

        const groups = {};
        items.forEach(r => {
            const key = order.includes(r[state.groupBy]) ? r[state.groupBy] : 'OTHER';
            (groups[key] ||= []).push(r);
        });

        let html = '';
        [...order, 'OTHER'].forEach(key => {
            if (!groups[key]) return;
            html += `<div class="section-label">${title(key)}</div>
                     <div class="panel">${groups[key].map(r => rowHtml(r, state.status)).join('')}</div>`;
        });
        if (!items.length) {
            html = `<div class="panel mt-3"><div class="empty-note">${q ? 'No matches.' : 'Nothing here yet.'}</div></div>`;
        }
        $('recipeGroups').innerHTML = html;

        const n = saved.filter(r => r.selected).length;
        $('selectedCount').textContent = n ? `${n} on list` : '';
    }

    function setSegment(el, value) {
        el.querySelectorAll('button').forEach(b => b.classList.toggle('active', b.dataset.value === value));
    }

    // ---- Detail view ------------------------------------------------------

    function openSheet(push) {
        if (DESKTOP.matches) return;
        $('recipeDetail').classList.add('open');
        document.body.classList.add('sheet-open');
        if (push) history.pushState({ sheet: true }, '');
    }

    function closeSheet() {
        $('recipeDetail').classList.remove('open');
        document.body.classList.remove('sheet-open');
    }

    function updateDetailToggle() {
        const btn = $('detailToggle');
        const r = state.current && state.current.status === 'saved' && saved.find(x => x.slug === state.current.slug);
        btn.hidden = !r;
        if (r) {
            btn.dataset.slug = r.slug;
            btn.classList.toggle('on', r.selected);
            btn.innerHTML = toggleLabel(r.selected);
        }
    }

    function loadRecipe(slug, status, { push = true } = {}) {
        const r = (status === 'saved' ? saved : archived).find(x => x.slug === slug);
        if (!r) return;
        state.current = { slug, status };
        localStorage.setItem('recipesLast', JSON.stringify(state.current));
        $('detailTitle').textContent = r.name;
        $('detailContent').innerHTML = '<p class="recipe-detail-placeholder">Loading...</p>';
        updateDetailToggle();
        render();
        openSheet(push);

        const req = status === 'archived'
            ? fetch(`/editor/recipe/archived/${encodeURIComponent(slug)}`).then(res => res.json()).then(d => d.preview_html || '')
            : fetch(`/markdown/recipe/${encodeURIComponent(r.name)}`).then(res => res.json()).then(d => d.content);

        req.then(html => {
            if (state.current && state.current.slug === slug) {
                $('detailContent').innerHTML = html || '<p class="recipe-detail-placeholder">This recipe has no instructions yet.</p>';
                $('detailContent').closest('.recipe-detail-body').scrollTop = 0;
            }
        }).catch(() => {
            $('detailContent').innerHTML = '<p class="text-danger">Could not load this recipe (offline and not cached yet?).</p>';
        });
    }

    // ---- Selection --------------------------------------------------------

    function toggleSelected(slug) {
        fetch(`/recipes_list/toggle/${encodeURIComponent(slug)}`, { method: 'POST' })
            .then(res => res.json())
            .then(d => {
                if (!d.success) throw new Error();
                const r = saved.find(x => x.slug === slug);
                if (r) r.selected = d.selected;
                render();
                updateDetailToggle();
            })
            .catch(() => alert('Could not update the shopping list (offline?).'));
    }

    // ---- Events -----------------------------------------------------------

    $('recipeGroups').addEventListener('click', (e) => {
        const add = e.target.closest('.add-btn');
        if (add) { toggleSelected(add.dataset.slug); return; }
        const row = e.target.closest('.recipe-row');
        if (row) loadRecipe(row.dataset.slug, row.dataset.status);
    });

    $('detailToggle').addEventListener('click', (e) => toggleSelected(e.currentTarget.dataset.slug));
    $('detailBack').addEventListener('click', () => history.state && history.state.sheet ? history.back() : closeSheet());
    window.addEventListener('popstate', closeSheet);

    $('recipeSearch').addEventListener('input', (e) => { state.query = e.target.value.trim(); render(); });

    $('statusToggle').addEventListener('click', (e) => {
        const b = e.target.closest('button');
        if (!b) return;
        state.status = b.dataset.value;
        setSegment($('statusToggle'), state.status);
        render();
    });

    $('groupToggle').addEventListener('click', (e) => {
        const b = e.target.closest('button');
        if (!b) return;
        state.groupBy = b.dataset.value;
        localStorage.setItem('recipesGroupBy', state.groupBy);
        setSegment($('groupToggle'), state.groupBy);
        render();
    });

    // ---- Init -------------------------------------------------------------

    setSegment($('groupToggle'), state.groupBy);
    render();

    // ?recipe=<name> (links from the shopping list and chat) always opens the recipe.
    // Otherwise restore the last one on desktop only, so mobile starts on the list.
    const linked = new URLSearchParams(location.search).get('recipe');
    const linkedRecipe = linked && saved.find(r => r.name === linked || r.slug === linked);
    if (linkedRecipe) {
        loadRecipe(linkedRecipe.slug, 'saved', { push: false });
    } else if (DESKTOP.matches) {
        try {
            const last = JSON.parse(localStorage.getItem('recipesLast'));
            if (last) {
                if (last.status === 'archived') { state.status = 'archived'; setSegment($('statusToggle'), 'archived'); }
                loadRecipe(last.slug, last.status, { push: false });
            }
        } catch (e) { /* ignore */ }
    }

    // Prefetch every saved recipe so the whole book is readable offline.
    if (navigator.serviceWorker && navigator.onLine) {
        navigator.serviceWorker.ready.then((reg) => {
            if (reg.active) reg.active.postMessage({
                type: 'WARM_CACHE',
                urls: saved.map(r => `/markdown/recipe/${encodeURIComponent(r.name)}`),
            });
        });
    }
})();
