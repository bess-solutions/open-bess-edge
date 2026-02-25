/* BESSAI Website — i18n Engine
 * Supports: ES, EN
 * Storage: localStorage('bessai_lang')
 * Usage:  data-i18n="key.nested" on any element
 *         data-i18n-html="key" to set innerHTML
 *         data-i18n-attr="placeholder:key" to set attrs
 */

const I18N = (() => {
    let _strings = {};
    let _lang = 'es';

    // Deep-get a key like "hero.cta_primary" from object
    function get(key) {
        return key.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : null), _strings);
    }

    // Apply all data-i18n translations to DOM
    function applyAll() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const val = get(el.dataset.i18n);
            if (val !== null) el.textContent = val;
        });
        document.querySelectorAll('[data-i18n-html]').forEach(el => {
            const val = get(el.dataset.i18nHtml);
            if (val !== null) el.innerHTML = val;
        });
        document.querySelectorAll('[data-i18n-attr]').forEach(el => {
            const [attr, key] = el.dataset.i18nAttr.split(':');
            const val = get(key);
            if (val !== null) el.setAttribute(attr, val);
        });
        // Update html lang attr
        document.documentElement.lang = _lang;
        // Update lang toggle buttons
        document.querySelectorAll('[data-lang-btn]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.langBtn === _lang);
        });
    }

    // Load strings object and apply
    function load(strings, lang) {
        _strings = strings;
        _lang = lang;
        applyAll();
    }

    // Switch language — fetches JSON from i18n/ folder
    async function switchTo(lang) {
        if (lang === _lang) return;
        try {
            const res = await fetch(`i18n/${lang}.json`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            load(data, lang);
            localStorage.setItem('bessai_lang', lang);
            // Re-run any dynamic rendering that depends on i18n
            if (window.BESSAI && window.BESSAI.refreshDynamic) window.BESSAI.refreshDynamic();
        } catch (e) {
            console.warn('[i18n] Failed to load', lang, e);
        }
    }

    // Init: detect lang from localStorage or browser
    async function init(inlineStrings) {
        const stored = localStorage.getItem('bessai_lang');
        const browser = navigator.language.slice(0, 2).toLowerCase();
        const preferred = stored || (['es', 'en'].includes(browser) ? browser : 'es');

        if (preferred === 'es' || !preferred) {
            // Use inline strings (already bundled) for default ES
            load(inlineStrings, 'es');
        } else {
            load(inlineStrings, 'es'); // paint immediately with default
            await switchTo(preferred);  // then fetch preferred
        }
    }

    return { init, switchTo, get, load };
})();
