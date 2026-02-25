/* ═══════════════════════════════════════════════════
   BESS Solutions — ORBITAL main.js v3.0
   Deps: Three.js r134 · GSAP 3.12 ScrollTrigger · Chart.js 4
═══════════════════════════════════════════════════ */

/* ── i18n ─────────────────────────────────────────── */
const T = {
    es: {
        'nav.1': 'Origen', 'nav.2': 'El Giro', 'nav.3': 'La Red', 'nav.4': 'BESSAI',
        'nav.5': 'Stack', 'nav.6': 'Dashboard', 'nav.7': 'Roadmap', 'nav.8': 'Impacto', 'nav.cta': 'Solicitar demo',
        'geo.tag': 'Contexto Global',
        'geo.text': 'Mientras algunos dan marcha atrás, <strong>América Latina lidera</strong> la transición energética con el mejor recurso solar y eólico del mundo.',
        'a1.badge': '<span class="badge-dot badge-dot-i"></span>ACT I · Origen',
        'a1.h1': '424 partes<br>por millón.',
        'a1.h2': 'El CO₂ más alto<br>en <span class="amber">800.000 años.</span>',
        'a1.sub': 'Y en lugar de paralizarse, el mundo eligió <em>acelerar la mayor transformación energética</em> de la historia.',
        'a2.badge': '<span class="badge-dot badge-dot-ii"></span>ACT II · El Giro',
        'a2.h1': 'Mientras Washington<br>vuelve al carbón…',
        'a2.h2': '<span class="gold">Santiago construye<br>el futuro.</span>',
        'a2.s1': 'Solar más barata que en 2010', 'a2.s2': 'Renovables en LatAm 2023', 'a2.s3': 'Chile: mejor irradiación solar del mundo',
        'a3.badge': '<span class="badge-dot badge-dot-iii"></span>ACT III · La Red',
        'a3.h1': 'El desafío ya no<br>es generarla.',
        'a3.h2': 'Es <span class="cyan">almacenarla<br>e inteligentizarla.</span>',
        'a3.sub': 'Las baterías industriales están aquí. El software para gestionarlas — hasta ahora — no.',
        'a4.badge': '<span class="badge-dot badge-dot-iv"></span>ACT IV · El Cerebro',
        'a4.h1': 'Las baterías<br>son el músculo.',
        'a4.h2': '<span class="green">BESSAI Edge<br>es el cerebro.</span>',
        'a5.badge': '<span class="badge-dot" style="background:var(--cyan)"></span>ACT V · La Construcción',
        'a5.h2': 'Open-source.<br>Industrial-grade.<br><span class="cyan">Hecho en LatAm.</span>',
        'a5.sub': 'Software diseñado para las condiciones reales de la red eléctrica latinoamericana.',
        'a5.conn': 'Conectividad Industrial', 'a5.connH': 'Protocolos soportados',
        'a5.opt': 'Motor de Optimización', 'a5.optH': 'Estrategias de despacho',
        'a5.o1': 'Arbitraje precio', 'a5.o2': 'Peak-shaving', 'a5.o3': 'Freq. regulation', 'a5.o4': 'Degradación', 'a5.o5': 'Multi-mercado', 'a5.o6': 'V2G',
        'a5.ai': 'Inteligencia Artificial', 'a5.aiH': 'Modelos y capacidades',
        'a5.m1': 'Predicción', 'a5.m1v': 'CMg 24h-ahead',
        'a5.m2': 'Optimización', 'a5.m2v': 'Despacho MILP',
        'a5.m3': 'Adaptación', 'a5.m3v': 'DRL con datos SEN',
        'a5.m4': 'Anomalías', 'a5.m4v': 'Detección en tiempo real',
        'a5.m5': 'Degradación', 'a5.m5v': 'Vida útil predictiva',
        'a5.m6': 'Latencia',
        'a5.close': 'Este software fue diseñado, arquitecturado y construido desde cero con una premisa simple: <span style="color:var(--white)">que ningún equipo de ingeniería en Latinoamérica tenga que volver a construir esto.</span> El problema ya está resuelto. El código ya existe. Es open source. Úsenlo.',
        'imp.badge': '<span class="badge-dot" style="background:var(--gold)"></span>VISIÓN · Impacto',
        'imp.h1': 'Esto no es un proyecto.<br>Es una <span class="gold">misión medible.</span>',
        'imp.sub': 'Cada línea de código tiene un propósito. Cada modelo un objetivo. Y cada objetivo una métrica. Así mediremos nuestro éxito — y así rendiremos cuentas.',
        'imp.e.dim': 'Energía', 'imp.e.goal': 'Optimizar el despacho de 50 MWh gestionados por BESSAI en los primeros 12 meses de operación real.',
        'imp.e.k1': 'Capacidad gestionada', 'imp.e.k2': 'Mejora eficiencia', 'imp.e.prog': 'Año 1 meta · operación piloto',
        'imp.$.dim': 'Económico', 'imp.$.goal': 'Ahorro operativo documentado de USD $200K+ anuales por operador via arbitraje e IA.',
        'imp.$.k1': 'Ahorro anual/operador', 'imp.$.k2': 'Revenue arbitraje', 'imp.$.prog': 'Validación con early adopters',
        'imp.env.dim': 'Ambiental', 'imp.env.goal': 'Evitar 10.000+ toneladas de CO₂ anuales al optimizar baterías e integrar renovables.',
        'imp.env.k1': 'Ton CO₂ evitadas/año', 'imp.env.k2': 'Integración renovable', 'imp.env.prog': 'Metodología en desarrollo',
        'imp.com.dim': 'Comunidad', 'imp.com.goal': '500+ ingenieros, 10+ universidades, 4+ países colaborando en LatAm.',
        'imp.com.k1': 'Ingenieros', 'imp.com.k2': 'Presencia activa', 'imp.com.prog': 'Discord abierto · GitHub activo',
        'imp.tec.dim': 'Técnico', 'imp.tec.goal': '99.9% uptime edge, <5ms inferencia local, >92% precisión predicción CMg.',
        'imp.tec.k1': 'Uptime objetivo', 'imp.tec.k2': 'Latencia inferencia', 'imp.tec.prog': 'Benchmarks internos completados',
        'imp.pledge': 'Publicaremos un <strong>reporte de impacto trimestral</strong> con datos reales verificables. Sin marketing. Métricas honestas de un proyecto que cree en la transparencia radical.',
        'dash.eye': 'Telemetría en tiempo real', 'dash.h2': 'Lo que ve el operador',
        'dash.sub': 'Simulación de la interfaz operativa de BESSAI Edge. Datos actualizados cada 2 segundos.',
        'dash.site': 'Sitio: Atacama Solar Storage · 2 MWh',
        'dash.opt': 'Optimizador', 'dash.bms': 'BMS Link', 'dash.sec': 'Seguridad',
        'dash.pw': 'Potencia Activa', 'dash.cmg': 'Costo Marginal', 'dash.lat': 'Latencia Edge',
        'dash.chart': 'SoC y Potencia · últimos 20 ciclos', 'dash.latK': 'Latencia',
        'dash.socd.up': '↑ cargando', 'dash.socd.dn': '↓ descargando',
        'dash.pwd.up': '↑ inyectando', 'dash.pwd.dn': '↓ cargando',
        'feat.eye': 'Por qué BESSAI', 'feat.h2': 'Lo que otros no tienen',
        'feat.1t': 'Edge-First', 'feat.1d': 'Corre en hardware embebido. Sin cloud obligatorio. Sin latencia de red. Sin single point of failure.',
        'feat.2t': 'IA Local', 'feat.2d': 'Predicción de costos marginales, optimización MILP y DRL entrenados con datos reales del SEN chileno.',
        'feat.3t': 'Open Source', 'feat.3d': 'Apache 2.0. Sin royalties, sin lock-in, sin black boxes. El código que gestiona tu batería es tuyo para auditar.',
        'feat.4t': 'Industrial-Grade', 'feat.4d': 'IEC 62443 security baseline. Comunicación cifrada. Watchdog de hardware. Diseñado para 24/7 sin supervisión.',
        'feat.5t': 'Multi-Química', 'feat.5d': 'LFP, NMC, NCA, VRLA. Si tiene Modbus o CAN, BESSAI lo habla. Agnóstico de hardware por diseño.',
        'feat.6t': 'LatAm-Native', 'feat.6d': 'Integración nativa con CEN, ANDES, API Coordinador Chile. Entiende los mercados donde opera.',
        'rm.eye': 'Roadmap', 'rm.h2': 'Construcción abierta y transparente',
        'rm.p1t': 'Fase 1 · Fundación', 'rm.p1b': 'Conectividad industrial, motor optimización base, seguridad certificada, arquitectura edge',
        'rm.p2t': 'Fase 2 · Inteligencia', 'rm.p2b': 'Stack IA completo, predicción CMg, telemetría en tiempo real, entrenamiento datos SEN',
        'rm.p3t': 'Fase 3 · Flota', 'rm.p3b': 'Orquestación multi-sitio, respuesta demanda, interoperabilidad, early adopters en terreno',
        'rm.p4t': 'Fase 4 · Ecosistema', 'rm.p4b': 'Marketplace soluciones, programa certificación, expansión continental',
        'ea.eye': 'Programa Early Adopter 2026',
        'ea.h2': 'Sea parte de los primeros.<br>Las condiciones no se repiten.',
        'ea.sub': 'Cupos limitados para proyectos BESS en Chile y Latinoamérica. A cambio: datos reales, feedback técnico, y co-autoría en publicaciones.',
        'ea.c1': '5 cupos Pioneer', 'ea.c2': '3 cupos Partner', 'ea.c3': 'Q2 2026',
        'ea.p1name': 'Pioneer', 'ea.p1price': 'Sin costo · soporte técnico dedicado',
        'ea.p1b1': 'Licencia Apache 2.0 — sin royalties, para siempre',
        'ea.p1b2': 'Instalación asistida en sitio o remota',
        'ea.p1b3': 'Co-autoría en publicaciones técnicas',
        'ea.p1b4': 'Acceso anticipado a nuevas funcionalidades',
        'ea.p1b5': 'Integración prioritaria de nuevo hardware',
        'ea.p1b6': 'Reporte mensual performance y ahorro estimado',
        'ea.p1b7': 'Canal directo con equipo de ingeniería',
        'ea.p1req': 'Requisito: BESS 100 kWh+ operativo o en comisionamiento 2026',
        'ea.p1cta': 'Aplicar al programa Pioneer →',
        'ea.p2name': 'Strategic Partner', 'ea.p2price': 'Co-inversión · revenue sharing',
        'ea.p2b1': 'Todo lo de Pioneer incluido',
        'ea.p2b2': 'Co-desarrollo de funcionalidades propias',
        'ea.p2b3': 'Integración con sistemas SCADA existentes',
        'ea.p2b4': 'Modelo de revenue sharing en ahorros',
        'ea.p2b5': 'SLA de respuesta <4h 24/7',
        'ea.p2b6': 'Presencia en roadmap público',
        'ea.p2b7': 'Board advisor seat opcional',
        'ea.p2req': 'Requisito: BESS 500 kWh+ o flota de proyectos',
        'ea.p2cta': 'Hablar con el equipo fundador →',
        'cta.eye': 'Open Source · Gratis · Para siempre',
        'cta.h2': 'El futuro energético de<br>Latinoamérica se construye<br><span class="cyan">en código abierto.</span>',
        'cta.sub': 'Únete a la comunidad que está construyendo el software de gestión de baterías más avanzado de la región.',
        'cta.gh': 'Ver en GitHub', 'cta.contact': 'Contactar al equipo',
        'foot.tag': 'Inteligencia para el almacenamiento de energía.',
        'foot.proj': 'Proyecto', 'foot.ch': 'Changelog', 'foot.lic': 'Licencia',
        'foot.comm': 'Comunidad', 'foot.contact': 'Contacto', 'foot.oss': 'Software libre bajo Apache 2.0',
    },
    en: {
        'nav.1': 'Origin', 'nav.2': 'The Shift', 'nav.3': 'The Grid', 'nav.4': 'BESSAI',
        'nav.5': 'Stack', 'nav.6': 'Dashboard', 'nav.7': 'Roadmap', 'nav.8': 'Impact', 'nav.cta': 'Request demo',
        'geo.tag': 'Global Context',
        'geo.text': 'While some step back, <strong>Latin America leads</strong> the energy transition with the world\'s best solar & wind resources.',
        'a1.badge': '<span class="badge-dot badge-dot-i"></span>ACT I · Origin',
        'a1.h1': '424 parts<br>per million.',
        'a1.h2': 'The highest CO₂<br>in <span class="amber">800,000 years.</span>',
        'a1.sub': 'Instead of freezing, the world chose to <em>accelerate the largest energy transformation</em> in history.',
        'a2.badge': '<span class="badge-dot badge-dot-ii"></span>ACT II · The Shift',
        'a2.h1': 'While Washington<br>returns to coal…',
        'a2.h2': '<span class="gold">Santiago builds<br>the future.</span>',
        'a2.s1': 'Solar cheaper than in 2010', 'a2.s2': 'Renewables in LatAm 2023', 'a2.s3': 'Chile: world\'s best solar irradiance',
        'a3.badge': '<span class="badge-dot badge-dot-iii"></span>ACT III · The Grid',
        'a3.h1': 'The challenge is no longer<br>generating it.',
        'a3.h2': 'It\'s <span class="cyan">storing it<br>and making it intelligent.</span>',
        'a3.sub': 'Industrial batteries are here. The software to manage them — until now — was not.',
        'a4.badge': '<span class="badge-dot badge-dot-iv"></span>ACT IV · The Brain',
        'a4.h1': 'Batteries<br>are the muscle.',
        'a4.h2': '<span class="green">BESSAI Edge<br>is the brain.</span>',
        'a5.badge': '<span class="badge-dot" style="background:var(--cyan)"></span>ACT V · The Build',
        'a5.h2': 'Open-source.<br>Industrial-grade.<br><span class="cyan">Built in LatAm.</span>',
        'a5.sub': 'Software designed for the real conditions of the Latin American electrical grid.',
        'a5.conn': 'Industrial Connectivity', 'a5.connH': 'Supported protocols',
        'a5.opt': 'Optimization Engine', 'a5.optH': 'Dispatch strategies',
        'a5.o1': 'Price arbitrage', 'a5.o2': 'Peak-shaving', 'a5.o3': 'Freq. regulation', 'a5.o4': 'Degradation', 'a5.o5': 'Multi-market', 'a5.o6': 'V2G',
        'a5.ai': 'Artificial Intelligence', 'a5.aiH': 'Models and capabilities',
        'a5.m1': 'Prediction', 'a5.m1v': 'CMg 24h-ahead',
        'a5.m2': 'Optimization', 'a5.m2v': 'MILP Dispatch',
        'a5.m3': 'Adaptation', 'a5.m3v': 'DRL with SEN data',
        'a5.m4': 'Anomalies', 'a5.m4v': 'Real-time detection',
        'a5.m5': 'Degradation', 'a5.m5v': 'Predictive lifespan',
        'a5.m6': 'Latency',
        'a5.close': 'This software was designed, architected, and built from scratch with one simple premise: <span style="color:var(--white)">no engineering team in Latin America should ever have to build this again.</span> The problem is solved. The code exists. It\'s open source. Use it.',
        'imp.badge': '<span class="badge-dot" style="background:var(--gold)"></span>VISION · Impact',
        'imp.h1': 'This is not a project.<br>It\'s a <span class="gold">measurable mission.</span>',
        'imp.sub': 'Every line of code has a purpose. Every model an objective. And every objective a metric. This is how we\'ll measure success — and how we\'ll be held accountable.',
        'imp.e.dim': 'Energy', 'imp.e.goal': 'Optimize dispatch of 50 MWh managed by BESSAI in the first 12 months of real operation.',
        'imp.e.k1': 'Managed capacity', 'imp.e.k2': 'Efficiency improvement', 'imp.e.prog': 'Year 1 target · pilot operation',
        'imp.$.dim': 'Economic', 'imp.$.goal': 'Documented operational savings of USD $200K+ per operator per year via AI-optimized arbitrage.',
        'imp.$.k1': 'Annual savings/operator', 'imp.$.k2': 'Arbitrage revenue', 'imp.$.prog': 'Validation underway with early adopters',
        'imp.env.dim': 'Environmental', 'imp.env.goal': 'Avoid 10,000+ tons of CO₂ annually by optimizing batteries and integrating renewables intelligently.',
        'imp.env.k1': 'Tons CO₂ avoided/year', 'imp.env.k2': 'Renewable integration', 'imp.env.prog': 'Measurement methodology in development',
        'imp.com.dim': 'Community', 'imp.com.goal': '500+ engineers, 10+ universities, 4+ countries collaborating in LatAm.',
        'imp.com.k1': 'Engineers', 'imp.com.k2': 'Active presence', 'imp.com.prog': 'Discord open · GitHub active',
        'imp.tec.dim': 'Technical', 'imp.tec.goal': '99.9% uptime edge deployments, <5ms local inference, >92% accuracy CMg prediction.',
        'imp.tec.k1': 'Target uptime', 'imp.tec.k2': 'Inference latency', 'imp.tec.prog': 'Internal benchmarks completed',
        'imp.pledge': 'We will publish a <strong>quarterly impact report</strong> with verifiable real data. No marketing. Honest metrics from a project that believes in radical transparency.',
        'dash.eye': 'Real-time telemetry', 'dash.h2': 'What the operator sees',
        'dash.sub': 'Simulation of the BESSAI Edge operational interface. Data updated every 2 seconds.',
        'dash.site': 'Site: Atacama Solar Storage · 2 MWh',
        'dash.opt': 'Optimizer', 'dash.bms': 'BMS Link', 'dash.sec': 'Security',
        'dash.pw': 'Active Power', 'dash.cmg': 'Marginal Cost', 'dash.lat': 'Edge Latency',
        'dash.chart': 'SoC & Power · last 20 cycles', 'dash.latK': 'Latency',
        'dash.socd.up': '↑ charging', 'dash.socd.dn': '↓ discharging',
        'dash.pwd.up': '↑ injecting', 'dash.pwd.dn': '↓ charging',
        'feat.eye': 'Why BESSAI', 'feat.h2': 'What others don\'t have',
        'feat.1t': 'Edge-First', 'feat.1d': 'Runs on embedded hardware. No mandatory cloud. No network latency. No single point of failure.',
        'feat.2t': 'Local AI', 'feat.2d': 'Marginal cost prediction, MILP and DRL optimization trained on real SEN Chilean data.',
        'feat.3t': 'Open Source', 'feat.3d': 'Apache 2.0. No royalties, no lock-in, no black boxes. The code managing your battery is yours to audit.',
        'feat.4t': 'Industrial-Grade', 'feat.4d': 'IEC 62443 security baseline. Encrypted comms. Hardware watchdog. Designed for 24/7 unattended operation.',
        'feat.5t': 'Multi-Chemistry', 'feat.5d': 'LFP, NMC, NCA, VRLA. If it has Modbus or CAN, BESSAI speaks it. Hardware-agnostic by design.',
        'feat.6t': 'LatAm-Native', 'feat.6d': 'Native integration with CEN, ANDES, Coordinador Chile API. Understands the markets where it operates.',
        'rm.eye': 'Roadmap', 'rm.h2': 'Open and transparent development',
        'rm.p1t': 'Phase 1 · Foundation', 'rm.p1b': 'Industrial connectivity, base optimization engine, certified security, edge architecture',
        'rm.p2t': 'Phase 2 · Intelligence', 'rm.p2b': 'Complete AI stack, CMg prediction, real-time telemetry, SEN data training',
        'rm.p3t': 'Phase 3 · Fleet', 'rm.p3b': 'Multi-site orchestration, demand response, interoperability, first early adopters deployed',
        'rm.p4t': 'Phase 4 · Ecosystem', 'rm.p4b': 'Solutions marketplace, certification program, continental expansion',
        'ea.eye': 'Early Adopter Program 2026',
        'ea.h2': 'Be among the first.<br>These terms won\'t repeat.',
        'ea.sub': 'Limited slots for BESS projects in Chile and Latin America. In exchange: real data, technical feedback, and co-authorship in publications.',
        'ea.c1': '5 Pioneer slots', 'ea.c2': '3 Partner slots', 'ea.c3': 'Q2 2026',
        'ea.p1name': 'Pioneer', 'ea.p1price': 'No cost · dedicated technical support',
        'ea.p1b1': 'Apache 2.0 license — no royalties, forever',
        'ea.p1b2': 'On-site or remote assisted installation',
        'ea.p1b3': 'Co-authorship in technical publications',
        'ea.p1b4': 'Early access to new features',
        'ea.p1b5': 'Priority integration of new hardware',
        'ea.p1b6': 'Monthly performance and savings report',
        'ea.p1b7': 'Direct channel with the engineering team',
        'ea.p1req': 'Requirement: BESS 100 kWh+ operational or commissioning in 2026',
        'ea.p1cta': 'Apply to Pioneer program →',
        'ea.p2name': 'Strategic Partner', 'ea.p2price': 'Co-investment · revenue sharing',
        'ea.p2b1': 'Everything in Pioneer included',
        'ea.p2b2': 'Co-development of custom features',
        'ea.p2b3': 'Integration with existing SCADA systems',
        'ea.p2b4': 'Revenue sharing model on savings',
        'ea.p2b5': '<4h 24/7 response SLA',
        'ea.p2b6': 'Presence on public roadmap',
        'ea.p2b7': 'Optional board advisor seat',
        'ea.p2req': 'Requirement: BESS 500 kWh+ or project portfolio',
        'ea.p2cta': 'Talk to the founding team →',
        'cta.eye': 'Open Source · Free · Forever',
        'cta.h2': 'The energy future of<br>Latin America is built<br><span class="cyan">in open code.</span>',
        'cta.sub': 'Join the community building the most advanced battery management software in the region.',
        'cta.gh': 'View on GitHub', 'cta.contact': 'Contact the team',
        'foot.tag': 'Intelligence for energy storage.',
        'foot.proj': 'Project', 'foot.ch': 'Changelog', 'foot.lic': 'License',
        'foot.comm': 'Community', 'foot.contact': 'Contact', 'foot.oss': 'Free software under Apache 2.0',
    },
    pt: {
        'nav.1': 'Origem', 'nav.2': 'A Virada', 'nav.3': 'A Rede', 'nav.4': 'BESSAI',
        'nav.5': 'Stack', 'nav.6': 'Dashboard', 'nav.7': 'Roadmap', 'nav.8': 'Impacto', 'nav.cta': 'Solicitar demo',
        'geo.tag': 'Contexto Global',
        'geo.text': 'Enquanto alguns recuam, <strong>a América Latina lidera</strong> a transição energética com os melhores recursos solar e eólico do mundo.',
        'a1.badge': '<span class="badge-dot badge-dot-i"></span>ATO I · Origem',
        'a1.h1': '424 partes<br>por milhão.',
        'a1.h2': 'O CO₂ mais alto<br>em <span class="amber">800.000 anos.</span>',
        'a1.sub': 'Em vez de paralisar, o mundo escolheu <em>acelerar a maior transformação energética</em> da história.',
        'a2.badge': '<span class="badge-dot badge-dot-ii"></span>ATO II · A Virada',
        'a2.h1': 'Enquanto Washington<br>volta ao carvão…',
        'a2.h2': '<span class="gold">Santiago constrói<br>o futuro.</span>',
        'a2.s1': 'Solar mais barata que em 2010', 'a2.s2': 'Renováveis na LatAm 2023', 'a2.s3': 'Chile: melhor irradiação solar do mundo',
        'a3.badge': '<span class="badge-dot badge-dot-iii"></span>ATO III · A Rede',
        'a3.h1': 'O desafio não é<br>mais gerá-la.',
        'a3.h2': 'É <span class="cyan">armazená-la<br>e inteligentizá-la.</span>',
        'a3.sub': 'As baterias industriais já estão aqui. O software para gerenciá-las — até agora — não.',
        'a4.badge': '<span class="badge-dot badge-dot-iv"></span>ATO IV · O Cérebro',
        'a4.h1': 'As baterias<br>são o músculo.',
        'a4.h2': '<span class="green">BESSAI Edge<br>é o cérebro.</span>',
        'a5.badge': '<span class="badge-dot" style="background:var(--cyan)"></span>ATO V · A Construção',
        'a5.h2': 'Open-source.<br>Industrial-grade.<br><span class="cyan">Feito na LatAm.</span>',
        'a5.sub': 'Software projetado para as condições reais da rede elétrica latino-americana.',
        'a5.conn': 'Conectividade Industrial', 'a5.connH': 'Protocolos suportados',
        'a5.opt': 'Motor de Otimização', 'a5.optH': 'Estratégias de despacho',
        'a5.o1': 'Arbitragem preço', 'a5.o2': 'Peak-shaving', 'a5.o3': 'Reg. frequência', 'a5.o4': 'Degradação', 'a5.o5': 'Multi-mercado', 'a5.o6': 'V2G',
        'a5.ai': 'Inteligência Artificial', 'a5.aiH': 'Modelos e capacidades',
        'a5.m1': 'Predição', 'a5.m1v': 'CMg 24h-ahead',
        'a5.m2': 'Otimização', 'a5.m2v': 'Despacho MILP',
        'a5.m3': 'Adaptação', 'a5.m3v': 'DRL com dados SEN',
        'a5.m4': 'Anomalias', 'a5.m4v': 'Detecção em tempo real',
        'a5.m5': 'Degradação', 'a5.m5v': 'Vida útil preditiva',
        'a5.m6': 'Latência',
        'a5.close': 'Este software foi projetado, arquitetado e construído do zero com uma premissa simples: <span style="color:var(--white)">nenhuma equipe de engenharia na América Latina precise construir isso novamente.</span> O problema está resolvido. O código existe. É open source. Use-o.',
        'imp.badge': '<span class="badge-dot" style="background:var(--gold)"></span>VISÃO · Impacto',
        'imp.h1': 'Isso não é um projeto.<br>É uma <span class="gold">missão mensurável.</span>',
        'imp.sub': 'Cada linha de código tem um propósito. Cada modelo um objetivo. E cada objetivo uma métrica. Assim mediremos nosso sucesso — e assim prestaremos contas.',
        'imp.e.dim': 'Energia', 'imp.e.goal': 'Otimizar o despacho de 50 MWh gerenciados pelo BESSAI nos primeiros 12 meses de operação real.',
        'imp.e.k1': 'Capacidade gerenciada', 'imp.e.k2': 'Melhoria eficiência', 'imp.e.prog': 'Ano 1 meta · operação piloto',
        'imp.$.dim': 'Econômico', 'imp.$.goal': 'Economia operacional de USD $200K+ anuais por operador via arbitragem e IA.',
        'imp.$.k1': 'Economia anual/operador', 'imp.$.k2': 'Receita arbitragem', 'imp.$.prog': 'Validação com early adopters',
        'imp.env.dim': 'Ambiental', 'imp.env.goal': 'Evitar 10.000+ toneladas de CO₂ anuais otimizando baterias e integrando renováveis.',
        'imp.env.k1': 'Ton CO₂ evitadas/ano', 'imp.env.k2': 'Integração renovável', 'imp.env.prog': 'Metodologia em desenvolvimento',
        'imp.com.dim': 'Comunidade', 'imp.com.goal': '500+ engenheiros, 10+ universidades, 4+ países colaborando na LatAm.',
        'imp.com.k1': 'Engenheiros', 'imp.com.k2': 'Presença ativa', 'imp.com.prog': 'Discord aberto · GitHub ativo',
        'imp.tec.dim': 'Técnico', 'imp.tec.goal': '99.9% uptime edge, <5ms inferência local, >92% precisão predição CMg.',
        'imp.tec.k1': 'Uptime alvo', 'imp.tec.k2': 'Latência inferência', 'imp.tec.prog': 'Benchmarks internos concluídos',
        'imp.pledge': 'Publicaremos um <strong>relatório de impacto trimestral</strong> com dados reais verificáveis. Sem marketing. Métricas honestas de um projeto que acredita na transparência radical.',
        'dash.eye': 'Telemetria em tempo real', 'dash.h2': 'O que o operador vê',
        'dash.sub': 'Simulação da interface operacional do BESSAI Edge. Dados atualizados a cada 2 segundos.',
        'dash.site': 'Site: Atacama Solar Storage · 2 MWh',
        'dash.opt': 'Otimizador', 'dash.bms': 'BMS Link', 'dash.sec': 'Segurança',
        'dash.pw': 'Potência Ativa', 'dash.cmg': 'Custo Marginal', 'dash.lat': 'Latência Edge',
        'dash.chart': 'SoC e Potência · últimos 20 ciclos', 'dash.latK': 'Latência',
        'dash.socd.up': '↑ carregando', 'dash.socd.dn': '↓ descarregando',
        'dash.pwd.up': '↑ injetando', 'dash.pwd.dn': '↓ carregando',
        'feat.eye': 'Por que BESSAI', 'feat.h2': 'O que outros não têm',
        'feat.1t': 'Edge-First', 'feat.1d': 'Roda em hardware embarcado. Sem cloud obrigatório. Sem latência de rede. Sem ponto único de falha.',
        'feat.2t': 'IA Local', 'feat.2d': 'Predição de custos marginais, otimização MILP e DRL treinados com dados reais do SEN chileno.',
        'feat.3t': 'Open Source', 'feat.3d': 'Apache 2.0. Sem royalties, sem lock-in, sem caixas pretas. O código que gerencia sua bateria é seu para auditar.',
        'feat.4t': 'Industrial-Grade', 'feat.4d': 'IEC 62443 security baseline. Comunicação cifrada. Watchdog de hardware. Projetado para 24/7 sem supervisão.',
        'feat.5t': 'Multi-Química', 'feat.5d': 'LFP, NMC, NCA, VRLA. Se tem Modbus ou CAN, BESSAI fala. Agnóstico de hardware por design.',
        'feat.6t': 'LatAm-Native', 'feat.6d': 'Integração nativa com CEN, ANDES, API Coordinador Chile. Entende os mercados onde opera.',
        'rm.eye': 'Roadmap', 'rm.h2': 'Construção aberta e transparente',
        'rm.p1t': 'Fase 1 · Fundação', 'rm.p1b': 'Conectividade industrial, motor otimização base, segurança certificada, arquitetura edge',
        'rm.p2t': 'Fase 2 · Inteligência', 'rm.p2b': 'Stack IA completo, predição CMg, telemetria em tempo real, treinamento dados SEN',
        'rm.p3t': 'Fase 3 · Frota', 'rm.p3b': 'Orquestração multi-site, resposta demanda, interoperabilidade, early adopters em campo',
        'rm.p4t': 'Fase 4 · Ecossistema', 'rm.p4b': 'Marketplace soluções, programa certificação, expansão continental',
        'ea.eye': 'Programa Early Adopter 2026',
        'ea.h2': 'Seja um dos primeiros.<br>As condições não se repetem.',
        'ea.sub': 'Vagas limitadas para projetos BESS no Chile e América Latina. Em troca: dados reais, feedback técnico e co-autoria em publicações.',
        'ea.c1': '5 vagas Pioneer', 'ea.c2': '3 vagas Partner', 'ea.c3': 'Q2 2026',
        'ea.p1name': 'Pioneer', 'ea.p1price': 'Sem custo · suporte técnico dedicado',
        'ea.p1b1': 'Licença Apache 2.0 — sem royalties, para sempre',
        'ea.p1b2': 'Instalação assistida no local ou remota',
        'ea.p1b3': 'Co-autoria em publicações técnicas',
        'ea.p1b4': 'Acesso antecipado a novas funcionalidades',
        'ea.p1b5': 'Integração prioritária de novo hardware',
        'ea.p1b6': 'Relatório mensal de performance e economia',
        'ea.p1b7': 'Canal direto com a equipe de engenharia',
        'ea.p1req': 'Requisito: BESS 100 kWh+ operacional ou em comissionamento 2026',
        'ea.p1cta': 'Aplicar ao programa Pioneer →',
        'ea.p2name': 'Strategic Partner', 'ea.p2price': 'Co-investimento · revenue sharing',
        'ea.p2b1': 'Tudo do Pioneer incluído',
        'ea.p2b2': 'Co-desenvolvimento de funcionalidades próprias',
        'ea.p2b3': 'Integração com sistemas SCADA existentes',
        'ea.p2b4': 'Modelo de revenue sharing nas economias',
        'ea.p2b5': 'SLA de resposta <4h 24/7',
        'ea.p2b6': 'Presença no roadmap público',
        'ea.p2b7': 'Assento opcional de board advisor',
        'ea.p2req': 'Requisito: BESS 500 kWh+ ou portfólio de projetos',
        'ea.p2cta': 'Falar com a equipe fundadora →',
        'cta.eye': 'Open Source · Gratuito · Para sempre',
        'cta.h2': 'O futuro energético da<br>América Latina é construído<br><span class="cyan">em código aberto.</span>',
        'cta.sub': 'Junte-se à comunidade que está construindo o software de gestão de baterias mais avançado da região.',
        'cta.gh': 'Ver no GitHub', 'cta.contact': 'Contatar a equipe',
        'foot.tag': 'Inteligência para o armazenamento de energia.',
        'foot.proj': 'Projeto', 'foot.ch': 'Changelog', 'foot.lic': 'Licença',
        'foot.comm': 'Comunidade', 'foot.contact': 'Contato', 'foot.oss': 'Software livre sob Apache 2.0',
    }
};

