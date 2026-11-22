// RecipeForm: drives templates/_recipe_form.html (Edit recipes and import review).
//   const form = RecipeForm.mount(document.getElementById('recipeForm'), {onChange});
//   form.set(state); form.get();   // state = recipe form JSON (see docs/FRONTEND.md)
// Fields the form doesn't show (image_url, source, ...) are carried through untouched.
(function () {
    const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
    let foodsLoaded = false;

    function loadFoods() {
        if (foodsLoaded) return;
        foodsLoaded = true;
        fetch('/editor/foods').then(r => r.json()).then(d => {
            if (d.success) document.getElementById('knownFoodsList').innerHTML = d.foods.map(f => `<option value="${esc(f)}">`).join('');
        }).catch(() => { foodsLoaded = false; });
    }

    function mount(root, { onChange = () => {} } = {}) {
        let extra = {};          // passthrough fields
        let suppress = false;    // don't report changes while set() fills the form
        const undoStack = [];
        const history = [];      // [{instruction, note}] for the AI
        const changed = () => { if (!suppress) onChange(); };

        const editors = {};
        root.querySelectorAll('.rich-host').forEach(host => {
            editors[host.dataset.md] = new RichEditor(host, {
                placeholder: host.dataset.md === 'ingredients_md' ? '- 1 cup flour' : '1. Preheat the oven...',
                onChange: changed,
            });
        });
        const rows = root.querySelector('.ing-rows');

        function rowHtml(food, quantity) {
            return `<div class="ing-row">
                <input type="text" class="form-control ingredient-food" list="knownFoodsList" placeholder="Food" value="${esc(food)}">
                <input type="text" class="form-control ingredient-quantity" placeholder="Qty" value="${esc(quantity)}">
                <button type="button" class="icon-btn remove-ingredient-row" aria-label="Remove">&times;</button>
            </div>`;
        }

        root.querySelector('.add-ing').addEventListener('click', () => {
            rows.insertAdjacentHTML('beforeend', rowHtml('', ''));
            rows.lastElementChild.querySelector('.ingredient-food').focus();
            changed();
        });
        rows.addEventListener('click', (e) => {
            if (e.target.closest('.remove-ingredient-row')) {
                e.target.closest('.ing-row').remove();
                changed();
            }
        });
        root.addEventListener('input', (e) => { if (!e.target.closest('.rich-editor, .ai-assist')) changed(); });
        root.addEventListener('change', (e) => { if (!e.target.closest('.rich-editor, .ai-assist')) changed(); });

        function get() {
            const state = { ...extra };
            root.querySelectorAll('[data-field]').forEach(el => {
                state[el.dataset.field] = el.type === 'checkbox' ? el.checked : el.value;
            });
            state.ingredients = [...rows.querySelectorAll('.ing-row')].map(r => ({
                food: r.querySelector('.ingredient-food').value.trim(),
                quantity: r.querySelector('.ingredient-quantity').value.trim(),
            }));
            for (const [key, ed] of Object.entries(editors)) state[key] = ed.getMarkdown();
            return state;
        }

        function set(state) {
            suppress = true;
            extra = { ...state };
            root.querySelectorAll('[data-field]').forEach(el => {
                const v = state[el.dataset.field];
                delete extra[el.dataset.field];
                if (el.type === 'checkbox') el.checked = v === undefined ? true : !!v;
                else el.value = v ?? '';
            });
            ['ingredients', 'ingredients_md', 'instructions_md'].forEach(k => delete extra[k]);
            rows.innerHTML = (state.ingredients || []).map(i => rowHtml(i.food, i.quantity)).join('');
            for (const [key, ed] of Object.entries(editors)) ed.setMarkdown(state[key] || '');
            suppress = false;
            loadFoods();
        }

        // ---- Ask AI to change it ----
        const ai = root.querySelector('.ai-assist');
        const input = ai.querySelector('.ai-input');
        const sendBtn = ai.querySelector('.ai-send');
        const note = ai.querySelector('.ai-note');

        async function revise() {
            const instruction = input.value.trim();
            if (!instruction) return;
            sendBtn.disabled = true;
            sendBtn.textContent = 'Working...';
            try {
                const before = get();
                const res = await fetch('/recipe/revise', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ draft: before, instruction, history }),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
                undoStack.push(before);
                history.push({ instruction, note: data.note });
                set(data.draft);
                onChange();
                input.value = '';
                note.querySelector('.ai-note-text').textContent = data.note;
                note.querySelector('.ai-undo').hidden = false;
                note.hidden = false;
            } catch (err) {
                note.querySelector('.ai-note-text').textContent = 'Could not change it: ' + err.message;
                note.querySelector('.ai-undo').hidden = true;
                note.hidden = false;
            } finally {
                sendBtn.disabled = false;
                sendBtn.textContent = 'Change';
            }
        }

        sendBtn.addEventListener('click', revise);
        input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); revise(); } });
        ai.querySelector('.ai-undo').addEventListener('click', () => {
            const prev = undoStack.pop();
            if (!prev) return;
            history.pop();
            set(prev);
            onChange();
            note.querySelector('.ai-note-text').textContent = 'Undone.';
            note.querySelector('.ai-undo').hidden = undoStack.length === 0;
        });

        function reset() {
            undoStack.length = 0;
            history.length = 0;
            note.hidden = true;
            input.value = '';
        }

        return { get, set, reset };
    }

    window.RecipeForm = { mount };
})();
