# Colaboración Académica — BESSAI Edge Gateway

> **Última actualización**: Marzo 2026  
> **Contacto**: `contacto@bess-solutions.cl` · `research@bessai.io`

---

## Por qué colaborar con BESSAI

BESSAI Edge Gateway es el **único gateway open source para BESS** con:
- Implementación de DRL (Aprendizaje por Refuerzo Profundo) exportable a ONNX
- Soporte completo de IEEE 2030.5 / SEP 2.0 para gestión de recursos distribuidos
- Ruta de certificación IEC 62443 documentada públicamente
- Integración con datos de mercados eléctricos reales (CEN Chile)

Colaborar con BESSAI significa trabajar con **código en producción**, no con prototipos académicos.

---

## Modalidades de colaboración

### 1. Tesis de grado / postgrado

Estudiantes pueden desarrollar su tesis usando el gateway como plataforma. El equipo BESSAI actúa como **co-mentor técnico** sin costo.

**Proceso**:
1. Revisar los [Temas de Investigación Abiertos](research_topics.md)
2. Contactar al equipo vía `research@bessai.io` con tu propuesta
3. Firma de acuerdo de colaboración (no exclusividad, IP del estudiante protegida)
4. Kick-off técnico + acceso a recursos y mentoría mensual

### 2. Proyectos FONDECYT / ANID / financiados

BESSAI puede participar como **entidad colaboradora** en proyectos de investigación financiados, aportando:
- Plataforma tecnológica open source como base
- Datos históricos energéticos (CMg Chile, perfiles de carga BESS)
- Carta de colaboración institucional firmada

**Requisito**: Que el proyecto incluya al menos un componente de mejora al código open source (contribución de código, dataset o documentación que regrese al repositorio público).

### 3. Proyectos de curso / ramos universitarios

Profesores pueden integrar BESSAI en cursos de:
- **Energías Renovables y Almacenamiento** (ingeniería eléctrica)
- **Inteligencia Artificial Aplicada** (ciencias de la computación)
- **IoT Industrial y Protocolos** (ingeniería en automatización)
- **Mercados Eléctricos** (economía / ingeniería)

**Lo que ofrecemos**:
- Material pedagógico listo para usar (Jupyter Notebooks, guías de laboratorio)
- Entorno Docker pre-configurado para que los estudiantes arranquen en < 10 minutos
- Charla gratuita de 1 hora por el equipo BESSAI para tu curso (online)

---

## Universidades con colaboración activa o en conversación

| Institución | País | Área | Estado |
|---|---|---|---|
| **Universidad de Santiago de Chile (USACH)** | Chile | Ingeniería Eléctrica · Mercados Energía | ✅ **Colaboración activa — 2026** |
| Universidad de Chile | Chile | Ingeniería Eléctrica | 🟡 En conversación |
| UTFSM (Federico Santa María) | Chile | Automatización | 🟡 En conversación |
| PUC Chile | Chile | Ing. Eléctrica / IA | 🟡 En conversación |
| *Tu universidad aquí* | — | — | ¡Postula! |

---

## Recursos pedagógicos disponibles

### Jupyter Notebooks de demostración

```bash
# Clonar el repositorio
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge

# Instalar dependencias
pip install -e ".[dev]"

# Ejecutar el simulador de BESS + arbitraje
jupyter notebook notebooks/demo_bess_arbitrage.ipynb
```

> **Nota**: Los notebooks pedagógicos están en desarrollo activo. La carpeta `notebooks/` es parte del roadmap Q2 2026.

### Docker lab environment

```bash
# Levantar entorno completo para laboratorio
docker compose -f docker-compose.lab.yml up -d

# Incluye: gateway, Grafana, MQTT broker, simulador de inversor
```

---

## Política de publicaciones

BESSAI fomenta la **ciencia abierta**. Las publicaciones derivadas de colaboraciones deben:

1. **Citar el proyecto** en la sección de herramientas/metodología:
   ```
   BESSAI Edge Gateway, v2.x (2026). Open source BESS edge intelligence platform.
   https://github.com/bess-solutions/open-bess-edge. DOI: 10.5281/zenodo.XXXXXXX
   ```
   Ver [`CITATION.cff`](../CITATION.cff) para el formato completo.