function setLang(lang) {
    document.documentElement.lang = lang === 'pt' ? 'pt-BR' : lang;
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const v = T[lang]?.[el.dataset.i18n];
        if (v !== undefined) el.innerHTML = v;
    });
    ['es', 'en', 'pt'].forEach(l => document.getElementById('lang-' + l)?.classList.toggle('active', l === lang));
    localStorage.setItem('lang', lang);
    // Dashboard KPI labels
    const soc = document.getElementById('kpi-soc-d');
    const pwd = document.getElementById('kpi-pw-d');
    if (soc) soc.dataset.up = T[lang]['dash.socd.up'] || '↑ cargando';
    if (soc) soc.dataset.dn = T[lang]['dash.socd.dn'] || '↓ descargando';
    if (pwd) pwd.dataset.up = T[lang]['dash.pwd.up'] || '↑ inyectando';
    if (pwd) pwd.dataset.dn = T[lang]['dash.pwd.dn'] || '↓ cargando';
}

window.setLang = setLang;

/* ── MOBILE MENU ──────────────────────────────────────── */
function toggleMobileMenu() {
    const menu = document.getElementById('mob-menu');
    const isOpen = menu.classList.contains('open');
    if (isOpen) {
        closeMobileMenu();
    } else {
        menu.classList.add('open');
        menu.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        // Update i18n inside mobile menu
        const lang = localStorage.getItem('lang') || 'es';
        menu.querySelectorAll('[data-i18n]').forEach(el => {
            const v = T[lang]?.[el.dataset.i18n];
            if (v !== undefined) el.innerHTML = v;
        });
    }
}

