/**
 * ═══════════════════════════════════════════════════════════
 *  BESS Solutions — UI Scripts
 *  Archivo: src/js/ui.js
 *
 *  • Typewriter effect en headlines con clase .type-target
 *  • Scroll reveal (IntersectionObserver)
 *  • Nav background on scroll
 * ═══════════════════════════════════════════════════════════
 */

(function () {
    'use strict';

    /* ──────────────────────────────────────────────────────────
       TYPEWRITER CONFIG
       ────────────────────────────────────────────────────────── */
    const TW = {
        baseSpeed: 38,    // ms por carácter (menor = más rápido)
        variance: 22,    // variación aleatoria de velocidad (más natural)
        cursorChar: '|',   // carácter cursor
        cursorBlink: 500,   // ms periodo parpadeo
        pauseAfter: 800,   // ms pausa al terminar de escribir antes de ocultar cursor
    };

    /* ──────────────────────────────────────────────────────────
       Typewriter core
       target     : el elemento DOM a animar
       html       : el contenido HTML final a "escribir"
       onComplete : callback cuando termina
       ────────────────────────────────────────────────────────── */
    function typewrite(target, html, onComplete) {
        // Extraemos el texto plano del HTML para mantener tags intactos
        // (escribimos tag por tag, no caracter por caracter dentro de tags)

        // Convertimos el innerHTML en una lista de "tokens":
        // - strings de texto => se escriben carácter a carácter
        // - tags HTML => se insertan completos al instante
        const tokens = tokenizeHTML(html);
        let cursor = createCursor();

        target.innerHTML = '';
        target.appendChild(cursor);

        let tokenIdx = 0;
        let charIdx = 0;
        let rendered = ''; // HTML ya renderizado

        function step() {
            if (tokenIdx >= tokens.length) {
                // Terminó — blink cursor un momento y luego lo quita
                setTimeout(() => {
                    cursor.remove();
                    if (onComplete) onComplete();
                }, TW.pauseAfter);
                return;
            }

            const token = tokens[tokenIdx];

            if (token.type === 'tag') {
                // Tags se insertan completos de una vez
                rendered += token.value;
                tokenIdx++;
                charIdx = 0;
                target.innerHTML = rendered;
                target.appendChild(cursor);
                // pequeña pausa después de un tag (p.ej. <br>)
                setTimeout(step, 40);
            } else {
                // Texto — un carácter a la vez
                if (charIdx < token.value.length) {
                    rendered += token.value[charIdx];
                    charIdx++;
                    target.innerHTML = rendered;
                    target.appendChild(cursor);
                    const delay = TW.baseSpeed + Math.random() * TW.variance;
                    setTimeout(step, delay);
                } else {
                    tokenIdx++;
                    charIdx = 0;
                    step();
                }
            }
        }

        step();
    }

    /* Tokeniza HTML en [{type:'tag'|'text', value:string}] */
    function tokenizeHTML(html) {
        const tokens = [];
        const tagRe = /<[^>]+>/g;
        let last = 0;
        let m;
        while ((m = tagRe.exec(html)) !== null) {
            if (m.index > last) {
                // Texto antes del tag
                tokens.push({ type: 'text', value: html.slice(last, m.index) });
            }
            tokens.push({ type: 'tag', value: m[0] });
            last = m.index + m[0].length;
        }
        if (last < html.length) {
            tokens.push({ type: 'text', value: html.slice(last) });
        }
        return tokens;
    }

    /* Crea el elemento cursor parpadeante */
    function createCursor() {
        const c = document.createElement('span');
        c.className = 'tw-cursor';
        c.textContent = TW.cursorChar;
        return c;
    }

    /* ──────────────────────────────────────────────────────────
       Observar elementos .type-target:
       Cuando entran al viewport → arrancar el efecto
       ────────────────────────────────────────────────────────── */
    const typeTargets = document.querySelectorAll('.type-target');

    const typeObs = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                typeObs.unobserve(el);

                // Guardamos el HTML original antes de vaciarlo
                const originalHTML = el.getAttribute('data-type-html') || el.innerHTML;
                el.setAttribute('data-type-html', originalHTML);

                // Pequeña pausa antes de iniciar (sección acaba de entrar)
                const delay = parseInt(el.getAttribute('data-type-delay') || '0', 10);
                setTimeout(() => typewrite(el, originalHTML), delay);
            }
        });
    }, { threshold: 0.3 });

    typeTargets.forEach(el => {
        // Esconder el contenido inicial — el typewriter lo va a escribir
        const html = el.innerHTML;
        el.setAttribute('data-type-html', html);
        el.innerHTML = ''; // vaciar hasta que entre al viewport
        typeObs.observe(el);
    });

    /* ──────────────────────────────────────────────────────────
       Hero h1 — typewriter inmediato al cargar la página
       ────────────────────────────────────────────────────────── */
    const heroH1 = document.querySelector('.hero-h1.type-target');
    // (Se maneja por el observer de arriba ya que está en el viewport desde el inicio)

    /* ──────────────────────────────────────────────────────────
       Scroll Reveal para otros elementos .reveal
       ────────────────────────────────────────────────────────── */
    const revealEls = document.querySelectorAll('.reveal');

    const revealObs = new IntersectionObserver(entries => {
        entries.forEach((entry, i) => {
            if (entry.isIntersecting) {
                setTimeout(() => entry.target.classList.add('visible'), i * 60);
                revealObs.unobserve(entry.target);
            }
        });
    }, { threshold: 0.08 });

    revealEls.forEach(el => revealObs.observe(el));

    /* ──────────────────────────────────────────────────────────
       NASA Climate Counters — count-up on enter viewport
       ────────────────────────────────────────────────────────── */
    function countUp(el, target, decimals, duration, suffix, prefix) {
        const start = performance.now();
        const from = parseFloat(el.getAttribute('data-from') || '0');
        function frame(now) {
            const pct = Math.min((now - start) / duration, 1);
            const ease = 1 - Math.pow(1 - pct, 4); // easeOutQuart
            const val = from + (target - from) * ease;
            const unitSpan = el.querySelector('.cs-unit');
            const unitHTML = unitSpan ? unitSpan.outerHTML : '';
            el.innerHTML = (prefix || '') + (decimals ? val.toFixed(decimals) : Math.round(val)) + unitHTML;
            if (pct < 1) requestAnimationFrame(frame);
        }
        requestAnimationFrame(frame);
    }

    const climateStats = document.getElementById('cs-co2');
    if (climateStats) {
        const statsObs = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting) {
                statsObs.disconnect();
                const co2El = document.getElementById('cs-co2');
                if (co2El) { co2El.setAttribute('data-from', '315'); countUp(co2El, 427, 0, 2200, ' ppm'); }
                const tempEl = document.getElementById('cs-temp');
                if (tempEl) { tempEl.setAttribute('data-from', '0'); countUp(tempEl, 1.19, 2, 2400, ' °C', '+'); }
                const yearEl = document.getElementById('cs-year');
                if (yearEl) { yearEl.setAttribute('data-from', '2002'); countUp(yearEl, 2024, 0, 2800); }
                const bar = document.getElementById('co2-bar');
                if (bar) requestAnimationFrame(() => bar.classList.add('animated'));
            }
        }, { threshold: 0.3 });
        statsObs.observe(climateStats);
    }

    /* ──────────────────────────────────────────────────────────
       Nav — background on scroll
       ────────────────────────────────────────────────────────── */
    const nav = document.getElementById('nav');
    if (nav) {
        window.addEventListener('scroll', () => {
            nav.style.background = window.scrollY > 50
                ? 'rgba(0, 0, 0, 0.98)'
                : 'rgba(0, 0, 0, 0.85)';
        }, { passive: true });
    }

})();