2. **Contribuir código** al repositorio si el trabajo genera mejoras al software (pull request o nueva BEP).

3. **No requieren** co-autoría del equipo BESSAI (aunque la ofrecemos si hubo contribución técnica sustancial del equipo).

---

## Dataset Académico CC-BY 4.0 — CMg SEN Chile 2023–2026

En el marco de la colaboración BESSAI × USACH, se publica el primer dataset
de Costo Marginal horario del SEN con cobertura de 39 meses:

[![Dataset](https://img.shields.io/badge/dataset-v1.0.0-blue)](https://github.com/bess-solutions/bessai-academic)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Rows](https://img.shields.io/badge/rows-111%2C100-green)](https://github.com/bess-solutions/bessai-academic)

### Contenido

| Campo | Valor |
|-------|-------|
| Nodos | Cardones · Crucero · Charrúa · Quillota |
| Período | Enero 2023 — Marzo 2026 (39 meses) |
| Filas | 111,100 puntos horarios |
| Formato | CSV (4 MB) + Parquet (1.1 MB) |
| Fuente | API pública Coordinador Eléctrico Nacional (CEN) Chile |
| Verificación | SHA-256 incluido en `dataset_metadata.json` |

### Resultados del backtest (regla P25/P75, BESS 5 MWh)

| Nodo | Revenue/mes | IRR | Horas CMg=0 |
|------|-------------|-----|-------------|
| **Crucero** | **$9,200 USD** | **4.6%** | 38% |
| **Cardones** | $8,800 USD | 4.1% | 40% |
| Charrúa | $1,200 USD | 0.3% | <1% |
| Quillota | $980 USD | 0.2% | <1% |

> El norte de Chile (Cardones, Crucero) concentra el 38-40% de horas con CMg ≤ 2 CLP/kWh
> por vertimiento solar masivo — ventana de carga a costo cero para BESS.

### Acceso rápido

```bash
# Clonar el repo académico
git clone https://github.com/bess-solutions/bessai-academic.git
cd bessai-academic

# Instalar dependencias
pip install pandas pyarrow matplotlib seaborn scipy

# Cargar dataset y ver estadísticas
python -c "import pandas as pd; df=pd.read_parquet('data/cmg_4nodos_2023_2026.parquet'); print(df.groupby('node')['cmg_clp_kwh'].describe())"

# Ejecutar backtest completo (12 escenarios, ~2 min)
python notebooks/02_arbitrage_backtest.py --parquet
```

### Cómo citar

```bibtex
@dataset{bessai_cmg_2026,
  author  = {BESS Solutions},
  title   = {BESSAI CMg Historical Dataset — SEN Chile 2023-2026},
  year    = {2026},
  version = {v1.0.0},
  url     = {https://github.com/bess-solutions/bessai-academic},
  license = {CC-BY 4.0}
}
```

---

## Mentoría para estudiantes individuales

¿Eres estudiante y quieres contribuir a BESSAI como proyecto de innovación personal? Ofrecemos mentoría informal para personas que:

- Quieren aprender sobre sistemas BESS reales
- Tienen un proyecto específico en mente (aunque sea pequeño)
- Pueden dedicar al menos 4 horas/semana durante min. 2 meses

**Cómo postular**: Abre una [GitHub Discussion](https://github.com/bess-solutions/open-bess-edge/discussions) con la etiqueta `mentorship` y cuéntanos sobre ti y tu proyecto.

---

## Contacto

| Canal | Uso |
|---|---|
| `research@bessai.io` | Colaboraciones formales, acuerdos institucionales |
| [GitHub Discussions](https://github.com/bess-solutions/open-bess-edge/discussions) | Preguntas técnicas, postulaciones mentoría |
| [Discord #academia](https://discord.gg/bessai) | Chat informal con la comunidad |

---

*Creemos que el software de infraestructura energética debería ser público, auditable y construido con rigor científico. La colaboración académica es central a esa visión.*
