# CHANGELOG — BESS Solutions Website

Todos los cambios notables del sitio web de BESS Solutions.
Formato: [Keep a Changelog](https://keepachangelog.com/es/1.0.0/) · Versionado semántico.

---

## [2.0.0] — 2026-02-25

### Refactorización completa — Proyecto estructurado y multilenguaje

**Arquitectura:**
- Nuevo árbol de fuentes `src/` separado del build output `dist/`
- `build.ps1` — script de build que combina CSS + JS en un único `dist/index.html` autocontenido
- Deploy workflow actualizado: build automático antes del FTP en GitHub Actions

**Multilenguaje (i18n):**
- Motor i18n en `src/js/i18n.js` — lazy-fetch por idioma, `data-i18n` attrs, `localStorage`
- `i18n/es.json` — todos los strings en español (100% cobertura)
- `i18n/en.json` — todos los strings en inglés (100% cobertura)
- Language switcher ES/EN en el nav — persistido en localStorage

**CSS modular:**
- `src/css/base.css` — reset, tokens CSS, tipografía, grid background, utilidades, botones
- `src/css/layout.css` — nav, hero, live strip, audience tabs, stats, features, terminal, community, roadmap, early adopter, footer
- `src/css/responsive.css` — breakpoints 1024/768/480px + music player flotante

**HTML template:**
- `src/index.html` — estructura semántica con `data-i18n` en todos los textos
- SEO: Open Graph, Twitter Card, meta description, favicon SVG
- Assets en `src/assets/` (logo-bess.png, favicon.svg)

**JavaScript:**
- `src/js/i18n.js` — motor de traducción con `I18N.switchTo(lang)`
- `src/js/main.js` — frases rotativas, audience tabs (dinámicos con i18n), live metrics, terminal boot, scroll reveal, nav hamburger, music player

**Build:**
- `dist/index.html` — output autocontenido (75 KB), CSS + JS inlineados
- `dist/assets/` — logo y favicon
- `dist/i18n/*.json` — JSONs para switch de idioma en runtime (fetch)

---

## [1.3.0] — 2026-02-25

### Reproductor de música flotante

- Reproductor flotante (esquina inferior derecha) con la canción *"BESS Solutions in the House"* (Phonk Chilean, Suno AI)
- Audio desde CDN directo de Suno (sin iframes)
- Play/Pause, barra de progreso clickeable, botón cerrar, link a Suno

---

## [1.2.0] — 2026-02-25

### v3 Dinámica — Audience tabs + frases rotativas + live metrics

- 5 audiencias con contenido específico (tabs interactivos)
- Frases rotativas en el hero (6 frases, crossfade cada 3.2s)
- Live strip con métricas que cambian cada 3 segundos
- Terminal animada con boot sequence real de BESSAI
- Sección "El Problema" con datos duros (38% CAGR, $2.4B TAM, 4.2% MAPE)
- Early Adopter con urgencia (8 cupos, sin segundas rondas)

---

## [1.1.0] — 2026-02-25

### Deploy automatizado — GitHub Actions FTP

- Workflow `deploy-website.yml` — deploy automático a cPanel vía FTPS
- Disparable manualmente desde GitHub Actions tab

---

## [1.0.0] — 2026-02-24

### Lanzamiento inicial

- Landing page BESS Solutions con hero, features, stack, comunidad, roadmap y early adopter
- Diseño dark mode con grid background, tipografía Inter + JetBrains Mono
- Botones CTA, scroll reveal, nav sticky
