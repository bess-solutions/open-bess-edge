#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-pager OPEN BESS — Dashboard Estratégico de Valor Técnico y Arquitectura v3.1
Formato de alta densidad ejecutiva, 1 sola página, tipografía condensada y balance industrial.

Inspirado en la planilla de ingeniería y due diligence BESSAI TDD.
"""
import argparse
import os
import sys
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.graphics.shapes import Drawing, Line, Rect, String, Group
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, FrameBreak, Image, KeepInFrame,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.flowables import HRFlowable

# =====================================================================
# DATOS DEL ECOSISTEMA OPEN BESS
# =====================================================================
TITULO = "OPEN BESS — Strategic & Technical Value Dashboard v3.1"
SUBTITULO = ("Industrial Edge Runtime, Grid-Forming & BTM Peak Shaving Suite  |  Zero-Vendor Lock-in"
             "  |  SSOT Hardware Abstraction")
TIER = "TIER-1 OPEN STACK"
META = "Release: v3.1.0  |  CI: 100% Green  |  Licencia: Apache-2.0"

HAIRCUT_TXT = ("Evaluación Estratégica Independiente: Arquitectura determinista para borde industrial con "
               "lazo cerrado, fail-safe local y validación matemática formal.")
HAIRCUT_TOPE = "Estado: PRODUCTION READY"

KPIS = [  # (etiqueta, valor, subtítulo)
    ("Cobertura & Tests", "285 / 285", "91.7% Cov  |  Hypothesis Fuzzing"),
    ("Lazo de Despacho", "< 50 ms", "Sub-ciclo determinista local"),
    ("Ahorro BTM Peak", "30% - 45%", "Cargos por potencia en punta"),
    ("Protocolos de Campo", "Modbus / CAN", "IEC-104 / DNP3 / RTU / TCP"),
    ("Vendor Lock-in", "0.0% NULO", "Hardware-Agnostic JSON SSOT"),
]

PILARES = [
    dict(
        titulo="Pilar 1: Cierra el Abismo Crítico IT vs OT (Edge Determinista vs Cloud)",
        score=20.0,
        maximo=20.0,
        items=[
            ("ok", "Runtime autónomo de borde (x86/ARM, Linux embebido): opera con total independencia ante cortes de fibra o red celular 4G."),
            ("ok", "BESS-GUARD local inviolable por software: envelope determinista de corriente, potencia, rampas kW/s y límites físicos de celdas."),
            ("ok", "Lazo cerrado continuo con medidor de red: watchdog con fallback a modo seguro ante pérdida de telemetría de red en subestación."),
            ("ok", "APIs REST locales autenticadas con observabilidad industrial: telemetría en tiempo real sin obligar al envío de datos a nubes externas."),
        ],
    ),
    dict(
        titulo="Pilar 2: Rigor de Ingeniería y Cultura Anti-Hype (Zero Mock Policy)",
        score=20.0,
        maximo=20.0,
        items=[
            ("ok", "285 pruebas automatizadas: unitarias, integración en lazo cerrado y property-based testing con Hypothesis para límites físicos."),
            ("ok", "Análisis estático exhaustivo: mypy --strict en 100% del código, ruff linter industrial y auditoría de seguridad bandit (0 hallazgos activos)."),
            ("ok", "CI/CD multiplataforma real: matrices continuas en Linux y Windows cruzadas contra pymodbus 3.9, 3.11 y 3.15."),
            ("ok", "Honestidad empírica: separación estricta entre invariantes físicas validadas y reglas de mercado clasificadas como SUPUESTO técnico."),
        ],
    ),
    dict(
        titulo="Pilar 3: Arquitectura Desacoplada y Agnosticism de Jurisdicción",
        score=15.0,
        maximo=15.0,
        items=[
            ("ok", "Separación arquitectónica tripartita: Edge Runtime (física neutra) + Device Profiles (hardware) + Sandbox (regulación)."),
            ("ok", "Universalmente adaptable: el mismo nodo opera en Chile (Art. 182° LGSE / NTSyCS), ERCOT (Texas) o REE (España) sin tocar código C/Python."),
            ("ok", "Abstracción declarativa JSON SSOT (bess-device-profiles): integrar nuevos inversores (PCS) o medidores no requiere recompilación."),
        ],
    ),
    dict(
        titulo="Pilar 4: Impacto Económico Inmediato (BTM Peak Shaving & Arbitraje)",
        score=15.0,
        maximo=15.0,
        items=[
            ("ok", "BTM Peak Shaving gobernado en tiempo real: amortigua la demanda industrial en horas punta evitando sobrecargos por potencia contratada."),
            ("ok", "Ahorro directo medible: reducción de hasta 45% en la factura eléctrica de clientes industriales (ROI típico entre 3.5 y 5 años)."),
            ("ok", "Reserva de SoC multiobjetivo: protección de capacidad crítica para respaldo UPS de planta combinada con recorte de picos."),
        ],
    ),
    dict(
        titulo="Pilar 5: Gemelo Digital y Simulación de Lazo Cerrado sin Riesgo Físico",
        score=15.0,
        maximo=15.0,
        items=[
            ("ok", "Ecosistema integrado (open-bess-sandbox + bess-modbus-simulator): simula subestaciones, PCS, medidores y cargas dinámicas de fábrica."),
            ("ok", "Simulación completa de 24h en < 10 segundos: permite iterar perfiles de carga y contingencias de red sin arriesgar celdas físicas de litio."),
            ("ok", "Validación previa al despliegue: reduce los costos y semanas de comisionamiento en terreno a una fracción del costo habitual."),
        ],
    ),
    dict(
        titulo="Pilar 6: Democratización Tecnológica y Soberanía para Integradores EPC",
        score=15.0,
        maximo=15.0,
        tabla=[
            ("Componente Evaluado", "Open BESS", "SCADA Propietario"),
            ("Licenciamiento por Sitio", "$0 USD (Open Source)", "$15k - $60k USD / año"),
            ("Acceso al Código Fuente", "100% Auditable", "0% Caja Negra"),
            ("Independencia de Marca", "Multi-vendor Libre", "Vendor Lock-in"),
            ("Tiempo de Integración", "Horas (Perfiles JSON)", "Semanas / Meses"),
        ],
        items=[
            ("ok", "Rompe el monopolio de los gigantes tradicionales (Siemens, Schneider, Sungrow, Huawei) para integradores medianos y cooperativas."),
            ("ok", "Despliegue ágil en contenedores Docker multi-arquitectura (AMD64 y ARM64 para Raspberry Pi CM4 y PLCs industriales)."),
        ],
    ),
]

RESUMEN_PILARES = [
    ("P1  Cierre Abismo IT/OT (Edge Autónomo)", 20.0, 20.0),
    ("P2  Rigor Técnico y Pruebas Formales", 20.0, 20.0),
    ("P3  Agnosticismo de Jurisdicción y HW", 15.0, 15.0),
    ("P4  Impacto Económico BTM y ROI", 15.0, 15.0),
    ("P5  Gemelo Digital y Simulación Cerrada", 15.0, 15.0),
    ("P6  Democratización y Soberanía EPC", 15.0, 15.0),
]

MATRIZ_RIESGOS = [
    ("Vendor Lock-in de Hardware", "NULO (0.0%)"),
    ("Dependencia de Conexión Cloud", "NULA (Edge 100%)"),
    ("Riesgo de Disparo Térmico por SW", "MITIGADO (BESS-GUARD)"),
    ("Fallas de Integración en Campo", "BAJO (Sandbox Sim)"),
    ("Obsolescencia Tecnológica", "BAJA (Stack Moderno)"),
    ("Cumplimiento en Auditoría / Due Diligence", "ALTO (Tests + Tipado)"),
]

AHORRO_ECONOMICO = [
    ("Concepto de Ahorro / Beneficio (Planta 500 kW / 1 MWh)", "Monto Anual Est."),
    ("Ahorro por Recorte de Potencia en Punta (Peak Shaving)", "$45,000 - $72,000 USD"),
    ("Arbitraje Horario de Energía (Carga Valle / Descarga)", "$14,000 - $22,000 USD"),
    ("Eliminación de Licencias SCADA / EMS Propietario", "$18,000 - $35,000 USD"),
    ("Mitigación de Multas por Falla de Despacho", "$8,000 - $15,000 USD"),
    ("Ahorro Total Estimado por Año", "$85,000 - $144,000 USD"),
]

ROADMAP = [
    ("Fase / Hito Estratégico", "Alcance Técnico", "Estado"),
    ("Fase 1: Runtime v3.1 & BTM Peak Shaving", "Edge + Medidor Modbus + Lazo Cerrado", "COMPLETADO"),
    ("Fase 2: Perfiles HW Comerciales Tier-1", "Janitza UMG, Schneider PM8000, Deye", "EN CURSO"),
    ("Fase 3: Banco Físico HIL en Laboratorio", "Raspberry Pi CM4 + RS-485 + Analizador", "PLANIFICADO"),
    ("Fase 4: Certificación SSCC Operador Red", "Homologación NTSyCS / CEN y ERCOT", "ROADMAP"),
]

DISCLAIMER = ("DECLARACIÓN DE INGENIERÍA Y VALOR ESTRATÉGICO: Este reporte sintetiza la evaluación técnica "
              "del ecosistema Open BESS v3.1.0. La arquitectura desacoplada y la suite de pruebas automatizadas "
              "garantizan que el software cumple con los estándares más exigentes de la industria eléctrica industrial "
              "(OT), proveyendo una alternativa robusta, auditable y financieramente bancable frente a soluciones propietarias.")

FIRMA = ("Emitido para el Ecosistema OPEN BESS — Arquitectura & Estrategia Industrial "
         "(Lead Energy Storage Engineering & Open Solutions)")

# =====================================================================
# ESTILO Y FORMATO (IDÉNTICO A LA PLANILLA BESSAI)
# =====================================================================
NEGRO = colors.black
GRIS_CLARO = colors.Color(0.91, 0.91, 0.91)
GRIS_MEDIO = colors.Color(0.60, 0.60, 0.60)

MARGEN = 24          # pt
GUTTER = 13          # separación entre columnas
ANCHO_IZQ_FRAC = 0.595
ALTO_CABECERA = 104
ALTO_PIE = 48
CUERPO = 6.6         # tamaño base

FUENTES_CANDIDATAS = [
    ("C:/Windows/Fonts/ARIALN.TTF", "C:/Windows/Fonts/ARIALNB.TTF"),
    ("/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial Narrow.ttf",
     "/System/Library/Fonts/Supplemental/Arial Narrow Bold.ttf"),
]

FONT, FONT_B, GLIFOS = "Helvetica", "Helvetica-Bold", None


def configurar_fuentes(regular=None, negrita=None):
    global FONT, FONT_B, GLIFOS
    pares = ([(regular, negrita or regular)] if regular else []) + FUENTES_CANDIDATAS
    for r, b in pares:
        if os.path.exists(r) and os.path.exists(b):
            try:
                pdfmetrics.registerFont(TTFont("Cond", r))
                pdfmetrics.registerFont(TTFont("Cond-Bold", b))
                pdfmetrics.registerFontFamily("Cond", normal="Cond", bold="Cond-Bold",
                                              italic="Cond", boldItalic="Cond-Bold")
                FONT, FONT_B = "Cond", "Cond-Bold"
                GLIFOS = set(pdfmetrics.getFont("Cond").face.charToGlyph.keys())
                print(f"Fuente tipográfica condensada activada: {os.path.basename(r)}")
                return
            except Exception as ex:
                print(f"Aviso al cargar {r}: {ex}")
    print("Aviso: usando Helvetica estándar.")


_REEMPLAZOS = {"≥": ">=", "≤": "<=", "Δ": "Delta ", "–": "-", "—": "-", "‑": "-"}


def _renderizable(ch):
    if GLIFOS is not None:
        return ord(ch) in GLIFOS
    try:
        ch.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def limpiar(texto):
    salida = []
    for ch in texto:
        if ch == "\ufe0f":
            continue
        salida.append(ch if _renderizable(ch) else _REEMPLAZOS.get(ch, "?"))
    return "".join(salida)


def E(texto):
    return escape(limpiar(texto))


def crear_estilos():
    def S(nombre, **kw):
        base = dict(fontName=FONT, fontSize=CUERPO, leading=CUERPO * 1.17, textColor=NEGRO)
        base.update(kw)
        return ParagraphStyle(nombre, **base)

    bullet = dict(leftIndent=8.5, bulletIndent=0.5, spaceAfter=0.8)
    return {
        "titulo": S("titulo", fontName=FONT_B, fontSize=12.4, leading=14.5),
        "sub": S("sub", fontSize=7.2, leading=9.0),
        "meta": S("meta", fontSize=6.5, alignment=TA_RIGHT),
        "badge": S("badge", fontName=FONT_B, fontSize=8.0, leading=9.8, alignment=TA_CENTER),
        "klabel": S("klabel", fontName=FONT_B, fontSize=5.5, leading=6.6),
        "kvalor": S("kvalor", fontName=FONT_B, fontSize=12.0, leading=14.0),
        "ksub": S("ksub", fontSize=5.8, leading=6.9),
        "nota": S("nota", fontSize=6.4, leading=7.7),
        "notad": S("notad", fontName=FONT_B, fontSize=6.4, leading=7.7, alignment=TA_RIGHT),
        "sec": S("sec", fontName=FONT_B, fontSize=7.3, leading=8.8),
        "ph": S("ph", fontName=FONT_B, fontSize=7.0, leading=8.5),
        "ps": S("ps", fontName=FONT_B, fontSize=7.3, leading=8.7, alignment=TA_RIGHT),
        "th": S("th", fontName=FONT_B, fontSize=5.8, leading=6.9),
        "thr": S("thr", fontName=FONT_B, fontSize=5.8, leading=6.9, alignment=TA_RIGHT),
        "c": S("c", fontSize=6.4, leading=7.5),
        "cb": S("cb", fontName=FONT_B, fontSize=6.4, leading=7.5),
        "cr": S("cr", fontSize=6.4, leading=7.5, alignment=TA_RIGHT),
        "crb": S("crb", fontName=FONT_B, fontSize=6.4, leading=7.5, alignment=TA_RIGHT),
        "b_ok": S("b_ok", bulletFontName=FONT_B, bulletFontSize=CUERPO, **bullet),
        "b_warn": S("b_warn", bulletFontName=FONT_B, bulletFontSize=CUERPO - 1, **bullet),
        "b_info": S("b_info", bulletFontName=FONT_B, bulletFontSize=CUERPO, **bullet),
        "pie": S("pie", fontSize=5.6, leading=6.7, alignment=TA_JUSTIFY),
        "pieb": S("pieb", fontName=FONT_B, fontSize=6.1, leading=7.4),
        "cap": S("cap", fontSize=5.5, leading=6.5),
    }


ST = {}


def P(texto, estilo, **kw):
    return Paragraph(E(texto), ST[estilo], **kw)


def seccion(titulo, ancho):
    t = Table([[P(titulo.upper(), "sec")]], colWidths=[ancho])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.9, NEGRO),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    return t


def tabla(filas, anchos, cabecera=True, der=(), neg=(), ultima_negrita=False):
    datos = []
    for i, fila in enumerate(filas):
        out = []
        for j, celda in enumerate(fila):
            if cabecera and i == 0:
                est = "thr" if j in der else "th"
            else:
                b = ultima_negrita and i == len(filas) - 1 or j in neg
                est = ("crb" if b else "cr") if j in der else ("cb" if b else "c")
            out.append(P(str(celda), est))
        datos.append(out)
    t = Table(datos, colWidths=anchos)
    cmds = [
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, GRIS_MEDIO),
        ("TOPPADDING", (0, 0), (-1, -1), 1.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.4),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if cabecera:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), GRIS_CLARO), ("LINEABOVE", (0, 0), (-1, 0), 0.6, NEGRO),
                 ("LINEBELOW", (0, 0), (-1, 0), 0.6, NEGRO)]
    if ultima_negrita:
        cmds += [("LINEABOVE", (0, -1), (-1, -1), 0.8, NEGRO), ("LINEBELOW", (0, -1), (-1, -1), 0.8, NEGRO)]
    t.setStyle(TableStyle(cmds))
    return t


def vineta(tipo, texto):
    marca = {"ok": "•", "warn": "!", "info": "i"}[tipo]
    contenido = E(texto)
    if tipo == "warn":
        contenido = f"<b>{contenido}</b>"
    return Paragraph(contenido, ST["b_" + tipo], bulletText=marca)


def bloque_pilar(p, ancho):
    cab = Table([[P(p["titulo"], "ph"), P(f'{p["score"]:.1f} / {p["maximo"]:.1f}', "ps")]],
                colWidths=[ancho - 50, 50])
    cab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRIS_CLARO), ("BOX", (0, 0), (-1, -1), 0.6, NEGRO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.5), ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    bloque = [cab, Spacer(1, 2.0)]
    if p.get("tabla"):
        bloque += [tabla(p["tabla"], [ancho - 150, 50, 50, 50], der=(1, 2, 3)), Spacer(1, 2.0)]
    bloque += [vineta(k, t) for k, t in p["items"]]
    bloque.append(Spacer(1, 3.5))
    return bloque


def grafico_comparativo(ancho, alto):
    """Genera un gráfico vectorial en ReportLab comparando costos y tiempos de integración."""
    d = Drawing(ancho, alto)
    x0, y0 = 35, 12
    pw, ph = ancho - x0 - 8, alto - y0 - 15

    # Categorías a comparar
    modelos = [
        ("SCADA Propietario (Tier-1 Tradicional)", 90, 85),
        ("Startup Cloud-Only (SaaS Remoto)", 60, 40),
        ("OPEN BESS Edge Stack (Open Source)", 15, 12),
    ]

    # Eje y guías
    d.add(Line(x0, y0, x0 + pw, y0, strokeColor=NEGRO, strokeWidth=0.7))
    d.add(Line(x0, y0, x0, y0 + ph, strokeColor=NEGRO, strokeWidth=0.5))

    slot = pw / len(modelos)
    bw = slot * 0.32

    for i, (nombre, costo, tiempo) in enumerate(modelos):
        bx = x0 + i * slot + (slot - 2 * bw) / 2
        # Barra 1: Costo TCO Relativo
        h_costo = (costo / 100.0) * ph
        d.add(Rect(bx, y0, bw, h_costo, fillColor=NEGRO, strokeColor=NEGRO, strokeWidth=0.3))
        d.add(String(bx + bw / 2, y0 + h_costo + 2, f"{costo}%", fontName=FONT_B, fontSize=4.8, textAnchor="middle"))

        # Barra 2: Tiempo de Integración / Rigidez
        h_tiempo = (tiempo / 100.0) * ph
        d.add(Rect(bx + bw + 2, y0, bw, h_tiempo, fillColor=GRIS_MEDIO, strokeColor=NEGRO, strokeWidth=0.3))
        d.add(String(bx + bw + 2 + bw / 2, y0 + h_tiempo + 2, f"{tiempo}d", fontName=FONT, fontSize=4.8, textAnchor="middle"))

        # Etiqueta abajo
        etiqueta_corta = ["SCADA Propietario", "SaaS Cloud-Only", "OPEN BESS Edge"][i]
        d.add(String(bx + bw, y0 - 7, etiqueta_corta, fontName=FONT_B, fontSize=4.7, textAnchor="middle"))

    # Leyenda
    d.add(Rect(x0 + pw - 90, y0 + ph - 2, 7, 5, fillColor=NEGRO, strokeColor=NEGRO, strokeWidth=0.2))
    d.add(String(x0 + pw - 80, y0 + ph - 2, "TCO Total (Licencias/HW)", fontName=FONT, fontSize=4.8))
    d.add(Rect(x0 + pw - 90, y0 + ph - 9, 7, 5, fillColor=GRIS_MEDIO, strokeColor=NEGRO, strokeWidth=0.2))
    d.add(String(x0 + pw - 80, y0 + ph - 9, "Rigidez / Setup (Días)", fontName=FONT, fontSize=4.8))

    return d


def resolver_logo():
    candidatos = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "bess_logo_bw_transparent.png"),
        r"C:\Users\lenovo\OneDrive\Desktop\02_Proyectos_Tech\01_BESS_Tech\bessai-pilot\assets\brand\bess_logo_bw_transparent.png",
        r"C:\Users\lenovo\OneDrive\Desktop\Logos BESS Solutions\bess-logo-light-bg (2).png",
    ]
    for c in candidatos:
        if os.path.exists(c):
            return c
    return None


def construir_cabecera(ancho):
    izq = []
    logo_p = resolver_logo()
    if logo_p:
        w_logo = 88
        h_logo = round(w_logo / (1459 / 319), 1)
        img = Image(logo_p, width=w_logo, height=h_logo)
        img.hAlign = "LEFT"
        izq += [img, Spacer(1, 2.5)]
    izq += [P(TITULO, "titulo"), Spacer(1, 1.2), P(SUBTITULO, "sub")]
    badge = Table([[P(TIER, "badge")]], colWidths=[105])
    badge.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1.2, NEGRO),
                               ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
    badge.hAlign = "RIGHT"
    der = [badge, Spacer(1, 2), P(META, "meta")]
    cab = Table([[izq, der]], colWidths=[ancho - 145, 145])
    cab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                             ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))

    celdas = [[[P(et.upper(), "klabel"), P(val, "kvalor"), P(sub, "ksub")] for et, val, sub in KPIS]]
    kpi = Table(celdas, colWidths=[ancho / len(KPIS)] * len(KPIS))
    kpi.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.9, NEGRO), ("INNERGRID", (0, 0), (-1, -1), 0.5, NEGRO),
                             ("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("TOPPADDING", (0, 0), (-1, -1), 2.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
                             ("LEFTPADDING", (0, 0), (-1, -1), 4.5), ("RIGHTPADDING", (0, 0), (-1, -1), 3.5)]))

    hair = Table([[P(HAIRCUT_TXT, "nota"), P(HAIRCUT_TOPE, "notad")]], colWidths=[ancho - 120, 120])
    hair.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, NEGRO), ("BACKGROUND", (0, 0), (-1, -1), GRIS_CLARO),
                              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                              ("TOPPADDING", (0, 0), (-1, -1), 1.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
                              ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return [cab, Spacer(1, 2.5), HRFlowable(width="100%", thickness=1.3, color=NEGRO, spaceAfter=0),
            Spacer(1, 3.5), kpi, Spacer(1, 3.5), hair]


def construir_columna_izq(ancho):
    out = [seccion("Evaluación técnica detallada por pilares de ingeniería", ancho), Spacer(1, 2.5)]
    for p in PILARES:
        out += bloque_pilar(p, ancho)
    return out


def construir_columna_der(ancho):
    out = []
    # Resumen de puntaje
    bruto = sum(s for _, s, _ in RESUMEN_PILARES)
    filas = [("Dimensión de Valor / Pilar", "Score", "Máx.")]
    filas += [(n, f"{s:.1f}", f"{m:.1f}") for n, s, m in RESUMEN_PILARES]
    filas += [("Puntuación Técnica Global", f"{bruto:.1f}", "100.0"),
              ("Calificación de Robustez", "EXCELENCIA (A+)", "")]
    t = tabla(filas, [ancho - 68, 32, 36], der=(1, 2), ultima_negrita=True)
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONT)]))
    out += [seccion("Puntuación global de arquitectura", ancho), Spacer(1, 1.8), t, Spacer(1, 6)]

    # Matriz de riesgos
    out += [seccion("Matriz de mitigación de riesgos industriales", ancho), Spacer(1, 1.8),
            tabla([("Factor de Riesgo Tradicional", "Estado Open BESS")] + MATRIZ_RIESGOS, [ancho - 66, 66], der=(1,), neg=(1,)), Spacer(1, 6)]

    # Gráfico comparativo
    out += [seccion("Comparativa TCO vs Soluciones Tradicionales", ancho), Spacer(1, 2),
            grafico_comparativo(ancho, 68),
            P("Comparativa cualitativa de Costo Total de Propiedad (TCO) y Rigidez de Integración en campo.", "cap"),
            Spacer(1, 5)]

    # Ahorro BTM
    out += [seccion("Modelo de ahorro económico (Planta C&I 500 kW / 1 MWh)", ancho), Spacer(1, 1.8),
            tabla(AHORRO_ECONOMICO, [ancho - 68, 68], der=(1,), neg=(1,), ultima_negrita=True),
            Spacer(1, 6)]

    # Roadmap
    out += [seccion("Hoja de ruta tecnológica y próximos hitos", ancho), Spacer(1, 1.8),
            tabla(ROADMAP, [ancho - 110, 65, 45], der=(2,), neg=(2,)),
            Spacer(1, 2)]

    return out


def construir_pie(ancho):
    cont = [Paragraph(f"<b>{E('Dictamen de Arquitectura y Valor de Ingeniería.')}</b> {E(DISCLAIMER)}", ST["pie"]),
            Spacer(1, 2.0), P(FIRMA, "pieb")]
    t = Table([[cont]], colWidths=[ancho])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.7, NEGRO),
                           ("TOPPADDING", (0, 0), (-1, -1), 3.0), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.0),
                           ("LEFTPADDING", (0, 0), (-1, -1), 4.5), ("RIGHTPADDING", (0, 0), (-1, -1), 4.5)]))
    return [t]


def altura(flowables, ancho):
    h = 0
    for f in flowables:
        _, hh = f.wrap(ancho, 10000)
        h += hh + f.getSpaceBefore() + f.getSpaceAfter()
    return h


def generar(salida, pagesize):
    global ST
    ST = crear_estilos()
    W, H = pagesize
    cw = W - 2 * MARGEN
    lw = round((cw - GUTTER) * ANCHO_IZQ_FRAC, 1)
    rw = cw - GUTTER - lw
    alto_col = H - 2 * MARGEN - ALTO_CABECERA - ALTO_PIE - 10
    y_col = MARGEN + ALTO_PIE + 5

    cab = construir_cabecera(cw)
    izq = construir_columna_izq(lw)
    der = construir_columna_der(rw)
    pie = construir_pie(cw)

    for nombre, cont, ancho, disp in (("cabecera", cab, cw, ALTO_CABECERA), ("col. izquierda", izq, lw, alto_col),
                                      ("col. derecha", der, rw, alto_col), ("pie", pie, cw, ALTO_PIE)):
        usado = altura(cont, ancho)
        estado = "OK" if usado <= disp else f"EXCEDE -> se reduce a {disp / usado:.0%}"
        print(f"  {nombre:<15} {usado:6.1f} / {disp:6.1f} pt  {estado}")

    def caja(c, ancho, alto):
        return KeepInFrame(ancho, alto - 1, c, mode="shrink", hAlign="LEFT", vAlign="TOP")

    def marco(fid, x, y, w, h):
        return Frame(x, y, w, h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id=fid)

    doc = BaseDocTemplate(salida, pagesize=pagesize, leftMargin=MARGEN, rightMargin=MARGEN,
                          topMargin=MARGEN, bottomMargin=MARGEN,
                          title="OPEN BESS — Strategic & Technical Value Dashboard v3.1",
                          author="OPEN BESS Engineering", subject="One-pager de Valor y Arquitectura")
    doc.addPageTemplates([PageTemplate(id="onepager", frames=[
        marco("cab", MARGEN, H - MARGEN - ALTO_CABECERA, cw, ALTO_CABECERA),
        marco("izq", MARGEN, y_col, lw, alto_col),
        marco("der", MARGEN + lw + GUTTER, y_col, rw, alto_col),
        marco("pie", MARGEN, MARGEN, cw, ALTO_PIE),
    ])])
    doc.build([caja(cab, cw, ALTO_CABECERA), FrameBreak(),
               caja(izq, lw, alto_col), FrameBreak(),
               caja(der, rw, alto_col), FrameBreak(),
               caja(pie, cw, ALTO_PIE)])
    print(f"\n>> PDF generado exitosamente: {salida} ({doc.page} página{'s' if doc.page != 1 else ''})\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Genera el one-pager OPEN BESS en PDF.")
    ap.add_argument("-o", "--output", default="Open_BESS_Strategic_Value_OnePager.pdf")
    ap.add_argument("--a4", action="store_true", help="Usar A4 en vez de carta")
    ap.add_argument("--font", help="TTF condensado regular (opcional)")
    ap.add_argument("--font-bold", help="TTF condensado negrita (opcional)")
    args = ap.parse_args()
    configurar_fuentes(args.font, args.font_bold)
    generar(args.output, A4 if args.a4 else letter)
