# IEC 62443 SL-2 Gap Analysis — BESSAI Edge Gateway
> **Base:** SL-1 completo (mapeado en `iec62443_mapping.md`)
> **Target:** SL-2 — Certificación enterprise para clientes mina/parque solar
> **Fecha:** 2026-02-22 · Versión: 1.0

---

## Resumen Ejecutivo

BESSAI Edge Gateway cumple actualmente **IEC 62443 SL-1** (protección contra amenazas comunes). Para SL-2 (protección contra atacantes con habilidades y recursos moderados) se requieren 12 controles adicionales.

**Costo estimado certificación SL-2:** $12.000 - $18.000 USD (organismo DNV o TÜV)
**ETA con fondos SSAF:** 90 días (Q2 2026)

---

## Controles SL-1 → SL-2: Gap por Requisito

### FR1 — Identificación y Autenticación (IAC)

| Control | SL-1 Estado | SL-2 Requerimiento | Gap | Prioridad |
|---|---|---|---|---|
| IAC-1: Account management | ✅ Config pydantic-settings | MFA obligatorio para operadores | 🔴 Alto | P1 |
| IAC-2: Identifier management | ✅ site_id en config | Gestión centralizada de identidades (LDAP/AD) | 🟡 Medio | P2 |
| IAC-3: Authenticator management | ❌ No implementado | Rotación automática de credenciales | 🔴 Alto | P1 |
| IAC-7: Strength of password | ✅ Secrets K8s | Política de contraseñas + auditoría | 🟡 Medio | P2 |

**Acciones requeridas:**
- [ ] Implementar RBAC con tokens JWT para acceso a API `/dashboard`
- [ ] Añadir rotación automática de secrets (ESO + GCP Secret Manager)
- [ ] Log de accesos en Cloud Audit Logs

### FR2 — Control de Uso (UC)

| Control | SL-1 Estado | SL-2 Requerimiento | Gap |
|---|---|---|---|
| UC-1: Least privilege | 🟡 SecurityContext K8s | Permisos mínimos por componente | 🟡 Medio |
| UC-2: Partition de redes | ❌ No implementado | NetworkPolicy K8s para aislar pods | 🔴 Alto |
| UC-6: Control de acceso remoto | ❌ No implementado | VPN obligatoria para acceso remoto | 🔴 Alto |

**Acciones requeridas:**
- [ ] Añadir `NetworkPolicy` K8s (ingress/egress restringidos)
- [ ] Documentar procedimiento de acceso remoto con VPN

### FR3 — Integridad del Sistema (SI)

| Control | SL-1 Estado | SL-2 Requerimiento | Gap |
|---|---|---|---|
| SI-1: Communication integrity | 🟡 MQTT TLS opcional | mTLS obligatorio en todas las conexiones | 🔴 Alto |
| SI-2: Malicious code protection | ✅ Trivy en CI | Escaneo en runtime (Falco) | 🟡 Medio |
| SI-3: Security functionality verification | ✅ CI automated tests | Pen-testing anual documentado | 🟡 Medio |

**Acciones requeridas:**
- [ ] Activar mTLS en MQTT publisher (cert-manager + Let's Encrypt)
- [ ] Instalar Falco como DaemonSet en K8s para detección runtime

### FR4 — Confidencialidad de Datos (DC)

| Control | SL-1 Estado | SL-2 Requerimiento | Gap |
|---|---|---|---|
| DC-1: Information confidentiality | ✅ Secrets K8s | Cifrado de datos en reposo (KMS) | 🟡 Medio |
| DC-3: Cryptography | 🟡 TLS 1.2+ | TLS 1.3 obligatorio, rotación de claves | 🟡 Medio |

### FR7 — Disponibilidad de Recursos (RA)

| Control | SL-1 Estado | SL-2 Requerimiento | Gap |
|---|---|---|---|
| RA-1: Availability of DoS | 🟡 K8s limits | Rate limiting + circuit breaker | 🟡 Medio |
| RA-6: Network and link design | ✅ Docker networking | Redundancia de enlace documentada | 🟢 Bajo |

---

## Plan de Remediación Priorizado

### Fase 1 — P1 (Q2 2026, semanas 1-4, $0 adicional)
```
[x] SecurityContext K8s hardened (ya implementado)
[ ] NetworkPolicy K8s egress/ingress
[ ] mTLS MQTT activado con cert-manager
[ ] RBAC JWT en dashboard_api.py
```

### Fase 2 — P2 (Q2 2026, semanas 5-8, ~$2k DevOps)
```
[ ] Rotación secrets con ESO + GCP Secret Manager
[ ] Falco DaemonSet en K8s
[ ] Cloud Audit Logs para accesos API
[ ] TLS 1.3 forzado en todos los endpoints
```

### Fase 3 — Certificación (Q2 2026, semanas 9-12, $12-18k)
```
[ ] Pen-testing por organismo externo (DNV / TÜV)
[ ] Documentación SL-2 completa (ICS-CERT style)
[ ] Audit trail completo 6 meses
[ ] Certificado SL-2 emitido
```

---

## Valor Comercial de SL-2

| Cliente | Exigencia actual | Post-SL-2 |
|---|---|---|
| Mineras (BHP, Codelco) | SL-2 obligatorio | 🟢 Acceso desbloqueado |
| Parques solares >50MW | SL-1 en licitaciones | 🟢 Diferenciador competitivo |
| Export a EU/Australia | IEC 62443 mención | 🟢 Credencial reconocida |
| AES, Engie Chile | Auditorías anuales | 🟢 Audit-ready |

> 🎯 **La certificación SL-2 desbloquea el mercado enterprise completo de minas y utilities en Chile.**
