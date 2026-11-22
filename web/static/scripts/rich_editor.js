// RichEditor: a small WYSIWYG editor that reads and writes markdown.
// contenteditable + a toolbar (section heading, bold, italic, bullets, numbers);
// marked renders markdown -> HTML, turndown converts back. A "Text" toggle edits the
// raw markdown. Needs vendor/marked.min.js and vendor/turndown.js.
(function () {
    const turndown = new TurndownService({
        headingStyle: 'atx', bulletListMarker: '-', emDelimiter: '*', codeBlockStyle: 'fenced',
    });

    function toMarkdown(html) {
        return turndown.turndown(html || '')
            .replace(/^(\s*)-\s{2,}/gm, '$1- ')          // "-   item" -> "- item"
            .replace(/^(\s*)(\d+)\.\s{2,}/gm, '$1$2. ')  // "1.  step" -> "1. step"
            .replace(/\n{3,}/g, '\n\n')
            .trim();
    }

    function toHtml(md) {
        return marked.parse(md || '', { gfm: true, breaks: true });
    }

    const ICONS = {
        heading: '<b style="font-size:.95em">H</b>',
        bold: '<b>B</b>',
        italic: '<i style="font-family:Georgia,serif">I</i>',
        ul: '<svg viewBox="0 0 24 24" width="18" height="18"><path d="M9 6h11M9 12h11M9 18h11" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="4.5" cy="6" r="1.5" fill="currentColor"/><circle cx="4.5" cy="12" r="1.5" fill="currentColor"/><circle cx="4.5" cy="18" r="1.5" fill="currentColor"/></svg>',
        ol: '<svg viewBox="0 0 24 24" width="18" height="18"><path d="M10 6h10M10 12h10M10 18h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><text x="2" y="8.5" font-size="7" fill="currentColor" font-family="sans-serif">1</text><text x="2" y="14.5" font-size="7" fill="currentColor" font-family="sans-serif">2</text><text x="2" y="20.5" font-size="7" fill="currentColor" font-family="sans-serif">3</text></svg>',
    };
    const TITLES = { heading: 'Section heading', bold: 'Bold', italic: 'Italic', ul: 'Bulleted list', ol: 'Numbered list' };

    class RichEditor {
        constructor(host, { placeholder = '', onChange = () => {} } = {}) {
            this.onChange = onChange;
            this.textMode = false;
            host.classList.add('rich-editor');
            host.innerHTML = `
                <div class="rich-toolbar" role="toolbar">
                    ${Object.keys(ICONS).map(cmd => `<button type="button" class="rich-btn" data-cmd="${cmd}" title="${TITLES[cmd]}" aria-label="${TITLES[cmd]}">${ICONS[cmd]}</button>`).join('')}
                    <span class="rich-spacer"></span>
                    <button type="button" class="rich-btn rich-mode" title="Edit as markdown text">Text</button>
                </div>
                <div class="rich-area markdown-content" contenteditable="true" data-placeholder="${placeholder}"></div>
                <textarea class="rich-text form-control font-monospace" hidden></textarea>`;
            this.area = host.querySelector('.rich-area');
            this.text = host.querySelector('.rich-text');

            host.querySelector('.rich-toolbar').addEventListener('pointerdown', (e) => {
                if (e.target.closest('.rich-btn')) e.preventDefault();   // keep the text selection
            });
            host.querySelector('.rich-toolbar').addEventListener('click', (e) => {
                const btn = e.target.closest('.rich-btn');
                if (!btn) return;
                if (btn.classList.contains('rich-mode')) { this.toggleMode(btn); return; }
                if (!this.textMode) this.exec(btn.dataset.cmd);
            });
            this.area.addEventListener('input', () => this.changed());
            this.text.addEventListener('input', () => this.changed());
            // Paste as plain text: web pages bring styling that doesn't belong in a recipe.
            this.area.addEventListener('paste', (e) => {
                e.preventDefault();
                document.execCommand('insertText', false, (e.clipboardData || window.clipboardData).getData('text/plain'));
            });
        }

        exec(cmd) {
            this.area.focus();
            if (cmd === 'heading') {
                // A list item can't hold a heading: take the line out of its list first.
                if (document.queryCommandState('insertOrderedList')) document.execCommand('insertOrderedList');
                else if (document.queryCommandState('insertUnorderedList')) document.execCommand('insertUnorderedList');
                const block = document.queryCommandValue('formatBlock').toLowerCase();
                document.execCommand('formatBlock', false, block === 'h3' ? 'p' : 'h3');
            } else if (cmd === 'ul') {
                document.execCommand('insertUnorderedList');
            } else if (cmd === 'ol') {
                document.execCommand('insertOrderedList');
            } else {
                document.execCommand(cmd);
            }
            this.changed();
        }

        toggleMode(btn) {
            if (this.textMode) {
                this.area.innerHTML = toHtml(this.text.value);
            } else {
                this.text.value = toMarkdown(this.area.innerHTML);
                this.text.rows = Math.max(6, this.text.value.split('\n').length + 1);
            }
            this.textMode = !this.textMode;
            this.area.hidden = this.textMode;
            this.text.hidden = !this.textMode;
            btn.classList.toggle('on', this.textMode);
            btn.textContent = this.textMode ? 'Formatted' : 'Text';
            btn.closest('.rich-toolbar').querySelectorAll('[data-cmd]').forEach(b => { b.disabled = this.textMode; });
        }

        changed() {
            this.area.classList.toggle('is-empty', !this.area.textContent.trim() && !this.area.querySelector('li'));
            this.onChange();
        }

        getMarkdown() {
            return this.textMode ? this.text.value.trim() : toMarkdown(this.area.innerHTML);
        }

        setMarkdown(md) {
            this.area.innerHTML = toHtml(md);
            this.text.value = md || '';
            this.area.classList.toggle('is-empty', !(md || '').trim());
        }
    }

    window.RichEditor = RichEditor;
})();