function closeMobileMenu() {
    const menu = document.getElementById('mob-menu');
    menu.classList.remove('open');
    menu.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
}

// Close mobile menu on scroll
window.addEventListener('scroll', () => {
    const menu = document.getElementById('mob-menu');
    if (menu?.classList.contains('open')) closeMobileMenu();
}, { passive: true });

window.toggleMobileMenu = toggleMobileMenu;
window.closeMobileMenu = closeMobileMenu;

/* ── BOOT ─────────────────────────────────────────── */
window.addEventListener('DOMContentLoaded', () => {
    const saved = localStorage.getItem('lang') ||
        (navigator.language?.startsWith('pt') ? 'pt' :
            navigator.language?.startsWith('en') ? 'en' : 'es');
    setLang(saved);
    initNav();
    initReveal();
    initCounters();
    initImpactBars();
    initTerminal();
    waitForLibs(initAll);
});

function waitForLibs(cb) {
    if (typeof THREE !== 'undefined' && typeof gsap !== 'undefined' && typeof Chart !== 'undefined') {
        cb();
    } else {
        setTimeout(() => waitForLibs(cb), 80);
    }
}

function initAll() {
    gsap.registerPlugin(ScrollTrigger);
    initThree();
    initGSAP();
    initDashboard();
}

/* ── NAV SCROLL ───────────────────────────────────── */
function initNav() {
    const nav = document.getElementById('nav');
    const onScroll = () => nav.classList.toggle('scrolled', window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
}

/* ── REVEAL OBSERVER ──────────────────────────────────────── */
function initReveal() {
    const io = new IntersectionObserver(entries => {
        entries.forEach(e => {
            if (e.isIntersecting) {
                e.target.classList.add('visible');
                io.unobserve(e.target);
            }
        });
    }, { threshold: .1 });
    document.querySelectorAll('.reveal').forEach(el => io.observe(el));

    // Stat items — each observed individually with stagger via delay
    const statIo = new IntersectionObserver(entries => {
        entries.forEach(e => {
            if (!e.isIntersecting) return;
            const idx = [...document.querySelectorAll('.stat-item')].indexOf(e.target);
            setTimeout(() => e.target.classList.add('visible'), idx * 180);
            statIo.unobserve(e.target);
        });
    }, { threshold: .15 });
    document.querySelectorAll('.stat-item').forEach(el => statIo.observe(el));
}

/* ── COUNTERS ─────────────────────────────────────────────── */
function initCounters() {
    const io = new IntersectionObserver(entries => {
        entries.forEach(e => {
            if (!e.isIntersecting) return;
            const el = e.target;
            const target = +el.dataset.count;
            const suffix = el.dataset.suffix || '';
            const dur = 1800;
            const start = performance.now();
            const tick = (now) => {
                const p = Math.min((now - start) / dur, 1);
                // Ease out cubic
                const ease = 1 - Math.pow(1 - p, 3);
                el.textContent = Math.round(target * ease) + suffix;
                if (p < 1) requestAnimationFrame(tick);
                else el.textContent = target + suffix;
            };
            requestAnimationFrame(tick);
            io.unobserve(el);
        });
    }, { threshold: .25 });
    document.querySelectorAll('[data-count]').forEach(el => io.observe(el));
}

/* ── IMPACT BARS ──────────────────────────────────── */
function initImpactBars() {
    const io = new IntersectionObserver(entries => {
        entries.forEach(e => {
            if (!e.isIntersecting) return;
            e.target.querySelectorAll('.impact-bar').forEach(b => {
                // Read --bar-w from inline style attribute (works for CSS custom props declared inline)
                const barW = b.style.getPropertyValue('--bar-w') ||
                    getComputedStyle(b).getPropertyValue('--bar-w').trim();
                if (barW) b.style.width = barW;
            });
            io.unobserve(e.target);
        });
    }, { threshold: .1 });
    document.querySelectorAll('.impact-card').forEach(el => {
        el.querySelectorAll('.impact-bar').forEach(b => b.style.width = '0');
        io.observe(el);
    });
}

/* ── TERMINAL ANIMATION ───────────────────────────── */
function initTerminal() {
    const body = document.getElementById('term-body');
    if (!body) return;
    const lines = [
        { type: 'cmd', text: 'bessai start --mode=optimize' },
        { type: 'out', text: '→ Loading config edge.toml...', delay: 600 },
        { type: 'ok', text: '✓ BMS connected · Modbus RTU /dev/ttyUSB0', delay: 1000 },
        { type: 'ok', text: '✓ Grid API · SEN Coordinador · OK', delay: 1400 },
        { type: 'out', text: '→ Fetching CMg forecast (24h)...', delay: 1800 },
        { type: 'ok', text: '✓ Modelo cargado · MAPE 4.2%', delay: 2400 },
        { type: 'out', text: '→ Running MILP optimizer...', delay: 2800 },
        { type: 'ok', text: '✓ Dispatch plan ready · 18 cycles', delay: 3400 },
        { type: 'warn', text: '⚡ Peak window: 18:00-22:00 · discharge', delay: 3800 },
        { type: 'ok', text: '✓ Latency: 3.1ms · SoC: 87.4%', delay: 4200 },
    ];

    const io = new IntersectionObserver(entries => {
        if (!entries[0].isIntersecting) return;
        io.disconnect();
        body.innerHTML = '';
        lines.forEach(({ type, text, delay = 0 }) => {
            setTimeout(() => {
                const div = document.createElement('div');
                div.className = 'term-line';
                if (type === 'cmd') {
                    div.innerHTML = `<span class="term-p">$</span><span class="term-cmd">${text}</span>`;
                } else {
                    div.innerHTML = `<span class="term-${type}">${text}</span>`;
                }
                body.appendChild(div);
                body.scrollTop = body.scrollHeight;
            }, delay);
        });
        setTimeout(() => {
            const cur = document.createElement('div');
            cur.className = 'term-line';
            cur.innerHTML = `<span class="term-p">$</span><span class="term-cursor"></span>`;
            body.appendChild(cur);
        }, 4800);
    }, { threshold: .4 });
    const term = document.getElementById('terminal');
    if (term) io.observe(term);
}

/* ── THREE.JS ─────────────────────────────────────── */
function initThree() {
    const canvas = document.getElementById('gl');
    if (!canvas) return;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 100);
    camera.position.set(0, 0, 14);

    // ── Lighting ──
    scene.add(new THREE.AmbientLight(0x0a0a1a, 1));
    const sun = new THREE.DirectionalLight(0x7adaff, 1.4);
    sun.position.set(5, 3, 5);
    scene.add(sun);

    // ── Earth (Act I & II) ──
    const earthGeo = new THREE.SphereGeometry(5, 64, 64);
    const earthMat = new THREE.MeshStandardMaterial({
        color: 0x0a2a4a,
        emissive: 0x020d1a,
        emissiveIntensity: 0.4,
        roughness: 0.8,
        metalness: 0.1,
        wireframe: false,
        transparent: true,
        opacity: 0,
    });
    const earth = new THREE.Mesh(earthGeo, earthMat);
    scene.add(earth);

    // Earth atmosphere glow
    const glowGeo = new THREE.SphereGeometry(5.3, 32, 32);
    const glowMat = new THREE.MeshStandardMaterial({
        color: 0x004488,
        transparent: true,
        opacity: 0,
        side: THREE.BackSide,
        emissive: 0x0066aa,
        emissiveIntensity: 0.3,
    });
    const glow = new THREE.Mesh(glowGeo, glowMat);
    scene.add(glow);

    // Dot grid on earth surface
    const dotGeo = new THREE.BufferGeometry();
    const dotCount = 1800;
    const dPos = new Float32Array(dotCount * 3);
    for (let i = 0; i < dotCount; i++) {
        const phi = Math.acos(-1 + (2 * i) / dotCount);
        const theta = Math.sqrt(dotCount * Math.PI) * phi;
        dPos[i * 3] = 5.05 * Math.sin(phi) * Math.cos(theta);
        dPos[i * 3 + 1] = 5.05 * Math.cos(phi);
        dPos[i * 3 + 2] = 5.05 * Math.sin(phi) * Math.sin(theta);
    }
    dotGeo.setAttribute('position', new THREE.BufferAttribute(dPos, 3));
    const dotMat = new THREE.PointsMaterial({ color: 0x00d4ff, size: 0.03, transparent: true, opacity: 0 });
    const dots = new THREE.Points(dotGeo, dotMat);
    scene.add(dots);

    // ── Grid (Act III) ──
    const gridGroup = new THREE.Group();
    const gGeo = new THREE.BufferGeometry();
    const gPos = [];
    for (let x = -8; x <= 8; x += 1) {
        gPos.push(x, -8, 0, x, 8, 0);
        gPos.push(-8, x, 0, 8, x, 0);
    }
    gGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(gPos), 3));
    const gMat = new THREE.LineBasicMaterial({ color: 0x00d4ff, transparent: true, opacity: 0 });
    gridGroup.add(new THREE.LineSegments(gGeo, gMat));

    // Grid nodes
    for (let i = 0; i < 12; i++) {
        const ng = new THREE.SphereGeometry(0.12, 8, 8);
        const nm = new THREE.MeshStandardMaterial({ color: 0x00d4ff, emissive: 0x00d4ff, emissiveIntensity: 0.8, transparent: true, opacity: 0 });
        const n = new THREE.Mesh(ng, nm);
        n.position.set((Math.random() - .5) * 12, (Math.random() - .5) * 10, (Math.random() - .5) * 2);
        gridGroup.add(n);
    }
    gridGroup.rotation.x = 0.3;
    scene.add(gridGroup);

    // ── Neural (Act IV) ──
    const neuralGroup = new THREE.Group();
    const nodePositions = [];
    for (let i = 0; i < 24; i++) {
        nodePositions.push(new THREE.Vector3(
            (Math.random() - .5) * 14,
            (Math.random() - .5) * 10,
            (Math.random() - .5) * 4
        ));
    }
    nodePositions.forEach(pos => {
        const ng = new THREE.SphereGeometry(0.15, 8, 8);
        const nm = new THREE.MeshStandardMaterial({ color: 0x34d399, emissive: 0x34d399, emissiveIntensity: 0.6, transparent: true, opacity: 0 });
        const n = new THREE.Mesh(ng, nm);
        n.position.copy(pos);
        neuralGroup.add(n);
    });
    // neural connections
    const nLinePts = [];
    for (let i = 0; i < nodePositions.length; i++) {
        for (let j = i + 1; j < nodePositions.length; j++) {
            if (nodePositions[i].distanceTo(nodePositions[j]) < 6) {
                nLinePts.push(...nodePositions[i].toArray(), ...nodePositions[j].toArray());
            }
        }
    }
    const nLineGeo = new THREE.BufferGeometry();
    nLineGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(nLinePts), 3));
    const nLineMat = new THREE.LineBasicMaterial({ color: 0x34d399, transparent: true, opacity: 0 });
    neuralGroup.add(new THREE.LineSegments(nLineGeo, nLineMat));
    scene.add(neuralGroup);

    // ── Scene state ──
    let currentScene = 'none';
    const scenes = {
        earth: { objs: [earthMat, glowMat, dotMat], target: [0.85, 0.35, 0.6] },
        grid: { objs: [gMat, ...gridGroup.children.slice(1).map(m => m.material)], target: [0.6] },
        neural: { objs: [nLineMat, ...neuralGroup.children.slice(0, -1).map(m => m.material)], target: [0.4, 0.7] },
    };

    function switchScene(name) {
        if (name === currentScene) return;
        currentScene = name;
        // Fade all out
        ['earth', 'grid', 'neural'].forEach(s => {
            scenes[s].objs.forEach(m => {
                gsap.to(m, { opacity: 0, duration: .6, ease: 'power2.inOut' });
            });
        });
        // Fade target in
        if (scenes[name]) {
            scenes[name].objs.forEach((m, i) => {
                gsap.to(m, { opacity: scenes[name].target[i] ?? scenes[name].target[0], duration: .9, delay: .1, ease: 'power2.inOut' });
            });
        }
    }

    // ── Animate ──
    const clock = new THREE.Clock();
    (function animate() {
        requestAnimationFrame(animate);
        const t = clock.getElapsedTime();
        earth.rotation.y = t * 0.04;
        dots.rotation.y = t * 0.04;
        glow.rotation.y = t * 0.04;
        gridGroup.rotation.z = Math.sin(t * 0.2) * 0.02;
        neuralGroup.rotation.y = t * 0.05;
        renderer.render(scene, camera);
    })();

    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });

    // Expose for GSAP
    window._bessaiSwitchScene = switchScene;
}

