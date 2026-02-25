/* ═══════════════════════════════════════════════════════════
   BESS Solutions — ORBITAL main.js
   Three.js multi-scene + IntersectionObserver + Chart.js + i18n
   ═══════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    /* ── i18n Full Dictionary ─────────────────────────────── */
    const T = {
        es: {
            /* Nav */
            'nav.1': 'Origen', 'nav.2': 'El Giro', 'nav.3': 'La Red', 'nav.4': 'BESSAI',
            'nav.5': 'Stack', 'nav.6': 'Dashboard', 'nav.7': 'Roadmap', 'nav.8': 'Impacto',
            'nav.cta': 'Solicitar demo',
            /* Geo banner */
            'geo.tag': 'Contexto Global',
            'geo.text': 'Mientras algunos dan marcha atrás, <strong>América Latina lidera</strong> la transición energética con el mejor recurso solar y eólico del mundo.',
            /* Act I */
            'a1.badge': '<span class="badge-dot badge-dot-i"></span>ACTO I · Origen',
            'a1.h1': '424 partes<br>por millón.',
            'a1.h2': 'El CO₂ más alto<br>en <span style="color:var(--amber)">800.000 años.</span>',
            'a1.sub': 'Y en lugar de paralizarse, el mundo eligió <em>acelerar la transformación energética</em> más grande de la historia.',
            /* Act II */
            'a2.badge': '<span class="badge-dot badge-dot-ii"></span>ACTO II · El Giro',
            'a2.h1': 'Mientras Washington<br>vuelve al carbón…',
            'a2.h2': 'Santiago construye<br><span style="color:var(--gold)">el futuro.</span>',
            'a2.sub': 'Chile tiene el <em>mejor recurso solar del planeta</em> (Atacama). Colombia el mejor eólico de LatAm. Un continente entero eligiendo la transición limpia.',
            /* Act III */
            'a3.badge': '<span class="badge-dot badge-dot-iii"></span>ACTO III · La Red',
            'a3.h1': '300 GW renovables<br>instalados en 2023.',
            'a3.h2': 'El desafío ya no es generarla.<br><span style="color:var(--cyan)">Es gestionarla.</span>',
            'a3.sub': 'La solar es <em>10 veces más barata</em> que en 2010. Chile apunta a 60% renovable al 2030. El cuello de botella ahora es almacenamiento + inteligencia.',
            /* Act IV */
            'a4.badge': '<span class="badge-dot badge-dot-iv"></span>ACTO IV · La Solución',
            'a4.h1': 'Las baterías son<br>el músculo.',
            'a4.h2': 'BESSAI Edge,<br><span style="color:var(--green)">el cerebro.</span>',
            'a4.sub': 'Software open-source de grado industrial que convierte cualquier BESS en un nodo inteligente: optimiza, predice, protege. <em>Sin nube. En el borde.</em>',
            /* Feature cards */
            'f1.t': 'Optimización inteligente',
            'f1.d': 'Algoritmos avanzados de IA que aprenden del mercado eléctrico en tiempo real y calculan el despacho óptimo de carga y descarga en milisegundos.',
            'f2.t': 'Cualquier hardware',
            'f2.d': 'Arquitectura modular diseñada para adaptarse a cualquier fabricante de baterías e inversores. Plug and play industrial.',
            'f3.t': 'Ciberseguridad industrial',
            'f3.d': 'Diseñado bajo los estándares más exigentes de ciberseguridad para infraestructura energética crítica. Sin compromisos.',
            'f4.t': '100% Edge. Sin nube.',
            'f4.d': 'Todo corre localmente en el sitio. Cero dependencia de internet. Latencia mínima. Máxima autonomía y resiliencia operativa.',
            /* Act V */
            'a5.badge': '<span class="badge-dot" style="background:#a78bfa"></span>ACTO V · La Construcción',
            'a5.h1': 'Un trabajo de titanes.<br>Y ahora es <span style="color:var(--green)">de todos.</span>',
            'a5.sub': 'Más de un año de ingeniería. Miles de líneas de código. Modelos de lenguaje entrenados. Estándares industriales cumplidos. Todo liberado bajo licencia Apache 2.0. Porque la transición energética no puede depender de software privativo.',
            'a5.k1': 'Tiempo de desarrollo', 'a5.k2': 'Líneas de código', 'a5.k3': 'Tests automáticos', 'a5.k4': 'Modelos IA entrenados',
            'a5.stack': 'Stack tecnológico', 'a5.stackH': 'Lenguajes y frameworks',
            'a5.s2': 'Optimización', 'a5.s3': 'Protocolos', 'a5.s4': 'Seguridad',
            'a5.s5': 'Infraestructura', 'a5.s6': 'Telemetría', 'a5.s7': 'Licencia',
            'a5.ai': 'Inteligencia artificial', 'a5.aiH': 'Modelos y capacidades',
            'a5.m1': 'Predicción', 'a5.m1v': 'Costo marginal 24h',
            'a5.m2': 'Optimización', 'a5.m2v': 'Despacho óptimo MILP',
            'a5.m3': 'Adaptación', 'a5.m3v': 'DRL con datos SEN Chile',
            'a5.m4': 'Anomalías', 'a5.m4v': 'Detección en tiempo real',
            'a5.m5': 'Degradación', 'a5.m5v': 'Predicción de vida útil',
            'a5.m6': 'Latencia', 'a5.m6v': '<5ms inference local',
            'a5.m7': 'Training data', 'a5.m7v': '+2 años mercado LatAm',
            'a5.close': 'Este software fue diseñado, arquitecturado y construido desde cero con una premisa simple: <span style="color:var(--white)">que ningún equipo de ingeniería en Latinoamérica tenga que volver a construir esto.</span> El problema ya está resuelto. El código ya existe. Es open source. Úsenlo.',
            /* Impact */
            'imp.badge': '<span class="badge-dot" style="background:var(--gold)"></span>VISIÓN · Impacto',
            'imp.h1': 'Esto no es un proyecto.<br>Es una <span style="color:var(--gold)">misión medible.</span>',
            'imp.sub': 'Cada línea de código tiene un propósito. Cada modelo un objetivo. Y cada objetivo una métrica. Así mediremos nuestro éxito — y así rendiremos cuentas.',
            'imp.e.dim': 'Energía', 'imp.e.goal': 'Optimizar el despacho de al menos 50 MWh gestionados por BESSAI en los primeros 12 meses de operación real.',
            'imp.e.k1': 'Capacidad gestionada', 'imp.e.k2': 'Mejora eficiencia despacho', 'imp.e.prog': 'Año 1 meta · operación piloto',
            'imp.$.dim': 'Económico', 'imp.$.goal': 'Demostrar un ahorro operativo documentado de USD $200K+ anuales por operador, vía arbitraje y peak-shaving optimizado por IA.',
            'imp.$.k1': 'Ahorro anual/operador', 'imp.$.k2': 'Incremento revenue arbitraje', 'imp.$.prog': 'Validación en curso con early adopters',
            'imp.env.dim': 'Ambiental', 'imp.env.goal': 'Contribuir a evitar 10.000+ toneladas de CO₂ anuales al optimizar el uso de baterías e integrar renovables de forma inteligente.',
            'imp.env.k1': 'Ton CO₂ evitadas/año', 'imp.env.k2': 'Integración renovable', 'imp.env.prog': 'Metodología de medición en desarrollo',
            'imp.com.dim': 'Comunidad', 'imp.com.goal': 'Construir la comunidad open-source de referencia para BESS en Latinoamérica. 500+ ingenieros, 10+ universidades, 4+ países colaborando.',
            'imp.com.k1': 'Ingenieros en la comunidad', 'imp.com.k2': 'Presencia activa', 'imp.com.prog': 'Discord abierto · GitHub activo',
            'imp.tec.dim': 'Técnico', 'imp.tec.goal': 'Alcanzar 99.9% uptime en despliegues edge, latencia <5ms en inferencia local, y precisión >92% en predicción de costos marginales.',
            'imp.tec.k1': 'Uptime objetivo', 'imp.tec.k2': 'Latencia inferencia', 'imp.tec.prog': 'Benchmarks internos completados',
            'imp.pledge': 'Publicaremos un <strong>reporte de impacto trimestral</strong> con datos reales verificables. Sin marketing. Sin inflación. Métricas honestas de un proyecto que cree en la transparencia radical.',
            /* Dashboard */
            'dash.eye': 'Telemetría en tiempo real', 'dash.h2': 'Lo que ve el operador',
            'dash.sub': 'Simulación de la interfaz operativa de BESSAI Edge. Datos actualizados cada 2 segundos.',
            'dash.pw': 'Potencia Activa', 'dash.cmg': 'Costo Marginal', 'dash.lat': 'Latencia Edge',
            'dash.chart': 'SoC y Potencia · últimos 20 ciclos',
            'dash.status': 'Estado del sistema', 'dash.op': 'operativo ✓',
            'dash.opt': 'Optimizador', 'dash.act': 'activo ✓',
            'dash.bms': 'Enlace BMS', 'dash.conn': 'conectado ✓',
            'dash.sec': 'Seguridad', 'dash.cert': 'certificado ✓',
            'dash.latK': 'Latencia',
            'dash.socd.up': '↑ cargando', 'dash.socd.dn': '↓ descargando',
            'dash.pwd.up': '↑ inyectando', 'dash.pwd.dn': '↓ cargando',
            /* Roadmap */
            'rm.h2': 'Construcción abierta y transparente',
            'rm.p1t': 'Fase 1 · Fundación', 'rm.p1b': 'Conectividad industrial, motor de optimización base, seguridad certificada, arquitectura edge',
            'rm.p2t': 'Fase 2 · Inteligencia', 'rm.p2b': 'Stack de IA completo, predicción de costos marginales, telemetría en tiempo real, entrenamiento con datos SEN',
            'rm.p3t': 'Fase 3 · Flota', 'rm.p3b': 'Orquestación multi-sitio, respuesta a demanda, interoperabilidad, primeros early adopters en terreno',
            'rm.p4t': 'Fase 4 · Ecosistema', 'rm.p4b': 'Marketplace de soluciones, programa de certificación, expansión continental',
            /* Early Adopter */
            'ea.eye': 'Programa Early Adopter 2026',
            'ea.h2': 'Sea parte de los primeros.<br>Las condiciones no se repiten.',
            'ea.sub': 'Cupos limitados para proyectos BESS en Chile y Latinoamérica. A cambio: datos reales, feedback técnico, y co-autoría en publicaciones.',
            'ea.c1': 'Cupos Pioneer', 'ea.c2': 'Cupos Partner', 'ea.c3': 'Inicio despliegues', 'ea.c4': 'Países objetivo',
            'ea.p1price': 'Implementación <strong>sin costo</strong> · soporte técnico dedicado',
            'ea.p1b1': 'Licencia Apache 2.0 — sin royalties, para siempre',
            'ea.p1b2': 'Instalación asistida en sitio o remota',
            'ea.p1b3': 'Co-autoría en publicaciones técnicas',
            'ea.p1b4': 'Acceso anticipado a nuevas funcionalidades',
            'ea.p1b5': 'Integración prioritaria de nuevo hardware',
            'ea.p1b6': 'Reporte mensual de performance y ahorro estimado',
            'ea.p1b7': 'Canal directo con el equipo de ingeniería',
            'ea.p1req': 'Requisito: BESS de 100 kWh+ operativo o en comisionamiento 2026',
            'ea.p1btn': 'Aplicar al programa Pioneer →',
            'ea.p2price': 'Co-desarrollo · <strong>condiciones exclusivas</strong>',
            'ea.p2b1': 'Todo lo del tier Pioneer, más:',
            'ea.p2b2': 'Desarrollo conjunto de funcionalidades',
            'ea.p2b3': 'Marca propia sobre la plataforma (white-label)',
            'ea.p2b4': 'Exclusividad regional por país',
            'ea.p2b5': 'Representación conjunta ante reguladores energéticos',
            'ea.p2b6': 'Participación en la gobernanza del proyecto',
            'ea.p2b7': 'Términos preferenciales de largo plazo',
            'ea.p2req': 'Requisito: proyecto BESS >1 MWh o flota de +3 sitios',
            'ea.p2btn': 'Hablar con el equipo fundador →',
            /* Final CTA */
            'cta.h2': 'El software que la transición<br>energética necesitaba.',
            'cta.sub': 'Open source. Grado industrial. Construido en Latinoamérica, para Latinoamérica. No hace falta que nadie más lo construya. Ya existe.',
            'cta.gh': 'Ver en GitHub', 'cta.contact': 'Contactar al equipo',
            /* Footer */
            'foot.copy': '© 2026 BESS Solutions SpA · Santiago, Chile',
        },
        en: {
            /* Nav */
            'nav.1': 'Origin', 'nav.2': 'The Shift', 'nav.3': 'The Grid', 'nav.4': 'BESSAI',
            'nav.5': 'Stack', 'nav.6': 'Dashboard', 'nav.7': 'Roadmap', 'nav.8': 'Impact',
            'nav.cta': 'Request demo',
            /* Geo banner */
            'geo.tag': 'Global Context',
            'geo.text': 'While some step back, <strong>Latin America leads</strong> the energy transition with the world\'s best solar & wind resources.',
            /* Act I */
            'a1.badge': '<span class="badge-dot badge-dot-i"></span>ACT I · Origin',
            'a1.h1': '424 parts<br>per million.',
            'a1.h2': 'The highest CO₂<br>in <span style="color:var(--amber)">800,000 years.</span>',
            'a1.sub': 'Instead of freezing, the world chose to <em>accelerate the largest energy transformation</em> in history.',
            /* Act II */
            'a2.badge': '<span class="badge-dot badge-dot-ii"></span>ACT II · The Shift',
            'a2.h1': 'While Washington<br>goes back to coal…',
            'a2.h2': 'Santiago builds<br><span style="color:var(--gold)">the future.</span>',
            'a2.sub': 'Chile has the <em>best solar resource on the planet</em> (Atacama). Colombia the best wind in LatAm. An entire continent choosing the clean transition.',
            /* Act III */
            'a3.badge': '<span class="badge-dot badge-dot-iii"></span>ACT III · The Grid',
            'a3.h1': '300 GW renewables<br>installed in 2023.',
            'a3.h2': 'The challenge is no longer generation.<br><span style="color:var(--cyan)">It\'s management.</span>',
            'a3.sub': 'Solar is <em>10 times cheaper</em> than in 2010. Chile targets 60% renewable by 2030. The bottleneck is now storage + intelligence.',
            /* Act IV */
            'a4.badge': '<span class="badge-dot badge-dot-iv"></span>ACT IV · The Solution',
            'a4.h1': 'Batteries are<br>the muscle.',
            'a4.h2': 'BESSAI Edge,<br><span style="color:var(--green)">the brain.</span>',
            'a4.sub': 'Industrial-grade open-source software that turns any BESS into an intelligent node: optimizes, predicts, protects. <em>No cloud. On the edge.</em>',
            /* Feature cards */
            'f1.t': 'Intelligent optimization',
            'f1.d': 'Advanced AI algorithms that learn from the electricity market in real time and calculate optimal charge/discharge dispatch in milliseconds.',
            'f2.t': 'Any hardware',
            'f2.d': 'Modular architecture designed to adapt to any battery and inverter manufacturer. Industrial plug and play.',
            'f3.t': 'Industrial cybersecurity',
            'f3.d': 'Designed under the most demanding cybersecurity standards for critical energy infrastructure. No compromises.',
            'f4.t': '100% Edge. No cloud.',
            'f4.d': 'Everything runs locally on-site. Zero internet dependency. Minimum latency. Maximum autonomy and operational resilience.',
            /* Act V */
            'a5.badge': '<span class="badge-dot" style="background:#a78bfa"></span>ACT V · The Build',
            'a5.h1': 'A titan\'s work.<br>And now it belongs to <span style="color:var(--green)">everyone.</span>',
            'a5.sub': 'Over a year of engineering. Thousands of lines of code. Trained language models. Industrial standards met. All released under Apache 2.0 license. Because the energy transition cannot depend on proprietary software.',
            'a5.k1': 'Development time', 'a5.k2': 'Lines of code', 'a5.k3': 'Automated tests', 'a5.k4': 'Trained AI models',
            'a5.stack': 'Technology stack', 'a5.stackH': 'Languages & frameworks',
            'a5.s2': 'Optimization', 'a5.s3': 'Protocols', 'a5.s4': 'Security',
            'a5.s5': 'Infrastructure', 'a5.s6': 'Telemetry', 'a5.s7': 'License',
            'a5.ai': 'Artificial intelligence', 'a5.aiH': 'Models & capabilities',
            'a5.m1': 'Prediction', 'a5.m1v': 'Marginal cost 24h',
            'a5.m2': 'Optimization', 'a5.m2v': 'MILP optimal dispatch',
            'a5.m3': 'Adaptation', 'a5.m3v': 'DRL with Chile SEN data',
            'a5.m4': 'Anomalies', 'a5.m4v': 'Real-time detection',
            'a5.m5': 'Degradation', 'a5.m5v': 'Lifespan prediction',
            'a5.m6': 'Latency', 'a5.m6v': '<5ms local inference',
            'a5.m7': 'Training data', 'a5.m7v': '+2 years LatAm market',
            'a5.close': 'This software was designed, architected, and built from scratch with one simple premise: <span style="color:var(--white)">no engineering team in Latin America should ever have to build this again.</span> The problem is solved. The code exists. It\'s open source. Use it.',
            /* Impact */
            'imp.badge': '<span class="badge-dot" style="background:var(--gold)"></span>VISION · Impact',
            'imp.h1': 'This is not a project.<br>It\'s a <span style="color:var(--gold)">measurable mission.</span>',
            'imp.sub': 'Every line of code has a purpose. Every model an objective. And every objective a metric. This is how we\'ll measure our success — and how we\'ll be held accountable.',
            'imp.e.dim': 'Energy', 'imp.e.goal': 'Optimize the dispatch of at least 50 MWh managed by BESSAI in the first 12 months of real operation.',
            'imp.e.k1': 'Managed capacity', 'imp.e.k2': 'Dispatch efficiency improvement', 'imp.e.prog': 'Year 1 target · pilot operation',
            'imp.$.dim': 'Economic', 'imp.$.goal': 'Demonstrate documented operational savings of USD $200K+ per operator per year, via AI-optimized arbitrage and peak-shaving.',
            'imp.$.k1': 'Annual savings/operator', 'imp.$.k2': 'Arbitrage revenue increase', 'imp.$.prog': 'Validation underway with early adopters',
            'imp.env.dim': 'Environmental', 'imp.env.goal': 'Contribute to avoiding 10,000+ tons of CO₂ annually by optimizing battery usage and intelligently integrating renewables.',
            'imp.env.k1': 'Tons CO₂ avoided/year', 'imp.env.k2': 'Renewable integration', 'imp.env.prog': 'Measurement methodology in development',
            'imp.com.dim': 'Community', 'imp.com.goal': 'Build the reference open-source community for BESS in Latin America. 500+ engineers, 10+ universities, 4+ countries collaborating.',
            'imp.com.k1': 'Engineers in the community', 'imp.com.k2': 'Active presence', 'imp.com.prog': 'Discord open · GitHub active',
            'imp.tec.dim': 'Technical', 'imp.tec.goal': 'Achieve 99.9% uptime in edge deployments, <5ms local inference latency, and >92% accuracy in marginal cost prediction.',
            'imp.tec.k1': 'Target uptime', 'imp.tec.k2': 'Inference latency', 'imp.tec.prog': 'Internal benchmarks completed',
            'imp.pledge': 'We will publish a <strong>quarterly impact report</strong> with verifiable real data. No marketing. No inflation. Honest metrics from a project that believes in radical transparency.',
            /* Dashboard */
            'dash.eye': 'Real-time telemetry', 'dash.h2': 'What the operator sees',
            'dash.sub': 'Simulation of the BESSAI Edge operational interface. Data updated every 2 seconds.',
            'dash.pw': 'Active Power', 'dash.cmg': 'Marginal Cost', 'dash.lat': 'Edge Latency',
            'dash.chart': 'SoC & Power · last 20 cycles',
            'dash.status': 'System status', 'dash.op': 'operational ✓',
            'dash.opt': 'Optimizer', 'dash.act': 'active ✓',
            'dash.bms': 'BMS Link', 'dash.conn': 'connected ✓',
            'dash.sec': 'Security', 'dash.cert': 'certified ✓',
            'dash.latK': 'Latency',
            'dash.socd.up': '↑ charging', 'dash.socd.dn': '↓ discharging',
            'dash.pwd.up': '↑ injecting', 'dash.pwd.dn': '↓ charging',
            /* Roadmap */
            'rm.h2': 'Open & transparent development',
            'rm.p1t': 'Phase 1 · Foundation', 'rm.p1b': 'Industrial connectivity, base optimization engine, certified security, edge architecture',
            'rm.p2t': 'Phase 2 · Intelligence', 'rm.p2b': 'Complete AI stack, marginal cost prediction, real-time telemetry, SEN data training',
            'rm.p3t': 'Phase 3 · Fleet', 'rm.p3b': 'Multi-site orchestration, demand response, interoperability, first early adopters in the field',
            'rm.p4t': 'Phase 4 · Ecosystem', 'rm.p4b': 'Solutions marketplace, certification program, continental expansion',
            /* Early Adopter */
            'ea.eye': 'Early Adopter Program 2026',
            'ea.h2': 'Be among the first.<br>These terms won\'t be repeated.',
            'ea.sub': 'Limited spots for BESS projects in Chile and Latin America. In exchange: real data, technical feedback, and co-authorship in publications.',
            'ea.c1': 'Pioneer spots', 'ea.c2': 'Partner spots', 'ea.c3': 'Deployment start', 'ea.c4': 'Target countries',
            'ea.p1price': 'Implementation <strong>at no cost</strong> · dedicated technical support',
            'ea.p1b1': 'Apache 2.0 license — no royalties, forever',
            'ea.p1b2': 'Assisted installation on-site or remote',
            'ea.p1b3': 'Co-authorship in technical publications',
            'ea.p1b4': 'Early access to new features',
            'ea.p1b5': 'Priority integration of new hardware',
            'ea.p1b6': 'Monthly performance and estimated savings report',
            'ea.p1b7': 'Direct channel with the engineering team',
            'ea.p1req': 'Requirement: 100 kWh+ BESS operational or in commissioning 2026',
            'ea.p1btn': 'Apply to the Pioneer program →',
            'ea.p2price': 'Co-development · <strong>exclusive terms</strong>',
            'ea.p2b1': 'Everything in Pioneer tier, plus:',
            'ea.p2b2': 'Joint feature development',
            'ea.p2b3': 'White-label platform branding',
            'ea.p2b4': 'Regional exclusivity by country',
            'ea.p2b5': 'Joint representation before energy regulators',
            'ea.p2b6': 'Participation in project governance',
            'ea.p2b7': 'Preferential long-term terms',
            'ea.p2req': 'Requirement: BESS project >1 MWh or fleet of 3+ sites',
            'ea.p2btn': 'Talk to the founding team →',
            /* Final CTA */
            'cta.h2': 'The software the energy<br>transition needed.',
            'cta.sub': 'Open source. Industrial grade. Built in Latin America, for Latin America. No one else needs to build it. It already exists.',
            'cta.gh': 'View on GitHub', 'cta.contact': 'Contact the team',
            /* Footer */
            'foot.copy': '© 2026 BESS Solutions SpA · Santiago, Chile',
        },
        pt: {
            /* Nav */
            'nav.1': 'Origem', 'nav.2': 'A Virada', 'nav.3': 'A Rede', 'nav.4': 'BESSAI',
            'nav.5': 'Stack', 'nav.6': 'Dashboard', 'nav.7': 'Roadmap', 'nav.8': 'Impacto',
            'nav.cta': 'Solicitar demo',
            /* Geo banner */
            'geo.tag': 'Contexto Global',
            'geo.text': 'Enquanto alguns recuam, <strong>a América Latina lidera</strong> a transição energética com os melhores recursos solar e eólico do mundo.',
            /* Act I */
            'a1.badge': '<span class="badge-dot badge-dot-i"></span>ATO I · Origem',
            'a1.h1': '424 partes<br>por milhão.',
            'a1.h2': 'O CO₂ mais alto<br>em <span style="color:var(--amber)">800.000 anos.</span>',
            'a1.sub': 'Em vez de paralisar, o mundo escolheu <em>acelerar a maior transformação energética</em> da história.',
            /* Act II */
            'a2.badge': '<span class="badge-dot badge-dot-ii"></span>ATO II · A Virada',
            'a2.h1': 'Enquanto Washington<br>volta ao carvão…',
            'a2.h2': 'Santiago constrói<br><span style="color:var(--gold)">o futuro.</span>',
            'a2.sub': 'O Chile tem o <em>melhor recurso solar do planeta</em> (Atacama). A Colômbia o melhor eólico da América Latina. Um continente inteiro escolhendo a transição limpa.',
            /* Act III */
            'a3.badge': '<span class="badge-dot badge-dot-iii"></span>ATO III · A Rede',
            'a3.h1': '300 GW renováveis<br>instalados em 2023.',
            'a3.h2': 'O desafio não é mais gerar.<br><span style="color:var(--cyan)">É gerenciar.</span>',
            'a3.sub': 'A solar é <em>10 vezes mais barata</em> do que em 2010. O Chile mira 60% renovável até 2030. O gargalo agora é armazenamento + inteligência.',
            /* Act IV */
            'a4.badge': '<span class="badge-dot badge-dot-iv"></span>ATO IV · A Solução',
            'a4.h1': 'As baterias são<br>o músculo.',
            'a4.h2': 'BESSAI Edge,<br><span style="color:var(--green)">o cérebro.</span>',
            'a4.sub': 'Software open-source de grau industrial que transforma qualquer BESS em um nó inteligente: otimiza, prediz, protege. <em>Sem nuvem. Na borda.</em>',
            /* Feature cards */
            'f1.t': 'Otimização inteligente',
            'f1.d': 'Algoritmos avançados de IA que aprendem do mercado elétrico em tempo real e calculam o despacho ótimo de carga e descarga em milissegundos.',
            'f2.t': 'Qualquer hardware',
            'f2.d': 'Arquitetura modular projetada para se adaptar a qualquer fabricante de baterias e inversores. Plug and play industrial.',
            'f3.t': 'Cibersegurança industrial',
            'f3.d': 'Projetado sob os padrões mais exigentes de cibersegurança para infraestrutura energética crítica. Sem concessões.',
            'f4.t': '100% Edge. Sem nuvem.',
            'f4.d': 'Tudo roda localmente no local. Zero dependência de internet. Latência mínima. Máxima autonomia e resiliência operacional.',
            /* Act V */
            'a5.badge': '<span class="badge-dot" style="background:#a78bfa"></span>ATO V · A Construção',
            'a5.h1': 'Um trabalho de titãs.<br>E agora pertence a <span style="color:var(--green)">todos.</span>',
            'a5.sub': 'Mais de um ano de engenharia. Milhares de linhas de código. Modelos de linguagem treinados. Padrões industriais cumpridos. Tudo liberado sob licença Apache 2.0. Porque a transição energética não pode depender de software proprietário.',
            'a5.k1': 'Tempo de desenvolvimento', 'a5.k2': 'Linhas de código', 'a5.k3': 'Testes automatizados', 'a5.k4': 'Modelos IA treinados',
            'a5.stack': 'Stack tecnológico', 'a5.stackH': 'Linguagens e frameworks',
            'a5.s2': 'Otimização', 'a5.s3': 'Protocolos', 'a5.s4': 'Segurança',
            'a5.s5': 'Infraestrutura', 'a5.s6': 'Telemetria', 'a5.s7': 'Licença',
            'a5.ai': 'Inteligência artificial', 'a5.aiH': 'Modelos e capacidades',
            'a5.m1': 'Predição', 'a5.m1v': 'Custo marginal 24h',
            'a5.m2': 'Otimização', 'a5.m2v': 'Despacho ótimo MILP',
            'a5.m3': 'Adaptação', 'a5.m3v': 'DRL com dados SEN Chile',
            'a5.m4': 'Anomalias', 'a5.m4v': 'Detecção em tempo real',
            'a5.m5': 'Degradação', 'a5.m5v': 'Predição de vida útil',
            'a5.m6': 'Latência', 'a5.m6v': '<5ms inferência local',
            'a5.m7': 'Training data', 'a5.m7v': '+2 anos mercado LatAm',
            'a5.close': 'Este software foi projetado, arquitetado e construído do zero com uma premissa simples: <span style="color:var(--white)">nenhuma equipe de engenharia na América Latina precise construir isso novamente.</span> O problema está resolvido. O código existe. É open source. Use-o.',
            /* Impact */
            'imp.badge': '<span class="badge-dot" style="background:var(--gold)"></span>VISÃO · Impacto',
            'imp.h1': 'Isso não é um projeto.<br>É uma <span style="color:var(--gold)">missão mensurável.</span>',
            'imp.sub': 'Cada linha de código tem um propósito. Cada modelo um objetivo. E cada objetivo uma métrica. Assim mediremos nosso sucesso — e assim prestaremos contas.',
            'imp.e.dim': 'Energia', 'imp.e.goal': 'Otimizar o despacho de pelo menos 50 MWh gerenciados pelo BESSAI nos primeiros 12 meses de operação real.',
            'imp.e.k1': 'Capacidade gerenciada', 'imp.e.k2': 'Melhoria eficiência despacho', 'imp.e.prog': 'Ano 1 meta · operação piloto',
            'imp.$.dim': 'Econômico', 'imp.$.goal': 'Demonstrar uma economia operacional documentada de USD $200K+ anuais por operador, via arbitragem e peak-shaving otimizado por IA.',
            'imp.$.k1': 'Economia anual/operador', 'imp.$.k2': 'Aumento receita arbitragem', 'imp.$.prog': 'Validação em curso com early adopters',
            'imp.env.dim': 'Ambiental', 'imp.env.goal': 'Contribuir para evitar 10.000+ toneladas de CO₂ anuais ao otimizar o uso de baterias e integrar renováveis de forma inteligente.',
            'imp.env.k1': 'Ton CO₂ evitadas/ano', 'imp.env.k2': 'Integração renovável', 'imp.env.prog': 'Metodologia de medição em desenvolvimento',
            'imp.com.dim': 'Comunidade', 'imp.com.goal': 'Construir a comunidade open-source de referência para BESS na América Latina. 500+ engenheiros, 10+ universidades, 4+ países colaborando.',
            'imp.com.k1': 'Engenheiros na comunidade', 'imp.com.k2': 'Presença ativa', 'imp.com.prog': 'Discord aberto · GitHub ativo',
            'imp.tec.dim': 'Técnico', 'imp.tec.goal': 'Alcançar 99.9% uptime em implantações edge, latência <5ms em inferência local e precisão >92% na predição de custos marginais.',
            'imp.tec.k1': 'Uptime alvo', 'imp.tec.k2': 'Latência inferência', 'imp.tec.prog': 'Benchmarks internos concluídos',
            'imp.pledge': 'Publicaremos um <strong>relatório de impacto trimestral</strong> com dados reais verificáveis. Sem marketing. Sem inflação. Métricas honestas de um projeto que acredita na transparência radical.',
            /* Dashboard */
            'dash.eye': 'Telemetria em tempo real', 'dash.h2': 'O que o operador vê',
            'dash.sub': 'Simulação da interface operacional do BESSAI Edge. Dados atualizados a cada 2 segundos.',
            'dash.pw': 'Potência Ativa', 'dash.cmg': 'Custo Marginal', 'dash.lat': 'Latência Edge',
            'dash.chart': 'SoC e Potência · últimos 20 ciclos',
            'dash.status': 'Status do sistema', 'dash.op': 'operacional ✓',
            'dash.opt': 'Otimizador', 'dash.act': 'ativo ✓',
            'dash.bms': 'Link BMS', 'dash.conn': 'conectado ✓',
            'dash.sec': 'Segurança', 'dash.cert': 'certificado ✓',
            'dash.latK': 'Latência',
            'dash.socd.up': '↑ carregando', 'dash.socd.dn': '↓ descarregando',
            'dash.pwd.up': '↑ injetando', 'dash.pwd.dn': '↓ carregando',
            /* Roadmap */
            'rm.h2': 'Desenvolvimento aberto e transparente',
            'rm.p1t': 'Fase 1 · Fundação', 'rm.p1b': 'Conectividade industrial, motor de otimização base, segurança certificada, arquitetura edge',
            'rm.p2t': 'Fase 2 · Inteligência', 'rm.p2b': 'Stack de IA completo, predição de custos marginais, telemetria em tempo real, treinamento com dados SEN',
            'rm.p3t': 'Fase 3 · Frota', 'rm.p3b': 'Orquestração multi-site, resposta à demanda, interoperabilidade, primeiros early adopters em campo',
            'rm.p4t': 'Fase 4 · Ecossistema', 'rm.p4b': 'Marketplace de soluções, programa de certificação, expansão continental',
            /* Early Adopter */
            'ea.eye': 'Programa Early Adopter 2026',
            'ea.h2': 'Faça parte dos primeiros.<br>As condições não se repetem.',
            'ea.sub': 'Vagas limitadas para projetos BESS no Chile e na América Latina. Em troca: dados reais, feedback técnico e co-autoria em publicações.',
            'ea.c1': 'Vagas Pioneer', 'ea.c2': 'Vagas Partner', 'ea.c3': 'Início das implantações', 'ea.c4': 'Países alvo',
            'ea.p1price': 'Implementação <strong>sem custo</strong> · suporte técnico dedicado',
            'ea.p1b1': 'Licença Apache 2.0 — sem royalties, para sempre',
            'ea.p1b2': 'Instalação assistida no local ou remota',
            'ea.p1b3': 'Co-autoria em publicações técnicas',
            'ea.p1b4': 'Acesso antecipado a novas funcionalidades',
            'ea.p1b5': 'Integração prioritária de novo hardware',
            'ea.p1b6': 'Relatório mensal de desempenho e economia estimada',
            'ea.p1b7': 'Canal direto com a equipe de engenharia',
            'ea.p1req': 'Requisito: BESS de 100 kWh+ operacional ou em comissionamento 2026',
            'ea.p1btn': 'Candidatar-se ao programa Pioneer →',
            'ea.p2price': 'Co-desenvolvimento · <strong>condições exclusivas</strong>',
            'ea.p2b1': 'Tudo do tier Pioneer, mais:',
            'ea.p2b2': 'Desenvolvimento conjunto de funcionalidades',
            'ea.p2b3': 'Marca própria na plataforma (white-label)',
            'ea.p2b4': 'Exclusividade regional por país',
            'ea.p2b5': 'Representação conjunta perante reguladores energéticos',
            'ea.p2b6': 'Participação na governança do projeto',
            'ea.p2b7': 'Termos preferenciais de longo prazo',
            'ea.p2req': 'Requisito: projeto BESS >1 MWh ou frota de +3 sites',
            'ea.p2btn': 'Falar com a equipe fundadora →',
            /* Final CTA */
            'cta.h2': 'O software que a transição<br>energética precisava.',
            'cta.sub': 'Open source. Grau industrial. Construído na América Latina, para a América Latina. Ninguém mais precisa construir isso. Já existe.',
            'cta.gh': 'Ver no GitHub', 'cta.contact': 'Contatar a equipe',
            /* Footer */
            'foot.copy': '© 2026 BESS Solutions SpA · Santiago, Chile',
        },
    };

    let currentLang = 'es';

    function setLang(lang) {
        currentLang = lang;
        document.documentElement.lang = lang === 'pt' ? 'pt-BR' : lang;
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const v = T[lang] && T[lang][el.dataset.i18n];
            if (v !== undefined) el.innerHTML = v;
        });
        document.querySelectorAll('.lang-btn').forEach(b => {
            b.classList.toggle('active', b.textContent.trim().toLowerCase() === lang);
        });
        localStorage.setItem('bess-lang', lang);
    }
    window.setLang = setLang; // expose globally for onclick

    /* ── Three.js 3D Scenes ───────────────────────────────── */
    const canvas = document.getElementById('universe');
    if (!canvas) return;
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);
    const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, .1, 1000);
    camera.position.z = 28;

    const sceneObj = new THREE.Scene();

    /* Earth – blue dots */
    const earthGeo = new THREE.IcosahedronGeometry(8, 5);
    const earthMat = new THREE.PointsMaterial({ size: .06, color: 0x22d3ee, transparent: true, opacity: .9, sizeAttenuation: true });
    const earthPts = new THREE.Points(earthGeo, earthMat);
    sceneObj.add(earthPts);

    /* Grid – wireframe cube grid */
    const gGeo = new THREE.BoxGeometry(12, 12, 12, 6, 6, 6);
    const gMat = new THREE.PointsMaterial({ size: .07, color: 0x34d399, transparent: true, opacity: 0 });
    const gPts = new THREE.Points(gGeo, gMat);
    sceneObj.add(gPts);

    const edges = new THREE.EdgesGeometry(new THREE.BoxGeometry(12, 12, 12, 6, 6, 6));
    const lMat = new THREE.LineBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0 });
    const lines = new THREE.LineSegments(edges, lMat);
    sceneObj.add(lines);

    /* Neural – random points */
    const nPos = new Float32Array(1200);
    for (let i = 0; i < 1200; i++) nPos[i] = (Math.random() - .5) * 22;
    const nGeo = new THREE.BufferGeometry();
    nGeo.setAttribute('position', new THREE.BufferAttribute(nPos, 3));
    const nMat = new THREE.PointsMaterial({ size: .08, color: 0xa78bfa, transparent: true, opacity: 0 });
    const nPts = new THREE.Points(nGeo, nMat);
    sceneObj.add(nPts);

    const nEdge = new THREE.BufferGeometry();
    const nIdxArr = [];
    const pos = nGeo.attributes.position.array;
    for (let i = 0; i < 400; i++) {
        for (let j = i + 1; j < 400; j++) {
            const dx = pos[i * 3] - pos[j * 3], dy = pos[i * 3 + 1] - pos[j * 3 + 1], dz = pos[i * 3 + 2] - pos[j * 3 + 2];
            if (Math.sqrt(dx * dx + dy * dy + dz * dz) < 3.5) { nIdxArr.push(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2], pos[j * 3], pos[j * 3 + 1], pos[j * 3 + 2]); }
        }
    }
    nEdge.setAttribute('position', new THREE.Float32BufferAttribute(nIdxArr, 3));
    const nLMat = new THREE.LineBasicMaterial({ color: 0x34d399, transparent: true, opacity: 0 });
    const nLines = new THREE.LineSegments(nEdge, nLMat);
    sceneObj.add(nLines);

    /* Scene transitions */
    let currentScene = 'earth';
    function switchScene(target) {
        if (target === currentScene) return;
        currentScene = target;
        const dur = 500, steps = dur / 16;
        let f = 0;
        const tick = () => {
            f++; const t = Math.min(f / steps, 1);
            const easeT = t * t * (3 - 2 * t);
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

    /* Animation loop */
    function animate() {
        requestAnimationFrame(animate);
        const t = performance.now() * .001;
        earthPts.rotation.y = t * .07;
        earthPts.rotation.x = Math.sin(t * .04) * .1;
        gPts.rotation.y = t * .05;
        gPts.rotation.x = t * .03;
        lines.rotation.y = gPts.rotation.y;
        lines.rotation.x = gPts.rotation.x;
        nPts.rotation.y = t * .04;
        nLines.rotation.y = nPts.rotation.y;
        renderer.render(sceneObj, camera);
    }
    animate();

    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });

    /* ── Scene observer ───────────────────────────────────── */
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

    /* ── Reveal on scroll ─────────────────────────────────── */
    const revealObs = new IntersectionObserver(entries => {
        entries.forEach(e => {
            if (e.isIntersecting) { e.target.classList.add('visible'); revealObs.unobserve(e.target); }
        });
    }, { threshold: .15 });
    document.querySelectorAll('.reveal, .act-line').forEach(el => revealObs.observe(el));

    /* ── Counter animations ───────────────────────────────── */
    const counterObs = new IntersectionObserver(entries => {
        entries.forEach(e => {
            if (!e.isIntersecting) return;
            const el = e.target;
            counterObs.unobserve(el);
            const target = parseFloat(el.dataset.count);
            if (isNaN(target)) return;
            const prefix = el.dataset.prefix || '';
            const suffix = el.dataset.suffix || '';
            const isFloat = target % 1 !== 0;
            const dur = 1500, steps = dur / 16;
            let f = 0;
            const tick = () => {
                f++;
                const t = Math.min(f / steps, 1);
                const easeT = t < .5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
                const val = easeT * target;
                el.textContent = prefix + (isFloat ? val.toFixed(1) : Math.round(val).toLocaleString()) + suffix;
                if (t < 1) requestAnimationFrame(tick);
            };
            tick();
        });
    }, { threshold: .5 });
    document.querySelectorAll('[data-count]').forEach(el => counterObs.observe(el));

    /* ── Chart.js Dashboard ───────────────────────────────── */
    const chartEl = document.getElementById('chart-main');
    if (chartEl) {
        const socData = Array.from({ length: 20 }, () => 60 + Math.random() * 30);
        const pwData = Array.from({ length: 20 }, () => (Math.random() - .5) * 500);
        const chart = new Chart(chartEl, {
            type: 'line',
            data: {
                labels: Array.from({ length: 20 }, (_, i) => i + 1),
                datasets: [
                    { label: 'SoC %', data: [...socData], borderColor: '#22d3ee', backgroundColor: 'rgba(34,211,238,.08)', fill: true, tension: .4, pointRadius: 0 },
                    { label: 'kW/10', data: pwData.map(v => v / 10), borderColor: '#34d399', backgroundColor: 'rgba(52,211,153,.05)', fill: true, tension: .4, pointRadius: 0 },
                ],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    x: { display: false },
                    y: { grid: { color: 'rgba(255,255,255,.04)' }, ticks: { color: '#666', font: { size: 10, family: 'JetBrains Mono' } } },
                },
                plugins: { legend: { labels: { color: '#888', font: { size: 10, family: 'JetBrains Mono' } } } },
                animation: false,
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
            const lang = currentLang;
            $id('kpi-soc-d').textContent = T[lang][soc > 70 ? 'dash.socd.up' : 'dash.socd.dn'];
            $id('kpi-soc-d').className = 'kpi-delta ' + (soc > 70 ? 'up' : 'dn');
            $id('kpi-pw').textContent = (pw >= 0 ? '+' : '') + Math.round(pw) + ' kW';
            $id('kpi-pw-d').textContent = T[lang][pw > 0 ? 'dash.pwd.up' : 'dash.pwd.dn'];
            $id('kpi-pw-d').className = 'kpi-delta ' + (pw > 0 ? 'up' : 'dn');
            $id('kpi-cmg').textContent = '$' + Math.round(cmg);
            $id('kpi-lat').textContent = (2 + Math.random() * 3).toFixed(1) + 'ms';
        }, 2000);
    }

    /* ── Nav scroll state ─────────────────────────────────── */
    let navSolid = false;
    window.addEventListener('scroll', () => {
        const scrolled = window.scrollY > 80;
        if (scrolled !== navSolid) {
            navSolid = scrolled;
            document.getElementById('nav').classList.toggle('scrolled', scrolled);
        }
    }, { passive: true });

    /* ── Init language ────────────────────────────────────── */
    const saved = localStorage.getItem('bess-lang');
    const browserLang = (navigator.language || 'es').slice(0, 2);
    const initLang = saved || (['es', 'en', 'pt'].includes(browserLang) ? browserLang : 'es');
    setLang(initLang);

})();
