#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
 scripts/bessai_ui_web.py
 BESSAI Auto-Feasibility Engine — Web Dashboard (Streamlit)
"""
import streamlit as st
import pandas as pd
import json
from pathlib import Path
import plotly.express as px
from bessai_lta_engine import generate_bankable_report

st.set_page_config(page_title="BESSAI Feasibility Studio", page_icon="⚡", layout="wide")

st.title("⚡ BESSAI Commercial Feasibility Studio")
st.markdown("Generativo instantáneo de Backtesting BESS basado en Data de Alta Frecuencia (CEN V4)")

data_path = "bessai-web/data/cmg_data.json"
alt_path = "data/training_dataset.parquet"

@st.cache_data
def load_hubs():
    path = Path(data_path) if Path(data_path).exists() else Path(alt_path)
    if not path.exists(): return ["Maitencillo"]
    try:
        if path.suffix == ".json":
            with open(path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            return sorted(list(raw.get("series", {}).keys()))
        elif path.suffix == ".parquet":
            df = pd.read_parquet(path)
            return sorted(df['barra_transf'].unique().tolist()) if 'barra_transf' in df.columns else ["Maitencillo", "Quillahua", "Arenales", "Crucero", "Cardones", "Polpaico", "Charrua", "Puerto Montt", "Diego de Almagro", "Andes"]
    except Exception:
        pass
    
    # Static Fallback if Parquet missing
    return sorted(["Maitencillo", "Arica", "Quillahua", "Arenales", "Crucero", "Cardones", 
                   "Polpaico", "Charrua", "Puerto Montt", "Diego de Almagro", "Andes", 
                   "Laguna Blanca", "Los Héroes", "Quillota", "Pan de Azucar"])

available_nodes = load_hubs()

def live_fetch_cen(node_name):
    """Fallback Engine: Extrae la data del servidor CEN en tiempo real si no existe localmente."""
    import requests
    start = (pd.Timestamp.now() - pd.Timedelta(days=15)).strftime("%Y-%m-%d")
    end = pd.Timestamp.now().strftime("%Y-%m-%d")
    url = "https://sipub.api.coordinador.cl/costo-marginal-online/v4/findByDate"
    api_key_header = {"user_key": "2b44048b9df6f8c42f3ff9aa1c153f32"} # default key
    
    prices, dates = [], []
    for page in range(1, 4): # Fetch max 3 pages for speed
        try:
            resp = requests.get(url, params={"startDate": start, "endDate": end, "limit": 10000, "page": page}, headers=api_key_header, timeout=8)
            if resp.status_code != 200: break
            data = resp.json().get("data", [])
            for row in data:
                if row.get("barra_transf") == node_name:
                    p = row.get("cmg_kwh_", "") or row.get("cmg_usd_mwh", "")
                    d = row.get("fecha_minuto")
                    if p != "" and d:
                        prices.append(float(p) * 1000 if "kwh" in str(row.keys()) else float(p))
                        dates.append(d)
        except Exception: break
    return dates, prices

# Sidebar Settings
st.sidebar.header("Parámetros del Proyecto")
node_input = st.sidebar.selectbox("Nodo de Conexión (CEN)", options=available_nodes, index=0 if "Maitencillo" not in available_nodes else available_nodes.index("Maitencillo"))
cap_mwh = st.sidebar.number_input("Capacidad BESS (MWh)", min_value=0.5, max_value=5000.0, value=300.0, step=0.5)
power_mw = st.sidebar.number_input("Potencia Inversor (MW)", min_value=0.5, max_value=2000.0, value=100.0, step=0.5)
deg_cost = st.sidebar.number_input("Costo Degradación (USD/kWh)", min_value=0.001, max_value=0.050, value=0.003, step=0.001, format="%.4f")

# Botón gigante
if st.sidebar.button("🚀 Ejecutar Cálculo de Factibilidad", use_container_width=True):
    path = Path(data_path) if Path(data_path).exists() else Path(alt_path)
    
    if not path.exists():
        st.error(f"❌ No se halló base de datos en {path}")
        st.stop()
        
    dates = []
    prices = []
    with st.spinner('Escaneando base de datos nacional...'):
        if path.suffix == ".parquet":
            df = pd.read_parquet(path)
            if 'barra_transf' in df.columns:
                df = df[df['barra_transf'].str.contains(node_input, case=False, na=False)]
            if df.empty:
                st.error(f"Nodo {node_input} no hallado en Parquet.")
                st.stop()
            time_col = 'fecha_minuto' if 'fecha_minuto' in df.columns else df.columns[0]
            price_col = 'cmg_usd_mwh' if 'cmg_usd_mwh' in df.columns else df.columns[1]
            df = df.sort_values(time_col)
            dates = df[time_col].astype(str).tolist()
            prices = df[price_col].astype(float).tolist()
        else:
            with open(path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            series = raw.get("series", {})
            found = next((k for k in series.keys() if node_input.lower() in k.lower()), None)
            
            if not found:
                st.toast(f"Híbrido BESSAI activado: Buscando '{node_input}' en vivo desde API Coordinador Eléctrico Nacional...", icon="📡")
                d_live, p_live = live_fetch_cen(node_input)
                if len(d_live) == 0:
                    st.warning(f"Protección Antidumping: La red gubernamental (CEN) denegó la lectura en vivo (403) o el nodo no retornó datos en los últimos 15 días. Para visualizar Arenales/Quillahua y el resto de los 3,500 nodos, requieres tu API Key corporativa o simplemente arrastrar tu archivo 'training_dataset.parquet' a la carpeta 'data/'.")
                    st.stop()
                found = node_input
                dates = d_live
                prices = p_live
                df = pd.DataFrame({"Fecha": dates, "Precio USD/MWh": prices})
            else:
                data = series[found]
                dates = [x['t'] for x in data]
                prices = [float(x['v']) for x in data]
                node_input = found
                df = pd.DataFrame({"Fecha": dates, "Precio USD/MWh": prices})
                
            # Fix 24:00 issue from CEN legacy systems
            if df["Fecha"].dtype == 'object':
                df["Fecha"] = df["Fecha"].str.replace("24:00", "23:59")
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")

    records = len(prices)
    days = records * 15 / 60 / 24 # aprox for 15-min
    
    mean_cmg = sum(prices) / records
    max_cmg = max(prices)
    hours_zero = sum(1 for p in prices if p <= 5.0) * (15/60)

    # Perfect Foresight Algorithm
    from collections import defaultdict
    by_day = defaultdict(list)
    for d, p in zip(dates, prices):
        by_day[str(d)[:10]].append(p)
        
    ideal_revenue = 0.0
    ideal_cycles = 0.0
    for day, day_prices in by_day.items():
        if len(day_prices) < 20: continue
        sorted_p = sorted(day_prices)
        blocks_to_fill = int(cap_mwh / (power_mw * 0.25))
        if blocks_to_fill > len(sorted_p) // 2: blocks_to_fill = len(sorted_p) // 2
        buy_cost = sum(sorted_p[:blocks_to_fill]) * (power_mw * 0.25)
        sell_rev = sum(sorted_p[-blocks_to_fill:]) * (power_mw * 0.25)
        deg_cost_daily = (cap_mwh * 2 * 1000) * deg_cost
        
        net_profit = (sell_rev - buy_cost) - deg_cost_daily
        if net_profit > 0:
            ideal_revenue += net_profit
            ideal_cycles += 1
            
    ann_mult = 365.0 / len(by_day) if len(by_day) > 0 else 1.0
    ann_ideal_rev = ideal_revenue * ann_mult
    
    # UI Render
    st.success(f"Dignóstico completado para **{node_input}** ({records} bloques analizados)")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Promedio Histórico", f"${mean_cmg:.1f}/MWh")
    col2.metric("Spike Volatilidad Máx", f"${max_cmg:.1f}/MWh")
    col3.metric("Oportunidad de Carga (0 USD)", f"{hours_zero:.0f} hrs")
    col4.metric("Ciclos Anuales", f"{ideal_cycles * ann_mult:.0f}")

    st.markdown("### 💸 Proyección Financiera (Upper Bound Algorítmico V4)")
    st.info(f"**Rentabilidad Neta Anual Esperada:** US$ {ann_ideal_rev:,.2f}  |  **(US$ {ann_ideal_rev/cap_mwh:,.2f} por MWh instalado)**")
    
    st.markdown("### 📈 Curva de Precios Histórica del Nodo")
    fig = px.line(df, x=df.columns[0], y=df.columns[1], title=f"Volatilidad Real: {node_input}", color_discrete_sequence=["#1f77b4"])
    st.plotly_chart(fig, use_container_width=True)

    st.caption("Nota Metodológica: Basado en C-Rate paramétrico y desgaste Li-ion V4 absoluto.")
    
    # Financial Projections (Bank Grade LTA)
    lta_report = generate_bankable_report(
        node_name=node_input,
        cap_mwh=cap_mwh,
        power_mw=power_mw,
        deg_cost=deg_cost,
        records_scanned=records,
        days_scanned=days,
        mean_cmg=mean_cmg,
        max_cmg=max_cmg,
        hours_zero=hours_zero,
        buy_cost_daily=buy_cost,
        sell_rev_daily=sell_rev,
        deg_cost_daily=deg_cost_daily,
        net_profit_daily=net_profit,
        ann_mult=ann_mult,
        ideal_cycles_yr=ideal_cycles * ann_mult,
        ann_merchant_rev=ann_ideal_rev
    )
    
    st.markdown("---")
    st.info(lta_report)
    
    st.download_button(
        label="🏦 Descargar Due Diligence Bancaria (LTA Lenders Report)",
        data=lta_report,
        file_name=f"Due_Diligence_BESSAI_LTA_{node_input}.md",
        mime="text/markdown"
    )
