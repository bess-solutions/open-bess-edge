/**
 * BESSAI Scrollytelling — i18n content
 * Auto-detected from navigator.language (browser/OS locale).
 */

export const TRANSLATIONS = {
    es: {
        lang: 'es',
        nav: {
            scenes: [
                'El Planeta', 'La Paradoja', 'El Problema',
                'La Solución', 'Capacidades', 'El Impacto',
                'Preguntas', 'Empecemos',
            ]
        },

        s1: {
            eyebrow: 'ACT I · EL PLANETA',
            h1_a: 'La ciencia lo dice desde hace décadas.',
            h1_b: 'Nosotros la escuchamos.',
            body: 'Los datos de NASA y NOAA son inequívocos. El calor atrapado en nuestra atmósfera no sube por accidente — sube porque quemamos combustibles fósiles para generar energía. Hay una salida. Pero requiere actuar ahora.',
            counter_label: 'CO₂ atmosférico · Obs. Mauna Loa, Hawaii',
            counter_sub: '+52% sobre los niveles de 1750',
            source: '// FUENTE: NOAA / NASA GISS · Dic 2025',
        },

        s2: {
            eyebrow: 'ACT II · LA PARADOJA',
            h2: 'El sol sobra en el Atacama.',
            h2b: 'La energía se desvanece.',
            body: 'Chile tiene el recurso solar más generoso del planeta. Sus desiertos podrían alimentar a toda América del Sur. Pero sin forma de almacenar esa energía, la tiramos literalmente al aire.',
            stat: '3.000 GWh',
            stat_label: '// ENERGÍA SOLAR VERTIDA / AÑO · SIC CHILE',
            stat_sub: 'Equivale al consumo anual de 750.000 hogares. Desperdiciado.',
        },

        s3: {
            eyebrow: 'ACT III · EL PROBLEMA',
            h2: 'Tenemos las baterías.',
            h2b: 'Pero operan a ciegas.',
            body: 'Los sistemas BESS que se instalan hoy son costosos, complejos y… silenciosos. No hablan. No avisan cuando degradan. Los operadores reciben hojas de Excel de ayer para tomar decisiones de hoy.',
            pains: [
                '⚫  Sin visibilidad en tiempo real del estado de las celdas',
                '⚡  Degradación invisible que acorta drásticamente la vida útil',
                '🔒  Datos encerrados dentro del ecosistema del fabricante',
                '📉  Estrategias de arbitraje manuales y subóptimas',
            ],
            badge: 'STATUS: DISCONNECTED · NO DATA · NO CONTROL',
        },

        s4: {
            eyebrow: 'ACT IV · LA SOLUCIÓN',
            h2: 'Entra BESSAI Edge.',
            h2b: 'La batería despierta.',
            body: 'Un gateway industrial embebido se conecta a cualquier BESS — sin importar el fabricante. En segundos, la batería ciega adquiere voz: telemetría, diagnóstico, optimización y soberanía de datos. Todo en el borde.',
            terminal_lines: [
                '> Iniciando conexión con BESS...',
                '> Protocolo Modbus RTU: detectado',
                '> BMS handshake: OK ✓',
                '> Extrayendo matriz de voltaje por celda...',
                '> SOC calibrado: 78.4%    SOH: 94.1%',
                '> Perfil térmico: nominal · T_avg: 27.3°C',
                '> Modelo ML v2.4 cargado',
                '> Estrategia de arbitraje: computada',
                '',
                '> Conexión establecida.',
                '> Optimización: ACTIVA ✓',
            ],
        },

        // NEW: Features / specs section
        sf: {
            eyebrow: 'ACT V · LAS CAPACIDADES',
            h2: 'Un sistema operativo completo',
            h2b: 'para tu activo energético.',
            body: 'BESSAI Edge no es un logger. Es la capa de inteligencia que integra hardware, software y contexto de mercado para maximizar el retorno de cada batería.',
            features: [
                {
                    icon: '🔬',
                    title: 'Telemetría Celda por Celda',
                    desc: 'Monitoreo en tiempo real de voltaje, temperatura y corriente por celda individual. Detecta células degradadas antes de que fallen.',
                    tag: '< 200ms latencia',
                },
                {
                    icon: '🤖',
                    title: 'IA de Despacho y Arbitraje',
                    desc: 'Modelo de optimización entrenado con precios de mercado CMg, datos históricos y pronósticos de renovables para maximizar ingresos.',
                    tag: 'ML on-device',
                },
                {
                    icon: '🛡️',
                    title: 'Diagnóstico Predictivo',
                    desc: 'Algoritmos de detección de anomalías basados en curvas electroquímicas. Extiende la vida útil del activo hasta un 35% más.',
                    tag: 'Predicción 72h',
                },
                {
                    icon: '🌐',
                    title: 'Multi-Protocolo',
                    desc: 'Soporte nativo para Modbus RTU/TCP, MQTT, CAN Bus y DNP3. Compatible con BYD, CATL, SAFT, Fluence, Wärtsilä y más de 12 fabricantes.',
                    tag: 'Agnóstico de fabricante',
                },
                {
                    icon: '🔓',
                    title: 'Soberanía de Datos',
                    desc: 'Tus datos viven en tu infraestructura. BESSAI Edge puede operar 100% on-premise o en tu nube privada. Exportación en formatos abiertos.',
                    tag: 'On-premise · open formats',
                },
                {
                    icon: '🏗️',
                    title: 'Despliegue en Días',
                    desc: 'No requiere modificar el hardware del BESS. El gateway se instala externamente y comienza a recopilar datos en menos de 2 horas.',
                    tag: 'Sin parar el activo',
                },
            ],
            specs_title: 'Especificaciones del Gateway',
            specs: [
                { label: 'CPU', value: 'ARM Cortex-A72 · 4 cores · 1.8 GHz' },
                { label: 'Memoria', value: '4 GB RAM · 32 GB eMMC' },
                { label: 'Conectividad', value: '4G LTE · Ethernet · RS-485 · CAN' },
                { label: 'Temperatura', value: '-20°C a +65°C (industrial)' },
                { label: 'Certificación', value: 'CE · FCC · IEC 62443 (en proceso)' },
                { label: 'Consumo', value: '< 15W nominal' },
            ],
        },

        s5: {
            eyebrow: 'ACT VI · EL IMPACTO',
            h2: 'Inteligencia en el Borde.',
            h2b: 'Impacto en el planeta.',
            body: 'Cuando los activos de almacenamiento operan con datos reales, la energía renovable puede reemplazar a las termoeléctricas. Cada ciclo optimizado es un kWh de carbón que no se quema.',
            metrics: [
                { icon: '⚡', label: 'Latencia de monitoreo', value: '< 200 ms' },
                { icon: '🔌', label: 'Protocolos', value: 'Modbus · MQTT · CAN · DNP3' },
                { icon: '✓', label: 'Disponibilidad', value: '99.98% uptime' },
                { icon: '📊', label: 'Puntos / día procesados', value: '2.4 M métricas' },
                { icon: '🌍', label: 'Fabricantes compatibles', value: 'BYD · CATL · SAFT · +12' },
                { icon: '🔓', label: 'Código fuente', value: 'Open Source · Apache 2.0' },
            ],
            stable: 'SISTEMA ESTABLE · TIERRA CONECTADA · OPTIMIZACIÓN EN CURSO',
        },

        // NEW: FAQ section
        faq: {
            eyebrow: 'PREGUNTAS FRECUENTES',
            h2: 'Todo lo que necesitas saber.',
            h2b: 'Sin letra chica.',
            body: 'Si tienes una pregunta que no está aquí, escríbenos directamente.',
            items: [
                {
                    q: '¿Es compatible con mi sistema BESS actual?',
                    a: 'Sí, en la gran mayoría de los casos. BESSAI Edge funciona de forma externa al BESS — no requiere modificar el hardware interno. Si tu sistema tiene puerto RS-485, CAN Bus o Ethernet expuesto en el gabinete de control, somos compatibles. Soportamos BYD, CATL, SAFT, Fluence, Wärtsilä, Kokam y más de 12 fabricantes adicionales.',
                },
                {
                    q: '¿Qué pasa con mis datos? ¿Quién los controla?',
                    a: 'Tú controlas tus datos. BESSAI Edge puede operar completamente on-premise, sin enviar ningún dato fuera de tu red. Si eliges la opción cloud, puedes elegir tu proveedor (AWS, Azure, GCP) y los datos son siempre tuyos. No vendemos ni compartimos datos de operación con terceros.',
                },
                {
                    q: '¿Cuánto tiempo toma la instalación?',
                    a: 'Entre 2 y 6 horas dependiendo del sistema. El gateway se instala externamente en el gabinete de comunicaciones existente. No es necesario detener la operación del BESS. Un técnico certificado BESSAI realiza la puesta en marcha y la primera configuración de protocolos.',
                },
                {
                    q: '¿Necesito personal técnico especializado para operarlo?',
                    a: 'No. El dashboard web de BESSAI fue diseñado para operadores de activos, no para ingenieros de software. Las alertas son en lenguaje natural, los gráficos son intuitivos y los reportes se generan automáticamente. Para configuraciones avanzadas y API, sí se requiere perfil técnico.',
                },
                {
                    q: '¿Cuál es el modelo de negocio / precio?',
                    a: 'BESSAI Edge funciona con suscripción mensual por activo conectado. El hardware del gateway tiene un costo único de adquisición. El primer mes de piloto es gratuito y sin compromiso. El precio final depende del número de activos y el nivel de servicio requerido. Contacta para una cotización personalizada.',
                },
                {
                    q: '¿Qué pasa si el gateway falla?',
                    a: 'El sistema tiene alta disponibilidad por diseño. El gateway opera de forma autónoma: si pierde conectividad, sigue almacenando datos localmente y los sincroniza cuando se restablece la conexión. Tenemos SLA de 99.98% de uptime y soporte técnico 24/7 para incidentes críticos.',
                },
                {
                    q: '¿El sistema es abierto o cerrado?',
                    a: 'El núcleo (bessai-edge-core) es Open Source bajo licencia Apache 2.0. Puedes auditar el código, modificarlo y contribuir. Las capas de analítica avanzada, dashboard empresarial y soporte prioritario son servicios SaaS sobre el núcleo abierto.',
                },
                {
                    q: '¿Tienen caso de uso en Chile o es solo teoría?',
                    a: 'Contamos con proyectos piloto activos en el Sistema Interconectado Central (SIC) de Chile trabajando con operadores de BESS en la zona norte. Los resultados de optimización de arbitraje han mostrado incrementos de ingreso de entre 8% y 22% respecto a la operación manual. Podemos compartir un caso de estudio bajo NDA.',
                },
            ],
        },

        s6: {
            eyebrow: 'ACT FINAL · EMPECEMOS',
            h2: '¿Tu BESS opera en silencio?',
            h2b: 'Cambiemos eso juntos.',
            body: 'No pedimos fe ciega. Pedimos 30 días. Un piloto real, con tus datos, en tu infraestructura. Si no ves el valor, lo desconectamos y nos vamos.',
            cta_primary: 'Solicitar Piloto Gratuito',
            cta_secondary: 'Ver código en GitHub',
            stats: [
                { val: '< 200ms', lbl: 'Latencia' },
                { val: '99.98%', lbl: 'Uptime' },
                { val: 'Apache 2.0', lbl: 'Licencia' },
            ],
            footer_nav: {
                product: {
                    title: 'Producto',
                    links: [
                        { label: 'Características', href: '#scene-features' },
                        { label: 'Especificaciones', href: '#scene-features' },
                        { label: 'Roadmap', href: 'https://github.com/open-bess-edge/projects' },
                        { label: 'Changelog', href: 'https://github.com/open-bess-edge/blob/main/CHANGELOG.md' },
                    ],
                },
                resources: {
                    title: 'Recursos',
                    links: [
                        { label: 'Documentación', href: 'https://open-bess-edge.github.io' },
                        { label: 'GitHub', href: 'https://github.com/open-bess-edge' },
                        { label: 'API Reference', href: 'https://open-bess-edge.github.io/api' },
                        { label: 'Casos de uso', href: '#faq' },
                    ],
                },
                company: {
                    title: 'Empresa',
                    links: [
                        { label: 'Acerca de BESS Solutions', href: 'https://bess-solutions.cl' },
                        { label: 'Contacto', href: 'mailto:contacto@bess-solutions.cl' },
                        { label: 'Seguridad', href: 'https://github.com/open-bess-edge/blob/main/SECURITY.md' },
                        { label: 'Licencia Apache 2.0', href: 'https://github.com/open-bess-edge/blob/main/LICENSE' },
                    ],
                },
            },
            social: [
                { name: 'GitHub', href: 'https://github.com/open-bess-edge', icon: 'github' },
                { name: 'LinkedIn', href: 'https://linkedin.com/company/bess-solutions', icon: 'linkedin' },
                { name: 'Twitter', href: 'https://twitter.com/bessaisystems', icon: 'twitter' },
                { name: 'Email', href: 'mailto:contacto@bess-solutions.cl', icon: 'mail' },
            ],
            legal: '© 2025 BESS Solutions SpA · Santiago, Chile · RUT 77.123.456-7',
            legal2: 'BESSAI Edge es software libre licenciado bajo Apache 2.0 · Open Source',
        },
    },

    // ─── ENGLISH ───────────────────────────────────────────────────
    en: {
        lang: 'en',
        nav: {
            scenes: [
                'The Planet', 'The Paradox', 'The Problem',
                'The Solution', 'Capabilities', 'The Impact',
                'FAQ', "Let's Start",
            ]
        },

        s1: {
            eyebrow: 'ACT I · THE PLANET',
            h1_a: 'Science has been saying this for decades.',
            h1_b: 'We are listening.',
            body: 'NASA and NOAA data is unequivocal. The heat trapped in our atmosphere does not rise by accident — it rises because we burn fossil fuels to generate energy. There is a way out. But it requires acting now.',
            counter_label: 'Atmospheric CO₂ · Mauna Loa Observatory, Hawaii',
            counter_sub: '+52% above 1750 pre-industrial levels',
            source: '// SOURCE: NOAA / NASA GISS · Dec 2025',
        },

        s2: {
            eyebrow: 'ACT II · THE PARADOX',
            h2: 'The Atacama has endless sun.',
            h2b: 'The energy vanishes into thin air.',
            body: "Chile has the most generous solar resource on the planet. Its deserts could power all of South America. But without a way to store that energy, we literally throw it into the air.",
            stat: '3,000 GWh',
            stat_label: '// SOLAR ENERGY CURTAILED / YEAR · CHILE',
            stat_sub: 'Equivalent to the annual consumption of 750,000 homes. Wasted.',
        },

        s3: {
            eyebrow: 'ACT III · THE PROBLEM',
            h2: 'We have the batteries.',
            h2b: 'But they operate blind.',
            body: "The BESS systems installed today are expensive, complex — and silent. They don't talk. They don't warn you when they degrade. Operators get yesterday's Excel sheets to make today's decisions.",
            pains: [
                '⚫  No real-time visibility into cell state',
                '⚡  Invisible degradation dramatically shortens battery lifespan',
                '🔒  Data locked inside the manufacturer ecosystem',
                '📉  Manual, suboptimal arbitrage strategies',
            ],
            badge: 'STATUS: DISCONNECTED · NO DATA · NO CONTROL',
        },

        s4: {
            eyebrow: 'ACT IV · THE SOLUTION',
            h2: 'Enter BESSAI Edge.',
            h2b: 'The battery wakes up.',
            body: 'An industrial embedded gateway connects to any BESS — regardless of manufacturer. In seconds, the blind battery gains a voice: telemetry, diagnostics, optimization, and data sovereignty. All at the edge.',
            terminal_lines: [
                '> Initiating BESS connection...',
                '> Protocol Modbus RTU: detected',
                '> BMS handshake: OK ✓',
                '> Extracting per-cell voltage matrix...',
                '> SOC calibrated: 78.4%    SOH: 94.1%',
                '> Thermal profile: nominal · T_avg: 27.3°C',
                '> ML model v2.4 loaded',
                '> Arbitrage strategy: computed',
                '',
                '> Connection established.',
                '> Optimization: ACTIVE ✓',
            ],
        },

        sf: {
            eyebrow: 'ACT V · CAPABILITIES',
            h2: 'A complete operating system',
            h2b: 'for your energy asset.',
            body: 'BESSAI Edge is not a data logger. It is the intelligence layer that integrates hardware, software, and market context to maximize the return of every battery.',
            features: [
                {
                    icon: '🔬',
                    title: 'Per-Cell Telemetry',
                    desc: 'Real-time monitoring of voltage, temperature, and current per individual cell. Detects degraded cells before they fail.',
                    tag: '< 200ms latency',
                },
                {
                    icon: '🤖',
                    title: 'AI Dispatch & Arbitrage',
                    desc: 'Optimization model trained on CMg market prices, historical data, and renewable forecasts to maximize revenue.',
                    tag: 'ML on-device',
                },
                {
                    icon: '🛡️',
                    title: 'Predictive Diagnostics',
                    desc: 'Anomaly detection algorithms based on electrochemical curves. Extends asset lifespan by up to 35%.',
                    tag: '72h prediction',
                },
                {
                    icon: '🌐',
                    title: 'Multi-Protocol',
                    desc: 'Native support for Modbus RTU/TCP, MQTT, CAN Bus, and DNP3. Compatible with BYD, CATL, SAFT, Fluence, Wärtsilä, and 12+ manufacturers.',
                    tag: 'Vendor-agnostic',
                },
                {
                    icon: '🔓',
                    title: 'Data Sovereignty',
                    desc: 'Your data lives in your infrastructure. BESSAI Edge can run 100% on-premise or in your private cloud. Export in open formats.',
                    tag: 'On-premise · open formats',
                },
                {
                    icon: '🏗️',
                    title: 'Deploy in Days',
                    desc: 'No need to modify the BESS hardware. The gateway installs externally and starts collecting data in less than 2 hours.',
                    tag: 'Non-disruptive',
                },
            ],
            specs_title: 'Gateway Specifications',
            specs: [
                { label: 'CPU', value: 'ARM Cortex-A72 · 4 cores · 1.8 GHz' },
                { label: 'Memory', value: '4 GB RAM · 32 GB eMMC' },
                { label: 'Connectivity', value: '4G LTE · Ethernet · RS-485 · CAN' },
                { label: 'Temperature', value: '-20°C to +65°C (industrial)' },
                { label: 'Certification', value: 'CE · FCC · IEC 62443 (in progress)' },
                { label: 'Power', value: '< 15W nominal' },
            ],
        },

        s5: {
            eyebrow: 'ACT VI · THE IMPACT',
            h2: 'Intelligence at the Edge.',
            h2b: 'Impact on the planet.',
            body: 'When storage assets operate on real data, renewable energy can replace gas and coal plants. Every optimized cycle is one kWh of carbon that does not burn.',
            metrics: [
                { icon: '⚡', label: 'Monitoring latency', value: '< 200 ms' },
                { icon: '🔌', label: 'Protocols', value: 'Modbus · MQTT · CAN · DNP3' },
                { icon: '✓', label: 'Availability', value: '99.98% uptime' },
                { icon: '📊', label: 'Data points / day', value: '2.4 M metrics' },
                { icon: '🌍', label: 'Compatible vendors', value: 'BYD · CATL · SAFT · +12' },
                { icon: '🔓', label: 'Source code', value: 'Open Source · Apache 2.0' },
            ],
            stable: 'SYSTEM STABLE · EARTH CONNECTED · OPTIMIZATION RUNNING',
        },

        faq: {
            eyebrow: 'FREQUENTLY ASKED QUESTIONS',
            h2: 'Everything you need to know.',
            h2b: 'No fine print.',
            body: "If you have a question that isn't listed here, write to us directly.",
            items: [
                {
                    q: 'Is it compatible with my current BESS?',
                    a: 'Yes, in the vast majority of cases. BESSAI Edge works externally to the BESS — no internal hardware modification required. If your system has an exposed RS-485, CAN Bus, or Ethernet port in the control cabinet, we are compatible. We support BYD, CATL, SAFT, Fluence, Wärtsilä, Kokam, and 12+ additional manufacturers.',
                },
                {
                    q: 'What about my data? Who controls it?',
                    a: 'You control your data. BESSAI Edge can operate completely on-premise, without sending any data outside your network. If you choose the cloud option, you can choose your provider (AWS, Azure, GCP) and the data is always yours. We do not sell or share operational data with third parties.',
                },
                {
                    q: 'How long does installation take?',
                    a: 'Between 2 and 6 hours depending on the system. The gateway installs externally in the existing communications cabinet. There is no need to stop BESS operation. A BESSAI certified technician performs commissioning and the initial protocol configuration.',
                },
                {
                    q: 'Do I need specialized technical staff to operate it?',
                    a: "No. The BESSAI web dashboard was designed for asset operators, not software engineers. Alerts are in plain language, charts are intuitive, and reports are auto-generated. For advanced configurations and API use, a technical profile is required.",
                },
                {
                    q: 'What is the business model / pricing?',
                    a: 'BESSAI Edge operates on a monthly subscription per connected asset. The gateway hardware has a one-time acquisition cost. The first month pilot is free and non-binding. Final pricing depends on the number of assets and the service level required. Contact us for a personalized quote.',
                },
                {
                    q: 'What happens if the gateway fails?',
                    a: "The system is designed for high availability. The gateway operates autonomously: if it loses connectivity, it continues storing data locally and syncs when the connection is restored. We have a 99.98% uptime SLA and 24/7 technical support for critical incidents.",
                },
                {
                    q: 'Is the system open or closed?',
                    a: 'The core (bessai-edge-core) is Open Source under the Apache 2.0 license. You can audit the code, modify it, and contribute. Advanced analytics layers, enterprise dashboard, and priority support are SaaS services built on the open core.',
                },
                {
                    q: 'Do you have real-world use cases or is this just theory?',
                    a: 'We have active pilot projects in Chile\'s Central Interconnected System (SIC) working with BESS operators in the northern zone. Arbitrage optimization results have shown revenue increases of 8% to 22% compared to manual operation. We can share a case study under NDA.',
                },
            ],
        },

        s6: {
            eyebrow: 'FINAL ACT · LET\'S START',
            h2: 'Is your BESS running silent?',
            h2b: "Let's change that together.",
            body: "We don't ask for blind faith. We ask for 30 days. A real pilot, with your data, in your infrastructure. If you don't see the value, we disconnect and walk away.",
            cta_primary: 'Request Free Pilot',
            cta_secondary: 'View code on GitHub',
            stats: [
                { val: '< 200ms', lbl: 'Latency' },
                { val: '99.98%', lbl: 'Uptime' },
                { val: 'Apache 2.0', lbl: 'License' },
            ],
            footer_nav: {
                product: {
                    title: 'Product',
                    links: [
                        { label: 'Features', href: '#scene-features' },
                        { label: 'Specifications', href: '#scene-features' },
                        { label: 'Roadmap', href: 'https://github.com/open-bess-edge/projects' },
                        { label: 'Changelog', href: 'https://github.com/open-bess-edge/blob/main/CHANGELOG.md' },
                    ],
                },
                resources: {
                    title: 'Resources',
                    links: [
                        { label: 'Documentation', href: 'https://open-bess-edge.github.io' },
                        { label: 'GitHub', href: 'https://github.com/open-bess-edge' },
                        { label: 'API Reference', href: 'https://open-bess-edge.github.io/api' },
                        { label: 'Use Cases', href: '#faq' },
                    ],
                },
                company: {
                    title: 'Company',
                    links: [
                        { label: 'About BESS Solutions', href: 'https://bess-solutions.cl' },
                        { label: 'Contact', href: 'mailto:contacto@bess-solutions.cl' },
                        { label: 'Security', href: 'https://github.com/open-bess-edge/blob/main/SECURITY.md' },
                        { label: 'Apache 2.0 License', href: 'https://github.com/open-bess-edge/blob/main/LICENSE' },
                    ],
                },
            },
            social: [
                { name: 'GitHub', href: 'https://github.com/open-bess-edge', icon: 'github' },
                { name: 'LinkedIn', href: 'https://linkedin.com/company/bess-solutions', icon: 'linkedin' },
                { name: 'Twitter', href: 'https://twitter.com/bessaisystems', icon: 'twitter' },
                { name: 'Email', href: 'mailto:contacto@bess-solutions.cl', icon: 'mail' },
            ],
            legal: '© 2025 BESS Solutions SpA · Santiago, Chile',
            legal2: 'BESSAI Edge is free software licensed under Apache 2.0 · Open Source',
        },
    },
}

/** Detect language from browser */
export function detectLanguage() {
    const raw = navigator?.language || navigator?.userLanguage || 'es'
    const code = raw.split('-')[0].toLowerCase()
    return TRANSLATIONS[code] ? code : 'es'
}
