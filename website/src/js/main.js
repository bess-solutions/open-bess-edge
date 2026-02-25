/* BESSAI Website — main.js
 * Requires: I18N global (i18n.js)
 */

window.BESSAI = (() => {

    // ── ROTATING HERO PHRASES ──────────────────────────────
    let phraseIdx = 0;
    let phraseTimer = null;

    function startPhrases() {
        const phrases = I18N.get('hero.phrases');
        if (!phrases || !phrases.length) return;
        const l1El = document.getElementById('hero-l1');
        const l2El = document.getElementById('hero-l2');
        if (!l1El || !l2El) return;

        function show(i) {
            l1El.style.opacity = '0'; l2El.style.opacity = '0';
            setTimeout(() => {
                l1El.innerHTML = phrases[i].l1;
                l2El.innerHTML = phrases[i].l2;
                l1El.style.opacity = '1'; l2El.style.opacity = '1';
            }, 350);
        }

        show(phraseIdx);
        phraseTimer = setInterval(() => {
            phraseIdx = (phraseIdx + 1) % phrases.length;
            show(phraseIdx);
        }, 3200);
    }

    // ── AUDIENCE TABS ──────────────────────────────────────
    const AUDIENCE_KEYS = ['integrador', 'developer', 'investor', 'academia', 'regulator'];

    function buildAudienceTabs() {
        const tabs = document.getElementById('aud-tabs');
        const content = document.getElementById('aud-content');
        if (!tabs || !content) return;

        const labels = I18N.get('audiences.tabs') || [];
        const data = I18N.get('audiences.content') || {};

        // Build tab buttons
        tabs.innerHTML = labels.map((label, i) =>
            `<button class="aud-tab${i === 0 ? ' active' : ''}" data-idx="${i}">${label}</button>`
        ).join('');

        function renderPanel(idx) {
            const key = AUDIENCE_KEYS[idx];
            const d = data[key] || {};
            content.innerHTML = `
        <div class="aud-panel fade-in">
          <h3 class="aud-headline">${d.headline || ''}</h3>
          <p class="aud-body">${d.body || ''}</p>
          <ul class="aud-benefits">
            ${(d.benefits || []).map(b => `<li>${b}</li>`).join('')}
          </ul>
          <a href="#early-adopter" class="btn-secondary">${d.cta || ''}</a>
        </div>`;
        }

        renderPanel(0);
        tabs.addEventListener('click', e => {
            const btn = e.target.closest('[data-idx]');
            if (!btn) return;
            tabs.querySelectorAll('.aud-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderPanel(+btn.dataset.idx);
        });
    }

    // ── LIVE METRICS STRIP ────────────────────────────────
    function startLiveMetrics() {
        const defs = [
            { id: 'lm-savings', min: 12400, max: 14800, decimals: 0 },
            { id: 'lm-latency', min: 23, max: 48, decimals: 1 },
            { id: 'lm-soc', min: 72, max: 91, decimals: 1 },
            { id: 'lm-cycles', min: 3, max: 7, decimals: 0 },
        ];
        function rnd(mn, mx, d) { return (Math.random() * (mx - mn) + mn).toFixed(d); }
        function update() {
            defs.forEach(({ id, min, max, decimals }) => {
                const el = document.getElementById(id);
                if (el) el.textContent = rnd(min, max, decimals);
            });
        }
        update();
        setInterval(update, 3000);
    }

    // ── TERMINAL BOOT SEQUENCE ────────────────────────────
    function runTerminal() {
        const out = document.getElementById('term-output');
        if (!out) return;
        const lines = [
            { text: '$ bessai-edge start --config /etc/bessai/prod.yml', delay: 0, color: '#34d399' },
            { text: '[BOOT] Initializing BESSAI Edge v1.5.0 …', delay: 400, color: '#94a3b8' },
            { text: '[CONN] Modbus TCP   → 192.168.1.10:502 ✓', delay: 900, color: '#94a3b8' },
            { text: '[CONN] MQTT broker  → mqtt://edge:1883   ✓', delay: 1300, color: '#94a3b8' },
            { text: '[CONN] Prometheus   → :9090              ✓', delay: 1700, color: '#94a3b8' },
            { text: '[AI]  Loading DRL model (ONNX) …', delay: 2200, color: '#94a3b8' },
            { text: '[AI]  Model loaded  → inference 12 ms latency', delay: 2800, color: '#94a3b8' },
            { text: '[OPT] Price forecast:  CMg  $42.3/MWh  (MAPE 4.2%)', delay: 3400, color: '#fbbf24' },
            { text: '[OPT] Decision: CHARGE  → SoC 72% → 91%  +$847/day', delay: 4000, color: '#34d399' },
            { text: '[SEC] IEC 62443 SL-2 audit: PASS  ✓', delay: 4600, color: '#22d3ee' },
            { text: '● BESSAI Edge ready  │  Dashboard: http://edge:8080', delay: 5200, color: '#e2e8f0' },
        ];
        lines.forEach(({ text, delay, color }) => {
            setTimeout(() => {
                const line = document.createElement('div');
                line.className = 'term-line';
                line.style.color = color;
                line.textContent = text;
                out.appendChild(line);
                out.scrollTop = out.scrollHeight;
            }, delay);
        });
    }

    // ── SCROLL REVEAL + COUNTERS ──────────────────────────
    function initReveal() {
        const obs = new IntersectionObserver(entries => {
            entries.forEach(e => {
                if (e.isIntersecting) {
                    e.target.classList.add('revealed');
                    obs.unobserve(e.target);
                    const counter = e.target.querySelector('[data-count]');
                    if (counter) animateCount(counter);
                }
            });
        }, { threshold: 0.15 });
        document.querySelectorAll('.reveal').forEach(el => obs.observe(el));
    }

    function animateCount(el) {
        const raw = el.dataset.count;
        const isFloat = raw.includes('.');
        const target = parseFloat(raw);
        const duration = 1400;
        const start = performance.now();
        function step(now) {
            const p = Math.min((now - start) / duration, 1);
            const ease = 1 - Math.pow(1 - p, 3);
            const val = target * ease;
            el.textContent = isFloat ? val.toFixed(1) : Math.round(val).toLocaleString();
            if (p < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    }

    // ── NAV SCROLL BEHAVIOUR ─────────────────────────────
    function initNav() {
        const nav = document.getElementById('main-nav');
        if (!nav) return;
        window.addEventListener('scroll', () => {
            nav.classList.toggle('scrolled', window.scrollY > 60);
        }, { passive: true });

        // Hamburger
        const burger = document.getElementById('nav-burger');
        const menu = document.getElementById('nav-menu');
        if (burger && menu) {
            burger.addEventListener('click', () => {
                menu.classList.toggle('open');
                burger.classList.toggle('open');
            });
            menu.querySelectorAll('a').forEach(a => {
                a.addEventListener('click', () => {
                    menu.classList.remove('open');
                    burger.classList.remove('open');
                });
            });
        }
    }

    // ── MUSIC PLAYER ─────────────────────────────────────
    function initPlayer() {
        const audio = document.getElementById('bess-audio');
        const btn = document.getElementById('mp-btn');
        const bar = document.getElementById('mp-bar');
        const wrap = document.getElementById('mp-progress-wrap');
        const player = document.getElementById('music-player');
        if (!audio || !player) return;

        setTimeout(() => {
            player.style.transform = 'translateY(0)';
            player.style.opacity = '1';
        }, 2000);

        window.toggleMusic = () => {
            if (audio.paused) {
                audio.play();
                btn.textContent = '⏸';
            } else {
                audio.pause();
                btn.textContent = '▶';
            }
        };
        if (bar && wrap) {
            audio.addEventListener('timeupdate', () => {
                if (audio.duration) bar.style.width = (audio.currentTime / audio.duration * 100) + '%';
            });
            wrap.addEventListener('click', e => {
                const r = wrap.getBoundingClientRect();
                audio.currentTime = ((e.clientX - r.left) / r.width) * audio.duration;
            });
        }
        audio.addEventListener('ended', () => {
            btn.textContent = '▶';
            if (bar) bar.style.width = '0%';
        });
    }

    // ── REFRESH AFTER LANG SWITCH ─────────────────────────
    function refreshDynamic() {
        clearInterval(phraseTimer);
        startPhrases();
        buildAudienceTabs();
    }

    // ── INIT ──────────────────────────────────────────────
    function init() {
        initNav();
        startPhrases();
        buildAudienceTabs();
        startLiveMetrics();
        runTerminal();
        initReveal();
        initPlayer();
    }

    return { init, refreshDynamic };
})();

document.addEventListener('DOMContentLoaded', () => BESSAI.init());