/* ── GSAP SCROLL ──────────────────────────────────── */
function initGSAP() {
    // PPM counter for Act I
    const ppmEl = document.getElementById('ppm-val');
    if (ppmEl) {
        ScrollTrigger.create({
            trigger: '#act1',
            start: 'top 80%',
            once: true,
            onEnter: () => {
                gsap.to({ val: 0 }, {
                    val: 424, duration: 2.5, ease: 'power2.out',
                    onUpdate() { ppmEl.textContent = Math.round(this.targets()[0].val); }
                });
            }
        });
    }

    // Scene switching per act — broader triggers for reliability
    const sceneMap = { act1: 'earth', act2: 'earth', act3: 'grid', act4: 'neural' };
    Object.entries(sceneMap).forEach(([id, scene]) => {
        ScrollTrigger.create({
            trigger: '#' + id,
            start: 'top 70%',
            end: 'bottom 30%',
            onEnter: () => window._bessaiSwitchScene?.(scene),
            onEnterBack: () => window._bessaiSwitchScene?.(scene),
        });
    });

    // Initial scene
    window._bessaiSwitchScene?.('earth');

    // Text reveals in acts
    document.querySelectorAll('.split-text').forEach(el => {
        gsap.fromTo(el,
            { opacity: 0, y: 30 },
            {
                opacity: 1, y: 0, duration: 1, ease: 'power3.out',
                scrollTrigger: { trigger: el, start: 'top 85%', once: true }
            }
        );
    });

    // Camera gentle parallax
    ScrollTrigger.create({
        trigger: 'body',
        start: 'top top',
        end: 'bottom bottom',
        scrub: true,
        onUpdate(self) {
            const cam = window.__bessaiCamera;
            if (cam) cam.position.y = -self.progress * 2;
        }
    });
}

