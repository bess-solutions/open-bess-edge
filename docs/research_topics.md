# Temas de Investigación Abiertos — BESSAI Edge Gateway

> **Última actualización**: Febrero 2026  
> **Contacto**: `research@bessai.io` o [GitHub Discussions](https://github.com/bess-solutions/open-bess-edge/discussions/categories/research)

---

## ¿Para quién es este documento?

Este documento está dirigido a **estudiantes de pregrado, posgrado, investigadores y académicos** que buscan proyectos de tesis, artículos o investigaciones en el área de:

- Almacenamiento de energía (BESS)
- Inteligencia artificial aplicada a sistemas de potencia
- Mercados eléctricos y optimización energética
- Ciberseguridad en infraestructura crítica
- IoT industrial y protocolos de comunicación

BESSAI Edge Gateway es un proyecto open source real, con código en producción, datasets históricos disponibles y un equipo técnico dispuesto a colaborar.

---

## Temas disponibles

### Tema R-001: Optimización DRL para Mercados Eléctricos con Alta Volatilidad

**Área**: Aprendizaje por Refuerzo, Mercados Eléctricos  
**Nivel**: Magíster / Doctorado  
**Estado**: 🟢 Disponible  

**Contexto**: El `ONNXArbitrageAgent` del proyecto usa PPO (Proximal Policy Optimization) entrenado en el mercado eléctrico chileno. Sin embargo, los precios CMg pueden ser extremadamente volátiles (0–500 USD/MWh en el mismo día), lo que desafía a los algoritmos DRL estándar.

**Pregunta de investigación**: ¿Cómo adaptar o mejorar el algoritmo DRL (SAC, TD3, PPO+LSTM) para manejar alta volatilidad de precios y distribuciones no estacionarias en mercados spot?

**Datos disponibles**: CMg horario CEN Chile 2020–2025 (via bessai-cen-data).  
**Entregable esperado**: Modelo mejorado exportable a ONNX + comparación benchmark publicada.

---

### Tema R-002: Detección de Anomalías con Transformers en BESS

**Área**: Deep Learning, Ciberseguridad OT  
**Nivel**: Magíster / Ingeniería civil  
**Estado**: 🟢 Disponible  

**Contexto**: El AI-IDS actual usa z-score estadístico para detectar anomalías en señales BESS. Investigaciones recientes sugieren que modelos basados en Transformer (ej. Autoformer, PatchTST) pueden superar a métodos estadísticos clásicos en series temporales industriales.

**Pregunta de investigación**: ¿Puede un modelo Transformer entrenado con datos BESS reales superar al z-score en detección de anomalías, manteniendo latencia < 10 ms en CPU edge?

**Datos disponibles**: Datos de telemetría BESS (SoC, temperatura, potencia) generados por el simulador del proyecto.  
**Entregable esperado**: Módulo ONNX para AI-IDS + benchmark comparativo z-score vs Transformer.

---

### Tema R-003: Digital Twin BESS con Physics-Informed Neural Networks (PINN)

**Área**: Física computacional, Machine Learning, BEP-0201  
**Nivel**: Doctorado  
**Estado**: 🟡 Pendiente de BEP-0201 (Q2 2026)  

**Contexto**: La degradación de baterías LFP/NMC depende de temperatura, ciclos y profundidad de descarga de maneras que los modelos puramente estadísticos no capturan bien. PINN combina leyes físicas de electroquímica con datos históricos para predecir RUL (Remaining Useful Life).

**Pregunta de investigación**: ¿Con qué precisión puede un PINN predecir el RUL de una batería BESS usando solo señales disponibles en el gateway (SoC, temperatura, potencia)?  
**KPI objetivo**: Error de predicción RUL < 2 % (MAPE).

**Entregable esperado**: Modelo PINN exportable a ONNX + validación con dataset público (ej. NASA Battery Dataset, CALCE).

---

### Tema R-004: VPP y Respuesta de Frecuencia en Microredes Insulares

**Área**: Sistemas de potencia, Optimización distribuida  
**Nivel**: Magíster / Doctorado  
**Estado**: 🟢 Disponible  

**Contexto**: El proyecto plantea un piloto VPP con 5 sitios BESS coordinados en Chile (BEP-0300, Q4 2026). El protocolo de coordinación y el algoritmo de consenso para respuesta de frecuencia < 500 ms aúnn están abiertos a investigación.

**Pregunta de investigación**: ¿Qué algoritmo de consenso distribuido (ADMM, gossip, mean-field) minimiza la latencia de coordinación VPP manteniendo la equidad entre sitios en una topología de red chilena real?

**Entregable esperado**: Simulación en BESSAI con 5+ gateways + análisis de latencia y equidad.

---

### Tema R-005: Análisis de Seguridad de Protocolo Modbus en BESS Industriales

**Área**: Ciberseguridad OT, IEC 62443  
**Nivel**: Ingeniería civil / Magíster  
**Estado**: 🟢 Disponible  

**Contexto**: Modbus TCP no tiene autenticación nativa, lo que lo hace vulnerable a ataques de replay, MITM y command injection. BESSAI implementa SafetyGuard como capa de defensa, pero su robustez ante atacantes activos en Modbus no ha sido evaluada formalmente.

**Pregunta de investigación**: ¿Qué tan efectivo es SafetyGuard contra ataques Modbus conocidos (false data injection, replay, out-of-range commands)? ¿Qué mejoras son necesarias para cumplir IEC 62443 SL-2?

**Entregable esperado**: Suite de pruebas de penetración OT + análisis de brechas IEC 62443 SL-2 + propuesta de mejoras implementadas.

---

### Tema R-006: Certificados de Carbono y Trazabilidad en Trading P2P de Energía

**Área**: Blockchain, Economía de la energía, DER  
**Nivel**: Magíster  
**Estado**: 🟡 En revisión para BEP futura  

**Contexto**: El módulo `p2p_trading.py` implementa trading P2P básico entre prosumidores. La EU CBAM (Carbon Border Adjustment Mechanism) y los mercados voluntarios de carbono requieren trazabilidad granular de la huella de carbono de cada kWh transado.

**Pregunta de investigación**: ¿Cómo integrar certificados de carbono tokenizados (NFT o fungibles) en el protocolo P2P de BESSAI, garantizando trazabilidad sin comprometer la escalabilidad?

**Entregable esperado**: Diseño de protocolo + prototipo en red de prueba (Hyperledger o Ethereum testnet) + integración con `lca_engine.py`.

---

### Tema R-007: Optimización Multi-Activo (BESS + V2G + Bomba Calor)

**Área**: Control óptimo, Mercados eléctricos  
**Nivel**: Doctorado  
**Estado**: 🔵 Largo plazo (v3.0.0, 2027)  

**Contexto**: La arquitectura v3.0.0 de BESSAI planea soporte multi-activo (BESS + Vehículo a red V2G + bombas de calor). La optimización conjunta de múltiples activos flexibles bajo restricciones técnicas y de mercado es un problema NP-complejo no resuelto en la escala de distribución.

**Pregunta de investigación**: ¿Puede un agente DRL multi-objetivo coordinar BESS + V2G + bomba de calor simultáneamente para maximizar el ingreso de arbitraje mientras minimiza el malestar térmico del usuario?

---

## Cómo postular a un tema de investigación

1. Leer el tema completo y verificar que tienes acceso a los datos necesarios
2. Abrir una [GitHub Discussion](https://github.com/bess-solutions/open-bess-edge/discussions) con la etiqueta `research` mencionando el número de tema (ej. `R-001`)
3. Incluir:
   - Tu institución y nivel académico
   - Contexto de tu proyecto (tesis individual, proyecto de investigación, trabajo de clase)
   - Plazo estimado
4. El equipo te contactará dentro de 5 días hábiles

---

## Recursos disponibles para investigadores

| Recurso | Acceso | Descripción |
|---|---|---|
| Dataset CMg Chile 2020–2025 | Previa solicitud | CMg horario del CEN Chile |
| Simulador BESS | Open source | `src/simulation/` + `BESSArbitrageEnv` |
| Código fuente completo | GitHub | `github.com/bess-solutions/open-bess-edge` |
| Entorno de desarrollo Docker | Open source | `docker-compose.yml` + instrucciones |
| Dataset de telemetría sintética | Open source | Generado por `scripts/generate_synthetic_data.py` |

---

*BESSAI cree en la ciencia abierta. Todas las publicaciones derivadas de colaboraciones con este proyecto pueden usar nuestro código y datos libremente bajo la licencia AGPL-3.0 y las condiciones de co-autoría acordadas.*
