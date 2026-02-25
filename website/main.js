/* ═══════════════════════════════════════════════════════════
   BESS Solutions — ORBITAL main.js
   Three.js multi-scene + IntersectionObserver + Chart.js + i18n
   ═══════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    // ── THREE.JS SETUP ──────────────────────────────────────
    const canvas = document.getElementById('universe');
    let W = innerWidth, H = innerHeight;
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(W, H);
    renderer.setClearColor(0x04050a, 1);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, W / H, .1, 200);
    camera.position.set(0, 0, 30);

    let mx = 0, my = 0;
    document.addEventListener('mousemove', e => { mx = e.clientX / W - .5; my = e.clientY / H - .5 });
    addEventListener('resize', () => {
        W = innerWidth; H = innerHeight;
        renderer.setSize(W, H); camera.aspect = W / H; camera.updateProjectionMatrix();
    });

    // ── SCENE 1: Earth sphere (Act I) ──
    const earthGeo = new THREE.BufferGeometry();
    const EC = 2400;
    const ePos = new Float32Array(EC * 3), eCol = new Float32Array(EC * 3);
    for (let i = 0; i < EC; i++) {
        const phi = Math.acos(-1 + 2 * Math.random());
        const theta = Math.random() * Math.PI * 2;
        const r = 11 + Math.random() * .7;
        ePos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        ePos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
        ePos[i * 3 + 2] = r * Math.cos(phi);
        const lat = Math.abs(ePos[i * 3 + 1]) / r;
        eCol[i * 3] = .75 + lat * .25;
        eCol[i * 3 + 1] = .22 + lat * .15;
        eCol[i * 3 + 2] = .04;
    }
    earthGeo.setAttribute('position', new THREE.BufferAttribute(ePos, 3));
    earthGeo.setAttribute('color', new THREE.BufferAttribute(eCol, 3));
    const earthMat = new THREE.PointsMaterial({ size: .16, vertexColors: true, transparent: true, opacity: .9 });
    const earthMesh = new THREE.Points(earthGeo, earthMat);
    scene.add(earthMesh);

    // Atmosphere ring
    const atmosGeo = new THREE.RingGeometry(11.5, 12.3, 64);
    const atmosMat = new THREE.MeshBasicMaterial({
        color: 0xff7043, transparent: true, opacity: .06, side: THREE.DoubleSide
    });
    const atmosMesh = new THREE.Mesh(atmosGeo, atmosMat);
    earthMesh.add(atmosMesh);

    // ── SCENE 2: Power grid (Act III) ──
    const gridGroup = new THREE.Group();
    const NG = 32;
    const gNodes = [];
    const gPos = new Float32Array(NG * 3), gCol = new Float32Array(NG * 3);
    for (let i = 0; i < NG; i++) {
        const x = (Math.random() - .5) * 36;
        const y = (Math.random() - .5) * 20;
        const z = (Math.random() - .5) * 5;
        gPos[i * 3] = x; gPos[i * 3 + 1] = y; gPos[i * 3 + 2] = z;
        gNodes.push([x, y, z]);
        gCol[i * 3] = .05; gCol[i * 3 + 1] = .82; gCol[i * 3 + 2] = 1;
    }
    const gGeo = new THREE.BufferGeometry();
    gGeo.setAttribute('position', new THREE.BufferAttribute(gPos, 3));
    gGeo.setAttribute('color', new THREE.BufferAttribute(gCol, 3));
    const gMat = new THREE.PointsMaterial({ size: .32, vertexColors: true, transparent: true, opacity: 0 });
    const gPoints = new THREE.Points(gGeo, gMat);
    gridGroup.add(gPoints);

    const lVerts = [];
    for (let i = 0; i < NG; i++)
        for (let j = i + 1; j < NG; j++) {
            const d = Math.hypot(gNodes[i][0] - gNodes[j][0], gNodes[i][1] - gNodes[j][1]);
            if (d < 12) lVerts.push(...gNodes[i], ...gNodes[j]);
        }
    const lGeo = new THREE.BufferGeometry();
    lGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(lVerts), 3));
    const lMat = new THREE.LineBasicMaterial({ color: 0x00d4ff, transparent: true, opacity: 0 });
    gridGroup.add(new THREE.LineSegments(lGeo, lMat));
    scene.add(gridGroup);

    // ── SCENE 3: Neural BESS (Act IV) ──
    const neuralGroup = new THREE.Group();
    const NN = 44;
    const nNodes = [];
    const nPos = new Float32Array(NN * 3), nCol = new Float32Array(NN * 3);
    const c3 = [[.05, .95, .55], [.0, .83, 1], [.25, .35, .95]];
    for (let i = 0; i < NN; i++) {
        const x = (Math.random() - .5) * 38;
        const y = (Math.random() - .5) * 22;
        const z = (Math.random() - .5) * 7;
        nPos[i * 3] = x; nPos[i * 3 + 1] = y; nPos[i * 3 + 2] = z;
        nNodes.push([x, y, z]);
        const c = c3[i % 3];
        nCol[i * 3] = c[0]; nCol[i * 3 + 1] = c[1]; nCol[i * 3 + 2] = c[2];
    }
    const nGeo = new THREE.BufferGeometry();
    nGeo.setAttribute('position', new THREE.BufferAttribute(nPos, 3));
    nGeo.setAttribute('color', new THREE.BufferAttribute(nCol, 3));
    const nMat = new THREE.PointsMaterial({ size: .28, vertexColors: true, transparent: true, opacity: 0 });
    neuralGroup.add(new THREE.Points(nGeo, nMat));

    const nLVerts = [];
    for (let i = 0; i < NN; i++)
        for (let j = i + 1; j < NN; j++) {
            const d = Math.hypot(nNodes[i][0] - nNodes[j][0], nNodes[i][1] - nNodes[j][1]);
            if (d < 10) nLVerts.push(...nNodes[i], ...nNodes[j]);
        }
    const nLGeo = new THREE.BufferGeometry();
    nLGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(nLVerts), 3));
    const nLMat = new THREE.LineBasicMaterial({ color: 0x00ff9d, transparent: true, opacity: 0 });
    neuralGroup.add(new THREE.LineSegments(nLGeo, nLMat));
    scene.add(neuralGroup);

    // ── SCENE SWITCHING ──
    let currentScene = 'earth';
    function switchScene(target) {
        if (target === currentScene) return;
        currentScene = target;
        const dur = 500, steps = dur / 16;
        let f = 0;
        const tick = () => {
            f++; const t = Math.min(f / steps, 1);
            const easeT = t * t * (3 - 2 * t); // smoothstep
            const eO = target === 'earth' ? easeT * .9 : (1 - easeT) * earthMat.opacity;
            const gO = target === 'grid' ? easeT * .85 : (1 - easeT) * gMat.opacity;
            const nO = target === 'neural' ? easeT * .85 : (1 - easeT) * nMat.opacity;
            earthMat.opacity = Math.max(0, eO);
            gMat.opacity = Math.max(0, gO); lMat.opacity = Math.max(0, gO * .35);
            nMat.opacity = Math.max(0, nO); nLMat.opacity = Math.max(0, nO * .3);
            if (t < 1) requestAnimationFrame(tick);
        };
        tick();
    }

    // ── ANIMATION LOOP ──
    let t = 0;
    (function animate() {
        requestAnimationFrame(animate);
        t += .006;
        earthMesh.rotation.y = t * .12;
        earthMesh.rotation.x = Math.sin(t * .08) * .04;
        gridGroup.rotation.y = Math.sin(t * .15) * .12;
        neuralGroup.rotation.y = t * .06;
        camera.position.x += (mx * 4 - camera.position.x) * .03;
        camera.position.y += (-my * 2 + 1.5 - camera.position.y) * .03;
        camera.lookAt(0, 0, 0);
        renderer.render(scene, camera);
    })();

    // ── INTERSECTION OBSERVERS ──
    // Scene switching
    const sceneMap = { act1: 'earth', act2: 'earth', act3: 'grid', act4: 'neural' };
    const sceneObs = new IntersectionObserver(entries => {
        entries.forEach(e => {
            if (e.isIntersecting) {
                const m = sceneMap[e.target.id];
                if (m) switchScene(m);
            }
        });
    }, { threshold: .25 });
    ['act1', 'act2', 'act3', 'act4'].forEach(id => {
        const el = document.getElementById(id);
        if (el) sceneObs.observe(el);
    });

    // Act text reveal
    const actObs = new IntersectionObserver(entries => {
        entries.forEach(e => {
            if (e.isIntersecting) {
                e.target.querySelectorAll('.act-line').forEach((el, i) => {
                    setTimeout(() => el.classList.add('in'), i * 100);
                });
                actObs.unobserve(e.target);
            }
        });
    }, { threshold: .12 });
    document.querySelectorAll('.act').forEach(el => actObs.observe(el));

    // Generic reveal
    const revObs = new IntersectionObserver(entries => {
        entries.forEach(e => {
            if (e.isIntersecting) { e.target.classList.add('in'); revObs.unobserve(e.target); }
        });
    }, { threshold: .08 });
    document.querySelectorAll('.reveal').forEach(el => revObs.observe(el));

    // ── COUNTER ANIMATION ──
    document.querySelectorAll('[data-count]').forEach(el => {
        const obs = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting) {
                const end = parseFloat(el.dataset.count);
                const suffix = el.dataset.suffix || '';
                const prefix = el.dataset.prefix || '';
                const dur = 2000;
                const start = performance.now();
                const step = (now) => {
                    const t = Math.min((now - start) / dur, 1);
                    const ease = 1 - Math.pow(1 - t, 3);
                    el.textContent = prefix + (end < 10 ? (end * ease).toFixed(1) : Math.round(end * ease)) + suffix;
                    if (t < 1) requestAnimationFrame(step);
                };
                requestAnimationFrame(step);
                obs.unobserve(el);
            }
        }, { threshold: .5 });
        obs.observe(el);
    });

    // ── CHART.JS LIVE DASHBOARD ──
    if (typeof Chart !== 'undefined') {
        const ctx = document.getElementById('chart-main');
        if (ctx) {
            const labels = Array.from({ length: 20 }, (_, i) => `${i + 1}`);
            let socData = Array.from({ length: 20 }, () => 65 + Math.random() * 20);
            let pwData = Array.from({ length: 20 }, () => -200 + Math.random() * 300);
            const chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels, datasets: [
                        { label: 'SoC (%)', data: [...socData], borderColor: '#00d4ff', backgroundColor: 'rgba(0,212,255,.06)', borderWidth: 1.8, fill: true, tension: .4, pointRadius: 0 },
                        { label: 'Power (kW/10)', data: pwData.map(v => v / 10), borderColor: '#fbbf24', backgroundColor: 'rgba(251,191,36,.03)', borderWidth: 1.4, fill: false, tension: .4, pointRadius: 0 }
                    ]
                },
                options: {
                    responsive: true, animation: { duration: 350 },
                    plugins: { legend: { labels: { color: '#4b5563', font: { size: 10, family: 'JetBrains Mono' } } } },
                    scales: {
                        x: { ticks: { color: '#4b5563', font: { size: 9 } }, grid: { color: 'rgba(255,255,255,.03)' } },
                        y: { ticks: { color: '#4b5563', font: { size: 9 } }, grid: { color: 'rgba(255,255,255,.03)' } }
                    }
                }
            });
            setInterval(() => {
                const soc = Math.max(20, Math.min(100, socData.at(-1) + (Math.random() - .45) * 4));
                const pw = Math.max(-500, Math.min(500, pwData.at(-1) + (Math.random() - .5) * 55));
                const cmg = 70 + Math.random() * 60;
                socData.shift(); socData.push(soc);
                pwData.shift(); pwData.push(pw);
                chart.data.datasets[0].data = [...socData];
                chart.data.datasets[1].data = pwData.map(v => v / 10);
                chart.update('none');
                const $id = id => document.getElementById(id);
                $id('kpi-soc').textContent = soc.toFixed(1) + '%';
                $id('kpi-soc-d').textContent = soc > 70 ? '\u2191 cargando' : '\u2193 descargando';
                $id('kpi-soc-d').className = 'kpi-delta ' + (soc > 70 ? 'up' : 'dn');
                $id('kpi-pw').textContent = (pw >= 0 ? '+' : '') + Math.round(pw) + ' kW';
                $id('kpi-pw-d').textContent = pw > 0 ? '\u2191 inyectando' : '\u2193 cargando';
                $id('kpi-pw-d').className = 'kpi-delta ' + (pw > 0 ? 'up' : 'dn');
                $id('kpi-cmg').textContent = '$' + Math.round(cmg);
                $id('kpi-lat').textContent = (2 + Math.random() * 3).toFixed(1) + 'ms';
            }, 2000);
        }
    }

    // ── NAV SCROLL ──
    addEventListener('scroll', () => {
        const nav = document.getElementById('nav');
        if (nav) nav.style.background = scrollY > 60 ? 'rgba(4,5,10,.97)' : 'rgba(4,5,10,.7)';
    });

})();

// ═══════════════════════════════════════════════════════════
// i18n ENGINE
// ═══════════════════════════════════════════════════════════
const T = {
    es: {
        'nav.1': 'Origen', 'nav.2': 'El Giro', 'nav.3': 'La Red', 'nav.4': 'BESSAI', 'nav.cta': 'Solicitar demo',
        'geo': 'Mientras algunos dan marcha atr\u00e1s, <strong>Am\u00e9rica Latina lidera</strong> la transici\u00f3n energ\u00e9tica con el mejor recurso solar y e\u00f3lico del mundo.',
        'a1.badge': '<span class="badge-dot badge-dot-i"></span>ACTO I \u00b7 Origen',
        'a1.h1': '424 partes<br>por mill\u00f3n.',
        'a1.h2': 'El CO\u2082 m\u00e1s alto<br>en <span style="color:var(--amber)">800.000 a\u00f1os.</span>',
        'a1.sub': 'Y en lugar de paralizarse, el mundo eligi\u00f3 <em>acelerar la transformaci\u00f3n energ\u00e9tica</em> m\u00e1s grande de la historia.',
        'a2.badge': '<span class="badge-dot badge-dot-ii"></span>ACTO II \u00b7 El Giro',
        'a2.h1': 'Mientras Washington<br>vuelve al carb\u00f3n\u2026',
        'a2.h2': 'Santiago construye<br><span style="color:var(--gold)">el futuro.</span>',
        'a2.sub': 'Chile tiene el <em>mejor recurso solar del planeta</em> (Atacama). Colombia el mejor e\u00f3lico de LatAm. Un continente entero eligiendo la transici\u00f3n limpia.',
        'a3.badge': '<span class="badge-dot badge-dot-iii"></span>ACTO III \u00b7 La Red',
        'a3.h1': '300 GW renovables<br>instalados en 2023.',
        'a3.h2': 'El desaf\u00edo ya no es generarla.<br><span style="color:var(--cyan)">Es gestionarla.</span>',
        'a3.sub': 'La solar es <em>10 veces m\u00e1s barata</em> que en 2010. Chile apunta a 60% renovable al 2030. El cuello de botella ahora es almacenamiento + inteligencia.',
        'a4.badge': '<span class="badge-dot badge-dot-iv"></span>ACTO IV \u00b7 La Soluci\u00f3n',
        'a4.h1': 'Las bater\u00edas son<br>el m\u00fasculo.',
        'a4.h2': 'BESSAI Edge,<br><span style="color:var(--green)">el cerebro.</span>',
        'a4.sub': 'Software open-source de grado industrial que convierte cualquier BESS en un nodo inteligente: optimiza, predice, protege. <em>Sin nube. En el borde.</em>',
    },
    en: {
        'nav.1': 'Origin', 'nav.2': 'The Shift', 'nav.3': 'The Grid', 'nav.4': 'BESSAI', 'nav.cta': 'Request demo',
        'geo': 'While some step back, <strong>Latin America leads</strong> the energy transition with the world\'s best solar & wind resources.',
        'a1.badge': '<span class="badge-dot badge-dot-i"></span>ACT I \u00b7 Origin',
        'a1.h1': '424 parts<br>per million.',
        'a1.h2': 'The highest CO\u2082<br>in <span style="color:var(--amber)">800,000 years.</span>',
        'a1.sub': 'Instead of freezing, the world chose to <em>accelerate the largest energy transformation</em> in history.',
        'a2.badge': '<span class="badge-dot badge-dot-ii"></span>ACT II \u00b7 The Shift',
        'a2.h1': 'While Washington<br>returns to coal\u2026',
        'a2.h2': 'Santiago builds<br><span style="color:var(--gold)">the future.</span>',
        'a2.sub': 'Chile has the <em>world\'s best solar resource</em> (Atacama). Colombia, the best wind in LatAm. An entire continent choosing the clean transition.',
        'a3.badge': '<span class="badge-dot badge-dot-iii"></span>ACT III \u00b7 The Grid',
        'a3.h1': '300 GW renewables<br>installed in 2023.',
        'a3.h2': 'The challenge is no longer generation.<br><span style="color:var(--cyan)">It\'s management.</span>',
        'a3.sub': 'Solar is <em>10 times cheaper</em> than in 2010. Chile aims for 60% renewable by 2030. The bottleneck is now storage + intelligence.',
        'a4.badge': '<span class="badge-dot badge-dot-iv"></span>ACT IV \u00b7 The Solution',
        'a4.h1': 'Batteries are<br>the muscle.',
        'a4.h2': 'BESSAI Edge,<br><span style="color:var(--green)">the brain.</span>',
        'a4.sub': 'Industrial-grade open-source software that turns any BESS into an intelligent grid node: optimizes, predicts, protects. <em>No cloud. At the edge.</em>',
    },
    pt: {
        'nav.1': 'Origem', 'nav.2': 'A Virada', 'nav.3': 'A Rede', 'nav.4': 'BESSAI', 'nav.cta': 'Solicitar demo',
        'geo': 'Enquanto alguns recuam, <strong>a Am\u00e9rica Latina lidera</strong> a transi\u00e7\u00e3o energ\u00e9tica com os melhores recursos solar e e\u00f3lico do mundo.',
        'a1.badge': '<span class="badge-dot badge-dot-i"></span>ATO I \u00b7 Origem',
        'a1.h1': '424 partes<br>por milh\u00e3o.',
        'a1.h2': 'O CO\u2082 mais alto<br>em <span style="color:var(--amber)">800.000 anos.</span>',
        'a1.sub': 'E em vez de paralisar, o mundo escolheu <em>acelerar a maior transforma\u00e7\u00e3o energ\u00e9tica</em> da hist\u00f3ria.',
        'a2.badge': '<span class="badge-dot badge-dot-ii"></span>ATO II \u00b7 A Virada',
        'a2.h1': 'Enquanto Washington<br>volta ao carv\u00e3o\u2026',
        'a2.h2': 'Santiago constr\u00f3i<br><span style="color:var(--gold)">o futuro.</span>',
        'a2.sub': 'O Chile tem o <em>melhor recurso solar do planeta</em> (Atacama). Col\u00f4mbia o melhor e\u00f3lico da LatAm. Um continente inteiro escolhendo a transi\u00e7\u00e3o limpa.',
        'a3.badge': '<span class="badge-dot badge-dot-iii"></span>ATO III \u00b7 A Rede',
        'a3.h1': '300 GW renov\u00e1veis<br>instalados em 2023.',
        'a3.h2': 'O desafio n\u00e3o \u00e9 mais gerar.<br><span style="color:var(--cyan)">\u00c9 gerenciar.</span>',
        'a3.sub': 'A solar \u00e9 <em>10 vezes mais barata</em> que em 2010. O Chile mira 60% renov\u00e1vel at\u00e9 2030. O gargalo agora \u00e9 armazenamento + intelig\u00eancia.',
        'a4.badge': '<span class="badge-dot badge-dot-iv"></span>ATO IV \u00b7 A Solu\u00e7\u00e3o',
        'a4.h1': 'As baterias s\u00e3o<br>o m\u00fasculo.',
        'a4.h2': 'BESSAI Edge,<br><span style="color:var(--green)">o c\u00e9rebro.</span>',
        'a4.sub': 'Software open-source de grau industrial que transforma qualquer BESS em n\u00f3 inteligente: otimiza, prev\u00ea, protege. <em>Sem cloud. No edge.</em>',
    }
};

function setLang(lang) {
    document.documentElement.lang = lang === 'pt' ? 'pt-BR' : lang;
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const v = T[lang] && T[lang][el.dataset.i18n];
        if (v !== undefined) el.innerHTML = v;
    });
    document.querySelectorAll('.lang-btn').forEach(b => {
        b.classList.toggle('active', b.textContent.trim().toLowerCase() === lang);
    });
    localStorage.setItem('bessai_lang', lang);
}

// Auto-detect on load
(function () {
    const saved = localStorage.getItem('bessai_lang');
    const br = (navigator.language || '').toLowerCase();
    const lang = saved || (br.startsWith('pt') ? 'pt' : br.startsWith('en') ? 'en' : 'es');
    if (lang !== 'es') setLang(lang);
})();