/* ── CHART.JS DASHBOARD ───────────────────────────── */
function initDashboard() {
    const ctx = document.getElementById('dash-chart');
    if (!ctx) return;

    const labels = Array.from({ length: 20 }, (_, i) => i);
    const socData = labels.map(() => 60 + Math.random() * 25);
    const pwData = labels.map(() => (Math.random() - .5) * 400);

    const chart = new Chart(ctx, {
        data: {
            labels,
            datasets: [
                {
                    type: 'line',
                    label: 'SoC %',
                    data: [...socData],
                    borderColor: '#00d4ff',
                    backgroundColor: 'rgba(0,212,255,.06)',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'ySoc',
                },
                {
                    type: 'bar',
                    label: 'Power kW',
                    data: pwData.map(v => v / 10),
                    backgroundColor: pwData.map(v => v >= 0 ? 'rgba(52,211,153,.5)' : 'rgba(249,115,22,.5)'),
                    borderWidth: 0,
                    yAxisID: 'yPw',
                },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            animation: { duration: 0 },
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            scales: {
                x: { display: false },
                ySoc: { position: 'left', min: 0, max: 100, ticks: { color: '#5a6480', font: { size: 9, family: 'JetBrains Mono' }, maxTicksLimit: 4 }, grid: { color: 'rgba(255,255,255,.03)' } },
                yPw: { position: 'right', ticks: { display: false }, grid: { display: false } },
            }
        }
    });

    const $id = id => document.getElementById(id);

    setInterval(() => {
        const lang = localStorage.getItem('lang') || 'es';
        const soc = Math.max(20, Math.min(100, socData.at(-1) + (Math.random() - .45) * 4));
        const pw = Math.max(-500, Math.min(500, pwData.at(-1) + (Math.random() - .5) * 55));
        const cmg = 70 + Math.random() * 80;
        socData.shift(); socData.push(soc);
        pwData.shift(); pwData.push(pw);
        chart.data.datasets[0].data = [...socData];
        chart.data.datasets[1].data = pwData.map(v => v / 10);
        chart.data.datasets[1].backgroundColor = pwData.map(v => v >= 0 ? 'rgba(52,211,153,.5)' : 'rgba(249,115,22,.5)');
        chart.update('none');

        if ($id('kpi-soc')) $id('kpi-soc').textContent = soc.toFixed(1) + '%';
        if ($id('kpi-soc-d')) {
            const up = T[lang]?.['dash.socd.up'] || '↑ cargando';
            const dn = T[lang]?.['dash.socd.dn'] || '↓ descargando';
            $id('kpi-soc-d').textContent = soc > 70 ? up : dn;
            $id('kpi-soc-d').className = 'kpi-delta ' + (soc > 70 ? 'up' : 'dn');
        }
        if ($id('kpi-pw')) $id('kpi-pw').textContent = (pw >= 0 ? '+' : '') + Math.round(pw) + ' kW';
        if ($id('kpi-pw-d')) {
            const up = T[lang]?.['dash.pwd.up'] || '↑ inyectando';
            const dn = T[lang]?.['dash.pwd.dn'] || '↓ cargando';
            $id('kpi-pw-d').textContent = pw > 0 ? up : dn;
            $id('kpi-pw-d').className = 'kpi-delta ' + (pw > 0 ? 'up' : 'dn');
        }
        if ($id('kpi-cmg')) $id('kpi-cmg').textContent = '$' + Math.round(cmg);
        if ($id('kpi-lat')) $id('kpi-lat').textContent = (1.5 + Math.random() * 3).toFixed(1) + 'ms';
    }, 2000);
}
