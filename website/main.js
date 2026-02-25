/* BESS Solutions — main.js v3 */

// ── ROTATING HERO PHRASES ──────────────────────────────────────
const phrases = [
    { line1: 'El cerebro de tu', line2: 'batería es', accent: 'open-source.' },
    { line1: 'Optimización de', line2: 'energía con', accent: 'IA en el edge.' },
    { line1: 'Más rentabilidad,', line2: 'menos pérdidas,', accent: 'más control.' },
    { line1: 'Cumple NTSyCS', line2: 'y IEC 62443', accent: 'desde el día 1.' },
    { line1: 'Arbitraje de precio', line2: 'autónomo,', accent: 'sin cloud.' },
    { line1: 'Construido para', line2: 'LatAm,', accent: 'abierto al mundo.' },
];
let phraseIdx = 0;
let typing = false;

function setPhrase(idx) {
    const h = document.getElementById('hero-phrase');
    if (!h) return;
    const p = phrases[idx];
    h.style.opacity = '0';
    h.style.transform = 'translateY(10px)';
    setTimeout(() => {
        h.innerHTML = `${p.line1}<br/>${p.line2} <span class="accent">${p.accent}</span>`;
        h.style.transition = 'opacity .6s ease, transform .6s ease';
        h.style.opacity = '1';
        h.style.transform = 'none';
    }, 350);
}

function rotatePhrases() {
    phraseIdx = (phraseIdx + 1) % phrases.length;
    setPhrase(phraseIdx);
}

// ── NAV ────────────────────────────────────────────────────────
const nav = document.getElementById('nav');
window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', scrollY > 20);
}, { passive: true });

// ── MOBILE MENU ────────────────────────────────────────────────
function toggleMenu() {
    const m = document.getElementById('mob-menu');
    const open = m.classList.toggle('open');
    document.body.style.overflow = open ? 'hidden' : '';
}
function closeMenu() {
    document.getElementById('mob-menu')?.classList.remove('open');
    document.body.style.overflow = '';
}
window.addEventListener('scroll', closeMenu, { passive: true });
window.toggleMenu = toggleMenu;
window.closeMenu = closeMenu;

// ── AUDIENCE TABS ──────────────────────────────────────────────
function setAudience(id) {
    document.querySelectorAll('.aud-btn').forEach(b => b.classList.toggle('active', b.dataset.aud === id));
    document.querySelectorAll('.aud-panel').forEach(p => p.classList.toggle('active', p.id === 'aud-' + id));
}
window.setAudience = setAudience;

// ── ANIMATED COUNTERS ──────────────────────────────────────────
function animateCounter(el) {
    const target = parseFloat(el.dataset.target);
    const decimals = el.dataset.dec ? parseInt(el.dataset.dec) : 0;
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

// ── LIVE METRICS (updates every 3s) ───────────────────────────
let liveBase = { savings: 14820, latency: 3.1, soc: 87.4, cycles: 18 };
function updateLive() {
    const el = {
        savings: document.getElementById('live-savings'),
        latency: document.getElementById('live-latency'),
        soc: document.getElementById('live-soc'),
        cycles: document.getElementById('live-cycles'),
    };
    liveBase.savings += Math.floor(Math.random() * 80 + 20);
    liveBase.latency = +(2.8 + Math.random() * 1.2).toFixed(1);
    liveBase.soc = +(82 + Math.random() * 12).toFixed(1);
    liveBase.cycles = 16 + Math.floor(Math.random() * 6);
    if (el.savings) el.savings.textContent = '$' + liveBase.savings.toLocaleString('es-CL');
    if (el.latency) el.latency.textContent = liveBase.latency + 'ms';
    if (el.soc) el.soc.textContent = liveBase.soc + '%';
    if (el.cycles) el.cycles.textContent = liveBase.cycles;
}

// ── TERMINAL ──────────────────────────────────────────────────
const termLines = [
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

function bootTerminal() {
    const tbody = document.getElementById('term-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    termLines.forEach(({ t, text, delay }) => {
        setTimeout(() => {
            const div = document.createElement('div');
            div.className = 't-l';
            if (t === 'cmd') {
                div.innerHTML = `<span class="t-p">$</span><span class="t-cmd">${text}</span>`;
            } else {
                div.innerHTML = `<span class="t-${t}">${text}</span>`;
            }
            tbody.appendChild(div);
            tbody.scrollTop = tbody.scrollHeight;
        }, delay);
    });
    setTimeout(() => {
        const c = document.createElement('div');
        c.className = 't-l';
        c.innerHTML = '<span class="t-p">$</span><span class="t-cursor"></span>';
        tbody.appendChild(c);
    }, 4400);
}

// ── REVEAL ────────────────────────────────────────────────────
const io = new IntersectionObserver(entries => {
    entries.forEach(e => {
        if (e.isIntersecting) {
            e.target.classList.add('vis');
            // trigger counters
            e.target.querySelectorAll('[data-target]').forEach(animateCounter);
            io.unobserve(e.target);
        }
    });
}, { threshold: 0.08 });

// ── BOOT ─────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
    // Init phrase
    setPhrase(0);
    setInterval(rotatePhrases, 3200);

    // Audience default
    setAudience('integrador');

    // Terminal
    bootTerminal();

    // Reveal observers
    document.querySelectorAll('.reveal,.reveal-l').forEach(el => io.observe(el));

    // Live metrics
    setInterval(updateLive, 3000);
    updateLive();

    // Counters in hero (immediate)
    document.querySelectorAll('.live-strip [data-target]').forEach(animateCounter);
});
