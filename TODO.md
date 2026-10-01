# Lista de Tareas y Hoja de Ruta — Open BESS Edge

Última actualización: 2026-10-01

---

## 📌 Próximas Tareas Inmediatas (Siguiente Sesión)

### 1. Integración con Discord
- [ ] **Configuración de Conexión Discord**:
  - **Opción A (Recomendada - Bidireccional MCP)**:
    1. Crear aplicación Bot en [Discord Developer Portal](https://discord.com/developers/applications) con cuenta personal.
    2. Copiar `DISCORD_BOT_TOKEN` y habilitar Gateway Intents.
    3. Configurar servidor MCP de Discord en Antigravity (`~/.gemini/config/mcp_config.json` con `@modelcontextprotocol/server-discord`).
  - **Opción B (Inmediata - Webhook)**:
    1. Crear Webhook en canal de Discord (Ajustes de Canal > Integraciones > Webhooks).
    2. Configurar variable `DISCORD_WEBHOOK_URL` en `.env`.
    3. Habilitar despachador de eventos críticos en Python para alertas de envolvente `BESS-GUARD` y contingencias FFR.
- [ ] **Comunidad BESS Solutions**:
  - [ ] Crear servidor institucional o canal oficial de BESS Solutions en Discord.
  - [ ] Generar enlace de invitación permanente y actualizar `README.md`, `README.es.md` y `docs/dwg_obe_2026.html`.

---

## 🔬 Hitos de Homologación y Validación Física

- [ ] **Protocolo de Banco Físico / HIL (72 horas)**:
  - Ensayo continuo de 72 horas conectado a inversor comercial (Huawei SUN2000 / SMA Tripower / Ingeteam).
  - Verificación de tiempo de respuesta FFR < 500 ms ante escalón de frecuencia sintética (49.65 Hz).
  - Verificación de 0 disparos espurios en envolvente de seguridad (`BESS-GUARD-001` a `091`).
- [ ] **Validación de Soporte Dinámico de Reactivos (LVRT / Q-Priority)**:
  - Ensayar respuesta de corriente reactiva inductiva/capacitiva ante hueco de tensión simulado ($V < 0.85\text{ p.u.}$).
  - Comprobar reducción automática de consigna de potencia activa $P$ para priorizar $Q$ según círculo de capacidad del inversor.

---

## 🛡️ Ciberseguridad y Operaciones OT

- [ ] **Evaluación IEC 62443 / NERC CIP**:
  - Documentar matriz de controles de ciberseguridad para gateways de subestación.
  - Verificación de mTLS en transporte y separación de redes OT/IT.
- [ ] **Pipeline de CI/CD**:
  - Incorporar validación automática de perfiles de inversores contra esquemas JSON estrictos.
  - Mantener ejecución permanente de `scripts/verify_claims.py` en cada pull request.

---

## ✅ Tareas Recientes Completadas (v3.1.0)

- [x] Inercia sintética por RoCoF ($df/dt$) implementada con ganancia $K_d$ y filtro $T_d$ en `FFRController`.
- [x] Prioridad reactiva dinámica en LVRT agregada en `Limiter` y orquestada en `Node`.
- [x] Perfiles de inversores de escala utility agregados a `registry/`: Power Electronics HEM e Ingeteam Ingecon Sun B.
- [x] Especificación técnica `docs/spec/CONTROL.md` y presentación interactiva `docs/dwg_obe_2026.html` actualizadas.
- [x] Documentación principal `README.md` traducida a inglés técnico con selector de idioma a `README.es.md`.
- [x] Correo de ingeniería actualizado a `bessai@bess-solutions.cl` en toda la documentación pública.
- [x] Suite completa de 278 pruebas canónicas pasando (100% OK) y `verify_claims.py` verificado sin advertencias.
