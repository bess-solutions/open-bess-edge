# Estrategia de Alojamiento y Despliegue Híbrido — Open BESS Edge

Este documento detalla la estrategia de infraestructura y alojamiento oficial para **Open BESS Edge**, optimizando la visibilidad en la comunidad de código abierto, la mantenibilidad de la documentación y la escalabilidad del Servidor MCP.

---

## 🏛️ 1. Código Fuente y Control de Versiones: GitHub

El núcleo del estándar se aloja en **GitHub** como repositorio central público:
* **URL Principal**: [github.com/bess-solutions/open-bess-edge](https://github.com/bess-solutions/open-bess-edge).
* **Propósito**: Canalizar contribuciones, automatizar control de calidad mediante **GitHub Actions** (CI/CD) y centralizar discusiones técnicas mediante Issues y Projects.
* **Soberanía y Redundancia (GitLab Self-Hosted)**: Como plan de contingencia corporativo o para entornos cerrados donde los operadores requieran soberanía absoluta del código, se proveerá una guía de migración/sincronización a instancias GitLab locales.

---

## 📚 2. Documentación Técnica: Read the Docs

La documentación técnica y de arquitectura del estándar debe ser limpia, versionable y auto-actualizable:
* **Plataforma**: **Read the Docs** (versión gratuita para proyectos Open Source).
* **Flujo de Integración**: Se activa un webhook que recompila y despliega la documentación automáticamente a partir de los archivos Markdown del directorio `docs/` en cada push a la rama principal (`main` o `feat/...`).
* **Fallback (GitHub Pages)**: Hospedaje alternativo integrado directamente en el repositorio usando Jekyll/MkDocs para desarrollos intermedios y de pre-lanzamiento.

---

## 🖥️ 3. Servidor MCP (Model Context Protocol): Despliegue Híbrido

El servidor MCP opera en un modelo dual para satisfacer tanto el desarrollo local como la integración centralizada en la nube:

### A. Ejecución Local (STDIO)
* **Destinatario**: Desarrolladores, integradores de sistemas y operadores en terreno.
* **Acceso**: Automatizado mediante los scripts `demo.sh` y `demo.ps1` del repositorio, exponiendo las herramientas sobre flujos de entrada/salida estándar para herramientas como Claude Desktop.

### B. Despliegue Remoto y SaaS (HTTP/SSE)
* **Plataformas de Producción (Render / Fly.io)**: Alojan contenedores Docker ligeros ejecutando el servidor MCP para su integración con el SaaS corporativo de monitoreo continuo.
* **Demostración Pública (Hugging Face Spaces)**: Espacio interactivo y gratuito configurado bajo protocolo Server-Sent Events (SSE) para permitir a potenciales early adopters testear el servidor MCP de forma inmediata sin realizar descargas ni configuraciones locales.

---

## 📢 4. Canales de Marketing y Comunicación

* **Sitio Web Corporativo (`openbessedge.io`)**: Landing page comercial y técnica de cara al cliente B2B, donde se publica el One-Pager, comunicados de prensa de lanzamientos y accesos al programa de Early Adopters.
* **Redes Profesionales (LinkedIn / X)**: Canales de engagement, anuncios regulatorios (CEN, SEC Chile) y actualizaciones técnicas para mantener informados a los operadores del Swarm.

---

## 💎 Resumen de la Arquitectura de Alojamiento

| Componente | Plataforma Recomendada | Propósito / Alcance |
| :--- | :--- | :--- |
| **Código Fuente** | **GitHub** | Repositorio principal, control de versiones, CI/CD, gestión de incidencias. |
| **Documentación** | **Read the Docs** | Portal técnico profesional, auto-actualizable y accesible globalmente. |
| **Servidor MCP** | **Local (STDIO) + Render / Fly.io (SSE/HTTP)** | Ejecución local en gateway OT y despliegue en nube para plataformas SaaS. |
| **Demostración MCP** | **Hugging Face Spaces** | Espacio de pruebas rápido para early adopters mediante SSE. |
| **Marketing** | **Web propio + LinkedIn** | One-pager comercial, prensa y posicionamiento de marca. |
