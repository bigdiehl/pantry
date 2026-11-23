// Recipes page: browse (saved / pending / archived), read, select for the list, and edit.
// Detail panel has two modes: view (rendered recipe) and edit (shared recipe form).
// Mobile: list -> view sheet -> edit, each step a history entry so Back undoes it.
// Desktop: list beside the panel; entering edit is a history entry.
(function () {
    const data = {
        saved: JSON.parse(document.getElementById('recipesData').textContent),
        pending: JSON.parse(document.getElementById('pendingRecipesData').textContent),
        archived: JSON.parse(document.getElementById('archivedRecipesData').textContent),
    };
    const LABEL = { saved: 'Saved', pending: 'Pending', archived: 'Archived' };
    const CATEGORY_ORDER = ['ENTREE', 'SALAD', 'SIDE', 'DESSERT'];
    const MEAL_ORDER = ['BREAKFAST', 'LUNCH', 'DINNER'];
    const DESKTOP = window.matchMedia('(min-width: 992px)');
    const CHECK = '<svg viewBox="0 0 24 24" width="14" height="14"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>';

    const params = new URLSearchParams(location.search);
    const state = {
        status: LABEL[params.get('status')] ? params.get('status') : 'saved',
        groupBy: localStorage.getItem('recipesGroupBy') || 'category',
        query: '',
        current: null,      // {slug, status}
        mode: 'view',       // 'view' | 'edit'
        dirty: false,
        original: '',
    };

    const $ = (id) => document.getElementById(id);
    const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
    const title = (s) => (s || '').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
    const find = (slug, status) => data[status].find(r => r.slug === slug);

    function fuzzy(query, text) {
        if (!query) return true;
        text = (text || '').toLowerCase();
        let qi = 0;
        for (let i = 0; i < text.length && qi < query.length; i++) if (text[i] === query[qi]) qi++;
        return qi === query.length;
    }

    async function postJSON(url, body, method = 'POST') {
        const res = await fetch(url, {
            method, headers: body ? { 'Content-Type': 'application/json' } : {},
            body: body ? JSON.stringify(body) : undefined,
        });
        const out = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(out.error || `Request failed (${res.status})`);
        return out;
    }

    // ---- List ---------------------------------------------------------------

    const toggleLabel = (selected) => selected ? `${CHECK} On list` : '+ Add';

    function rowHtml(r, status) {
        const active = state.current && state.current.slug === r.slug && state.current.status === status;
        const meta = [title(r.category), title(r.meal)].filter(Boolean).join(' / ');
        const btn = status === 'saved'
            ? `<button class="pill-btn add-btn${r.selected ? ' on' : ''}" data-slug="${esc(r.slug)}">${toggleLabel(r.selected)}</button>` : '';
        return `<div class="recipe-row${active ? ' active' : ''}" data-slug="${esc(r.slug)}" data-status="${status}">
            <div class="recipe-row-text">
                <div class="recipe-row-name">${esc(r.name)}</div>
                ${meta ? `<div class="recipe-row-meta">${esc(meta)}</div>` : ''}
            </div>${btn}</div>`;
    }

    function render() {
        const q = state.query.toLowerCase();
        const order = state.groupBy === 'meal' ? MEAL_ORDER : CATEGORY_ORDER;
        const items = data[state.status].filter(r => fuzzy(q, r.name)).sort((a, b) => a.name.localeCompare(b.name));
        const groups = {};
        items.forEach(r => (groups[order.includes(r[state.groupBy]) ? r[state.groupBy] : 'OTHER'] ||= []).push(r));

        let html = '';
        [...order, 'OTHER'].forEach(key => {
            if (groups[key]) html += `<div class="section-label">${title(key)}</div><div class="panel">${groups[key].map(r => rowHtml(r, state.status)).join('')}</div>`;
        });
        if (!items.length) {
            const empty = q ? 'No matches.' : state.status === 'pending'
                ? 'No pending recipes. Imports you save for later show up here.' : 'Nothing here yet.';
            html = `<div class="panel mt-3"><div class="empty-note">${empty}</div></div>`;
        }
        $('recipeGroups').innerHTML = html;

        document.querySelectorAll('#statusToggle button').forEach(b => {
            const n = data[b.dataset.value].length;
            b.textContent = b.dataset.value !== 'saved' && n ? `${LABEL[b.dataset.value]} ${n}` : LABEL[b.dataset.value];
            b.classList.toggle('active', b.dataset.value === state.status);
        });
        document.querySelectorAll('#groupToggle button').forEach(b => b.classList.toggle('active', b.dataset.value === state.groupBy));
        const n = data.saved.filter(r => r.selected).length;
        $('selectedCount').textContent = n ? `${n} on list` : '';
    }

    // ---- Detail: view ---------------------------------------------------------

    function openSheet(push) {
        if (DESKTOP.matches) return;
        $('recipeDetail').classList.add('open');
        document.body.classList.add('sheet-open');
        if (push) history.pushState({ sheet: 'view' }, '');
    }

    function closeSheet() {
        $('recipeDetail').classList.remove('open');
        document.body.classList.remove('sheet-open');
    }

    function updateHeader() {
        const cur = state.current;
        const r = cur && find(cur.slug, cur.status);
        const editing = state.mode === 'edit';
        $('viewActions').hidden = !r || editing;
        $('editActions').hidden = !editing;
        $('detailMeta').textContent = r ? (editing ? 'Editing' : (cur.status === 'saved' ? '' : LABEL[cur.status])) : '';
        if (!r) return;
        const t = $('detailToggle');
        t.hidden = cur.status !== 'saved';
        t.classList.toggle('on', !!r.selected);
        t.innerHTML = toggleLabel(r.selected);
        $('moveBtn').closest('li').hidden = cur.status === 'archived';
        $('moveBtn').textContent = cur.status === 'pending' ? 'Move to Saved' : 'Move to Pending';
        $('archiveBtn').textContent = cur.status === 'archived' ? 'Restore to Saved' : 'Archive';
    }

    async function loadRecipe(slug, status, { push = true } = {}) {
        const r = find(slug, status);
        if (!r) return;
        if (state.mode === 'edit' && !leaveEdit()) return;
        state.current = { slug, status };
        localStorage.setItem('recipesLast', JSON.stringify(state.current));
        $('detailContent').innerHTML = '<p class="recipe-detail-placeholder">Loading...</p>';
        updateHeader();
        render();
        openSheet(push);

        try {
            // Saved recipes come from /markdown/recipe (warmed for offline); others from the editor API.
            const resp = status === 'saved'
                ? await fetch(`/markdown/recipe/${encodeURIComponent(r.name)}`)
                : await fetch(`/editor/recipe/${status}/${encodeURIComponent(slug)}`);
            if (!resp.ok && resp.status !== 404) throw new Error(resp.status);
            // 404 for a saved recipe = no recipe.md yet; show the "no instructions" note.
            const body = resp.ok ? await resp.json() : {};
            const html = status === 'saved' ? body.content : body.preview_html;
            if (state.current && state.current.slug === slug) {
                $('detailContent').innerHTML = html || '<p class="recipe-detail-placeholder">No instructions yet. Tap Edit to add them.</p>';
                $('detailContent').closest('.recipe-detail-body').scrollTop = 0;
                if (DESKTOP.matches) {
                    window.scrollTo({ top: 0 });
                    const row = document.querySelector('#recipeGroups .recipe-row.active');
                    if (row) row.scrollIntoView({ block: 'nearest' });
                }
            }
        } catch (err) {
            $('detailContent').innerHTML = '<p class="text-danger">Could not load this recipe (offline and not cached yet?).</p>';
        }
    }

    // ---- Detail: edit ---------------------------------------------------------

    const form = RecipeForm.mount(document.getElementById('recipeForm'), {
        onChange: () => setDirty(JSON.stringify(form.get()) !== state.original),
    });

    function setDirty(dirty) {
        state.dirty = dirty;
        $('saveBtn').disabled = !dirty;
        $('saveBtn').textContent = dirty ? 'Save' : 'Saved';
    }

    function showMode(mode) {
        state.mode = mode;
        $('detailContent').hidden = mode === 'edit';
        $('detailEdit').hidden = mode !== 'edit';
        // Desktop edit mode drops the panel's inner scroll box; the page scrolls instead.
        $('recipeDetail').classList.toggle('editing', mode === 'edit');
        updateHeader();
        $('detailContent').closest('.recipe-detail-body').scrollTop = 0;
        if (DESKTOP.matches) window.scrollTo({ top: 0 });
    }

    async function enterEdit({ push = true } = {}) {
        const cur = state.current;
        if (!cur) return;
        $('editBtn').disabled = true;
        try {
            const r = await (await fetch(`/editor/recipe/${cur.status}/${encodeURIComponent(cur.slug)}`)).json();
            if (!r.success) throw new Error(r.error || 'not found');
            form.reset();
            form.set({ ...r.metadata, ingredients_md: r.ingredients_md, instructions_md: r.instructions_md });
            const warn = $('yamlErrorWarning');
            warn.style.display = r.yaml_error ? '' : 'none';
            warn.textContent = r.yaml_error ? `Couldn't read recipe.yaml: ${r.yaml_error}. Saving rewrites it from this form.` : '';
            $('markdownSplitWarning').style.display = r.markdown_matched ? 'none' : '';
            updateImageUI(r.image_url, r.image_width);
            state.original = JSON.stringify(form.get());
            setDirty(false);
            showMode('edit');
            if (push) history.pushState({ sheet: 'edit' }, '');
        } catch (err) {
            alert(navigator.onLine ? 'Could not open the editor: ' + err.message : 'Editing needs a connection.');
        } finally {
            $('editBtn').disabled = false;
        }
    }

    // Returns false if the user wants to keep editing.
    function leaveEdit() {
        if (state.dirty && !confirm('You have unsaved changes. Discard them?')) return false;
        setDirty(false);
        showMode('view');
        return true;
    }

    async function save() {
        const cur = state.current;
        const draft = form.get();
        $('saveBtn').disabled = true;
        $('saveBtn').textContent = 'Saving...';
        try {
            const out = await postJSON(`/editor/recipe/${cur.status}/${encodeURIComponent(cur.slug)}`, draft);
            const r = find(cur.slug, cur.status);
            if (r) { r.name = draft.name.trim() || r.name; r.category = draft.category; r.meal = draft.meal; }
            $('detailContent').innerHTML = out.preview_html || '';
            setDirty(false);
            render();
            exitEdit();
        } catch (err) {
            alert('Could not save: ' + err.message);
            setDirty(true);
        }
    }

    function exitEdit() {
        if (history.state && history.state.sheet === 'edit') history.back();
        else leaveEdit();
    }

    // ---- Photo (edit mode) ----------------------------------------------------

    // The photo block lives inside the form, after the Servings line, like the rendered recipe.
    document.querySelector('#recipeForm .doc-photo-slot').appendChild($('photoBlock'));

    function setPhotoWidth(width) {
        $('photoBlock').style.setProperty('--photo-w', `${width || 400}px`);
    }

    function updateImageUI(url, width) {
        const has = !!url;
        $('recipeImagePreview').hidden = !has;
        $('recipeImageEmpty').hidden = has;
        $('photoControls').hidden = !has;
        $('photoBlock').classList.toggle('has-photo', has);
        if (has) {
            $('recipeImagePreview').src = url + '?t=' + Date.now();
            $('recipeImageWidth').value = width || 400;
            setPhotoWidth(width);
        }
        $('recipeImageActionBtn').dataset.has = has ? '1' : '';
    }

    const imageUrl = () => `/editor/recipe/${state.current.status}/${encodeURIComponent(state.current.slug)}/image`;

    $('recipeImageEmpty').addEventListener('click', () => $('recipeImageInput').click());
    $('recipeImageReplaceBtn').addEventListener('click', () => $('recipeImageInput').click());
    $('recipeImageWidth').addEventListener('input', (e) => setPhotoWidth(parseInt(e.target.value, 10)));

    $('recipeImageActionBtn').addEventListener('click', async () => {
        if (!confirm('Remove the photo from this recipe?')) return;
        try {
            const out = await postJSON(imageUrl(), null, 'DELETE');
            updateImageUI(null);
            $('detailContent').innerHTML = out.preview_html || $('detailContent').innerHTML;
        } catch (err) { alert('Could not remove the photo: ' + err.message); }
    });

    $('recipeImageInput').addEventListener('change', async (e) => {
        if (!e.target.files.length) return;
        const fd = new FormData();
        fd.append('image', e.target.files[0]);
        try {
            const res = await fetch(imageUrl(), { method: 'POST', body: fd });
            const out = await res.json();
            if (!res.ok) throw new Error(out.error);
            updateImageUI(out.url, out.image_width);
            $('detailContent').innerHTML = out.preview_html || $('detailContent').innerHTML;
        } catch (err) { alert('Could not upload the photo: ' + err.message); }
        e.target.value = '';
    });

    $('recipeImageWidth').addEventListener('change', async (e) => {
        const width = parseInt(e.target.value, 10);
        if (!width) return;
        try {
            const out = await postJSON(imageUrl() + '/width', { width });
            $('recipeImageWidth').value = out.width;
            $('detailContent').innerHTML = out.preview_html || $('detailContent').innerHTML;
        } catch (err) { alert('Could not resize the photo: ' + err.message); }
    });

    // ---- Selection, move, archive, delete ---------------------------------------

    async function toggleSelected(slug) {
        try {
            const d = await postJSON(`/recipes_list/toggle/${encodeURIComponent(slug)}`);
            const r = find(slug, 'saved');
            if (r) r.selected = d.selected;
            render();
            updateHeader();
        } catch (err) { alert('Could not update the shopping list (offline?).'); }
    }

    function reloadTo(status, slug) {
        const q = new URLSearchParams({ status });
        if (slug) q.set('recipe', slug);
        location.href = `/recipes_list?${q}`;
    }

    $('moveBtn').addEventListener('click', async () => {
        const { slug, status } = state.current;
        const toSaved = status === 'pending';
        if (!confirm(`Move this recipe to ${toSaved ? 'Saved' : 'Pending'}?`)) return;
        try {
            await postJSON(toSaved ? `/pending/promote/${slug}` : `/editor/demote/${slug}`);
            reloadTo(toSaved ? 'saved' : 'pending', slug);
        } catch (err) { alert('Could not move it: ' + err.message); }
    });

    $('archiveBtn').addEventListener('click', async () => {
        const { slug, status } = state.current;
        const restoring = status === 'archived';
        if (!confirm(restoring ? 'Restore this recipe to Saved?' : 'Archive this recipe? It leaves the rotation but is kept.')) return;
        try {
            await postJSON(restoring ? `/editor/unarchive/${slug}` : `/editor/archive/${slug}`);
            reloadTo(restoring ? 'saved' : 'archived', slug);
        } catch (err) { alert('Could not archive it: ' + err.message); }
    });

    $('deleteBtn').addEventListener('click', async () => {
        const { slug, status } = state.current;
        if (!confirm('Delete this recipe permanently? This cannot be undone.')) return;
        const url = status === 'pending' ? `/pending/discard/${slug}`
            : status === 'archived' ? `/editor/delete_archived/${slug}` : `/editor/delete/${slug}`;
        try {
            await postJSON(url);
            localStorage.removeItem('recipesLast');
            reloadTo(status);
        } catch (err) { alert('Could not delete it: ' + err.message); }
    });

    // ---- Events -------------------------------------------------------------------

    $('recipeGroups').addEventListener('click', (e) => {
        const add = e.target.closest('.add-btn');
        if (add) { toggleSelected(add.dataset.slug); return; }
        const row = e.target.closest('.recipe-row');
        if (row) loadRecipe(row.dataset.slug, row.dataset.status);
    });

    $('detailToggle').addEventListener('click', () => toggleSelected(state.current.slug));
    $('editBtn').addEventListener('click', () => enterEdit());
    $('saveBtn').addEventListener('click', save);
    $('cancelEditBtn').addEventListener('click', exitEdit);

    $('detailBack').addEventListener('click', () => {
        if (state.mode === 'edit') { exitEdit(); return; }
        if (history.state && history.state.sheet) history.back(); else closeSheet();
    });

    window.addEventListener('popstate', (e) => {
        const target = (e.state && e.state.sheet) || null;
        if (state.mode === 'edit' && target !== 'edit') {
            if (!leaveEdit()) { history.pushState({ sheet: 'edit' }, ''); return; }
        }
        if (!target) closeSheet();
    });

    window.addEventListener('beforeunload', (e) => { if (state.dirty) { e.preventDefault(); e.returnValue = ''; } });

    $('recipeSearch').addEventListener('input', (e) => { state.query = e.target.value.trim(); render(); });
    $('statusToggle').addEventListener('click', (e) => {
        const b = e.target.closest('button');
        if (b) { state.status = b.dataset.value; render(); }
    });
    $('groupToggle').addEventListener('click', (e) => {
        const b = e.target.closest('button');
        if (!b) return;
        state.groupBy = b.dataset.value;
        localStorage.setItem('recipesGroupBy', state.groupBy);
        render();
    });

    // ---- Init -----------------------------------------------------------------------

    render();

    // ?recipe=<slug or name>[&status=][&edit=1] (links from the list, chat, import) opens it.
    // Otherwise desktop restores the last one; mobile starts on the list.
    const linked = params.get('recipe');
    const linkedRecipe = linked && data[state.status].find(r => r.slug === linked || r.name === linked);
    if (linkedRecipe) {
        loadRecipe(linkedRecipe.slug, state.status, { push: false }).then(() => {
            if (params.get('edit')) enterEdit({ push: !DESKTOP.matches });
        });
    } else if (DESKTOP.matches) {
        try {
            const last = JSON.parse(localStorage.getItem('recipesLast'));
            if (last && find(last.slug, last.status)) {
                state.status = last.status;
                render();
                loadRecipe(last.slug, last.status, { push: false });
            }
        } catch (e) { /* ignore */ }
    }

    // Prefetch every saved recipe so the whole book is readable offline.
    if (navigator.serviceWorker && navigator.onLine) {
        navigator.serviceWorker.ready.then((reg) => {
            if (reg.active) reg.active.postMessage({
                type: 'WARM_CACHE',
                urls: data.saved.map(r => `/markdown/recipe/${encodeURIComponent(r.name)}`),
            });
        });
    }
})();
