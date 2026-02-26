/**
 * BESS Solutions — main.js v4
 * IEC 62443 SL-2 hardened build
 * © 2026 BESS Solutions SpA — Apache License 2.0
 * SPDX-License-Identifier: Apache-2.0
 */

'use strict';

(function () {

    // ── MATRIX DIGITAL RAIN ──────────────────────────────────────
    /**
     * Classic Matrix rain effect on hero canvas.
     * Characters: binary + numerals + katakana — industrial aesthetic.
     * Pauses via IntersectionObserver when hero scrolls off-screen (CPU friendly).
     */
    function initMatrixRain() {
        const canvas = document.getElementById('matrix-canvas');
        if (!canvas || !canvas.getContext) return;
        const ctx = canvas.getContext('2d');

        // Character pool — binary dominant for BESS/industrial feel, + katakana accent
        const CHARS = '01010110001011000110111001001011001001010110001011010110' +
            '0123456789' +
            'ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ';

        const FONT_SIZE = 14;          // px
        const SPEED_MIN = 1;           // column fall speed range
        const SPEED_MAX = 2.5;
        const GREEN_HEAD = '#edfff8';   // bright white-green: leading character
        const GREEN_MID = '#00ff41';   // classic Matrix lime green
        const GREEN_DIM = '#006b1c';   // dim trailing green
        const BG_FADE = 'rgba(7, 8, 16, 0.055)'; // hero bg colour with low alpha → trail fade

        let cols, drops, speeds;
        let animId = null;
        let running = false;

        function resize() {
            canvas.width = canvas.offsetWidth;
            canvas.height = canvas.offsetHeight;
            cols = Math.floor(canvas.width / FONT_SIZE);
            drops = new Array(cols).fill(1).map(() => Math.random() * -50);
            speeds = new Array(cols).fill(0).map(() => SPEED_MIN + Math.random() * (SPEED_MAX - SPEED_MIN));
        }

        function randomChar() {
            return CHARS[Math.floor(Math.random() * CHARS.length)];
        }

        function draw() {
            // Fade the previous frame (creates the trailing green glow)
            ctx.fillStyle = BG_FADE;
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            ctx.font = `bold ${FONT_SIZE}px 'JetBrains Mono', monospace`;

            for (let i = 0; i < cols; i++) {
                const y = drops[i] * FONT_SIZE;
                const x = i * FONT_SIZE;

                // Head character — bright flash
                ctx.fillStyle = GREEN_HEAD;
                ctx.shadowColor = GREEN_MID;
                ctx.shadowBlur = 8;
                ctx.fillText(randomChar(), x, y);

                // Mid character (1 step behind) — mid green
                ctx.fillStyle = GREEN_MID;
                ctx.shadowBlur = 4;
                ctx.fillText(randomChar(), x, y - FONT_SIZE);

                // Dim trail (2 steps behind)
                ctx.fillStyle = GREEN_DIM;
                ctx.shadowBlur = 0;
                ctx.fillText(randomChar(), x, y - FONT_SIZE * 2);

                // Advance column
                drops[i] += speeds[i];

                // Reset when off-screen (random stagger for organic feel)
                if (drops[i] * FONT_SIZE > canvas.height && Math.random() > 0.975) {
                    drops[i] = Math.random() * -20;
                }
            }

            animId = requestAnimationFrame(draw);
        }

        function start() {
            if (running) return;
            running = true;
            resize();
            draw();
        }

        function pause() {
            if (!running) return;
            running = false;
            if (animId) { cancelAnimationFrame(animId); animId = null; }
        }

        // Pause/resume based on hero viewport visibility (saves CPU)
        if ('IntersectionObserver' in window) {
            const heroObs = new IntersectionObserver(entries => {
                entries[0].isIntersecting ? start() : pause();
            }, { threshold: 0.01 });
            heroObs.observe(canvas.closest('section') || canvas.parentElement);
        } else {
            start();
        }

        // Redraw on window resize (debounced)
        let resizeTimer;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => { if (running) { pause(); start(); } }, 200);
        }, { passive: true });
    }


    const PHRASES = [
        { line1: 'El cerebro de tu', line2: 'batería es', accent: 'open-source.' },
        { line1: 'Optimización de', line2: 'energía con', accent: 'IA en el edge.' },
        { line1: 'Más rentabilidad,', line2: 'menos pérdidas,', accent: 'más control.' },
        { line1: 'Cumple NTSyCS', line2: 'y IEC 62443 SL-2', accent: 'desde el día 1.' },
        { line1: 'Arbitraje de precio', line2: 'autónomo,', accent: 'sin cloud.' },
        { line1: 'Construido para', line2: 'LatAm,', accent: 'abierto al mundo.' },
    ];
    let phraseIdx = 0;

    function setPhrase(idx) {
        const h = document.getElementById('hero-phrase');
        if (!h) return;
        const p = PHRASES[idx];
        h.style.opacity = '0';
        h.style.transform = 'translateY(10px)';
        setTimeout(() => {
            // Use textContent nodes + createElement to avoid innerHTML XSS pattern
            h.textContent = '';
            const line1Node = document.createTextNode(p.line1);
            const br = document.createElement('br');
            const line2Node = document.createTextNode(p.line2 + ' ');
            const accentSpan = document.createElement('span');
            accentSpan.className = 'accent';
            accentSpan.textContent = p.accent;
            h.appendChild(line1Node);
            h.appendChild(br);
            h.appendChild(line2Node);
            h.appendChild(accentSpan);
            h.style.transition = 'opacity .6s ease, transform .6s ease';
            h.style.opacity = '1';
            h.style.transform = 'none';
        }, 350);
    }

    function rotatePhrases() {
        phraseIdx = (phraseIdx + 1) % PHRASES.length;
        setPhrase(phraseIdx);
    }

    // ── NAV ─────────────────────────────────────────────────────
    function initNav() {
        const nav = document.getElementById('nav');
        if (!nav) return;
        window.addEventListener('scroll', () => {
            nav.classList.toggle('scrolled', window.scrollY > 20);
        }, { passive: true });
    }

    // ── MOBILE MENU ──────────────────────────────────────────────
    function toggleMenu() {
        const m = document.getElementById('mob-menu');
        if (!m) return;
        const burger = document.querySelector('.nav-burger');
        const isOpen = m.classList.toggle('open');
        document.body.style.overflow = isOpen ? 'hidden' : '';
        if (burger) burger.setAttribute('aria-expanded', String(isOpen));
    }

    function closeMenu() {
        const m = document.getElementById('mob-menu');
        const burger = document.querySelector('.nav-burger');
        if (m) m.classList.remove('open');
        document.body.style.overflow = '';
        if (burger) burger.setAttribute('aria-expanded', 'false');
    }

    function initMobileMenu() {
        const burger = document.querySelector('.nav-burger');
        if (burger) burger.addEventListener('click', toggleMenu);

        document.querySelectorAll('.mob-menu a').forEach(link => {
            link.addEventListener('click', closeMenu);
        });

        window.addEventListener('scroll', closeMenu, { passive: true });
    }

    // ── AUDIENCE TABS ────────────────────────────────────────────
    function setAudience(id) {
        document.querySelectorAll('.aud-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.aud === id);
            b.setAttribute('aria-selected', String(b.dataset.aud === id));
        });
        document.querySelectorAll('.aud-panel').forEach(p => {
            p.classList.toggle('active', p.id === 'aud-' + id);
        });
    }

    function initAudienceTabs() {
        document.querySelectorAll('.aud-btn').forEach(btn => {
            btn.addEventListener('click', () => setAudience(btn.dataset.aud));
        });
    }

    // ── ANIMATED COUNTERS ────────────────────────────────────────
    function animateCounter(el) {
        const target = parseFloat(el.dataset.target);
        if (isNaN(target)) return;
        const decimals = el.dataset.dec ? parseInt(el.dataset.dec, 10) : 0;
        const suffix = el.dataset.suffix || '';
        const prefix = el.dataset.prefix || '';
        const duration = 1800;
        const start = performance.now();
        function tick(now) {
            const t = Math.min((now - start) / duration, 1);
            const ease = 1 - Math.pow(1 - t, 3);
            const val = target * ease;
            el.textContent = prefix + val.toFixed(decimals) + suffix;
            if (t < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
    }

    // ── LIVE METRICS (updates every 3 s) ────────────────────────
    let liveBase = { savings: 14820, latency: 3.1, soc: 87.4, cycles: 18 };

    function updateLive() {
        const elSavings = document.getElementById('live-savings');
        const elLatency = document.getElementById('live-latency');
        const elSoc = document.getElementById('live-soc');
        const elCycles = document.getElementById('live-cycles');

        liveBase.savings += Math.floor(Math.random() * 80 + 20);
        liveBase.latency = +(2.8 + Math.random() * 1.2).toFixed(1);
        liveBase.soc = +(82 + Math.random() * 12).toFixed(1);
        liveBase.cycles = 16 + Math.floor(Math.random() * 6);

        if (elSavings) elSavings.textContent = '$' + liveBase.savings.toLocaleString('es-CL');
        if (elLatency) elLatency.textContent = liveBase.latency + 'ms';
        if (elSoc) elSoc.textContent = liveBase.soc + '%';
        if (elCycles) elCycles.textContent = liveBase.cycles;
    }

    // ── TERMINAL ─────────────────────────────────────────────────
    // NOTE: text values are STATIC constants — no user-supplied data.
    // Using textContent for all text nodes to enforce XSS-safe pattern.
    const TERM_LINES = [
        { t: 'cmd', text: 'bessai start --mode=optimize --site=atacama-1', delay: 0 },
        { t: 'info', text: '→ Loading config edge.toml…', delay: 500 },
        { t: 'ok', text: '✓ BMS · Huawei SUN2000 · Modbus RTU connected', delay: 950 },
        { t: 'ok', text: '✓ Grid API · Coordinador CEN · OK', delay: 1300 },
        { t: 'info', text: '→ Fetching CMg forecast 24h SEN…', delay: 1700 },
        { t: 'ok', text: '✓ Modelo ONNX · MAPE 4.2% · CMg: $142/MWh', delay: 2150 },
        { t: 'info', text: '→ MILP optimizer solving dispatch plan…', delay: 2550 },
        { t: 'ok', text: '✓ 18 ciclos optimizados · ahorro: $14.820 CLP', delay: 3000 },
        { t: 'warn', text: '⚡ Peak window 18:00–22:00 → discharge 92 kW', delay: 3400 },
        { t: 'ok', text: '✓ SoC 87.4% · Latency 3.1ms · WDG ❤ online', delay: 3850 },
    ];

    // Safe class whitelist — only these values are valid for t-{class}
    const SAFE_TERM_CLASSES = new Set(['cmd', 'ok', 'info', 'warn']);

    function buildTermLine(t, text) {
        const div = document.createElement('div');
        div.className = 't-l';
        if (t === 'cmd') {
            const prompt = document.createElement('span');
            prompt.className = 't-p';
            prompt.textContent = '$';
            const cmd = document.createElement('span');
            cmd.className = 't-cmd';
            cmd.textContent = text;            // textContent, NOT innerHTML
            div.appendChild(prompt);
            div.appendChild(cmd);
        } else {
            const span = document.createElement('span');
            // Enforce safe class: fallback to 't-info' if unknown type
            span.className = 't-' + (SAFE_TERM_CLASSES.has(t) ? t : 'info');
            span.textContent = text;           // textContent, NOT innerHTML
            div.appendChild(span);
        }
        return div;
    }

    function bootTerminal() {
        const tbody = document.getElementById('term-body');
        if (!tbody) return;
        tbody.innerHTML = '';
        TERM_LINES.forEach(({ t, text, delay }) => {
            setTimeout(() => {
                tbody.appendChild(buildTermLine(t, text));
                tbody.scrollTop = tbody.scrollHeight;
            }, delay);
        });
        // Blinking cursor
        setTimeout(() => {
            const c = document.createElement('div');
            c.className = 't-l';
            const prompt = document.createElement('span');
            prompt.className = 't-p';
            prompt.textContent = '$';
            const cursor = document.createElement('span');
            cursor.className = 't-cursor';
            c.appendChild(prompt);
            c.appendChild(cursor);
            tbody.appendChild(c);
        }, 4400);
    }

    // ── REVEAL (IntersectionObserver) ────────────────────────────
    function initReveal() {
        if (!('IntersectionObserver' in window)) {
            // Fallback: just make everything visible
            document.querySelectorAll('.reveal,.reveal-l').forEach(el => el.classList.add('vis'));
            return;
        }
        const io = new IntersectionObserver(entries => {
            entries.forEach(e => {
                if (e.isIntersecting) {
                    e.target.classList.add('vis');
                    e.target.querySelectorAll('[data-target]').forEach(animateCounter);
                    io.unobserve(e.target);
                }
            });
        }, { threshold: 0.08 });
        document.querySelectorAll('.reveal,.reveal-l').forEach(el => io.observe(el));
    }

    // ── MUSIC PLAYER ─────────────────────────────────────────────
    function initMusicPlayer() {
        const audio = document.getElementById('bess-audio');
        const btn = document.getElementById('mp-btn');
        const bar = document.getElementById('mp-bar');
        const wrap = document.getElementById('mp-progress-wrap');
        const player = document.getElementById('music-player');
        if (!audio || !btn || !bar || !wrap || !player) return;

        // Show player after 2 s
        setTimeout(() => {
            player.style.transform = 'translateY(0)';
            player.style.opacity = '1';
        }, 2000);

        btn.addEventListener('click', () => {
            if (audio.paused) {
                audio.play().catch(() => {/* autoplay blocked — user already interacted */ });
                btn.textContent = '⏸';
                btn.style.transform = 'scale(.92)';
                btn.setAttribute('aria-label', 'Pausar');
            } else {
                audio.pause();
                btn.textContent = '▶';
                btn.style.transform = '';
                btn.setAttribute('aria-label', 'Reproducir');
            }
        });

        // Close button
        const closeBtn = document.getElementById('mp-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                audio.pause();
                player.style.display = 'none';
            });
        }

        audio.addEventListener('timeupdate', () => {
            if (audio.duration) {
                bar.style.width = (audio.currentTime / audio.duration * 100) + '%';
            }
        });

        wrap.addEventListener('click', e => {
            if (!audio.duration) return;
            const r = wrap.getBoundingClientRect();
            const pct = (e.clientX - r.left) / r.width;
            audio.currentTime = Math.max(0, Math.min(1, pct)) * audio.duration;
        });

        audio.addEventListener('ended', () => {
            btn.textContent = '▶';
            btn.style.transform = '';
            bar.style.width = '0%';
            btn.setAttribute('aria-label', 'Reproducir');
        });
    }

    // ── BOOT ────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        initMatrixRain();   // ← Matrix digital rain hero background
        initNav();
        initMobileMenu();
        initAudienceTabs();
        initReveal();
        initMusicPlayer();

        setPhrase(0);
        setInterval(rotatePhrases, 3200);

        setAudience('integrador');
        bootTerminal();

        setInterval(updateLive, 3000);
        updateLive();

        // Counters in hero live-strip (if any have data-target)
        document.querySelectorAll('.live-strip [data-target]').forEach(animateCounter);
    });

})(); // end IIFE
