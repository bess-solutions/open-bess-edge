#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
 scripts/bessai_ui_desktop.py
 BESSAI Auto-Feasibility Engine — Desktop Executable (CustomTkinter)
"""
import customtkinter as ctk
import pandas as pd
import json
from pathlib import Path

# Configuración Visual
ctk.set_appearance_mode("dark")  
ctk.set_default_color_theme("blue")  

def load_hubs():
    alt_path = "data/training_dataset.parquet"
    data_path = "bessai-web/data/cmg_data.json"
    path = Path(data_path) if Path(data_path).exists() else Path(alt_path)
    if not path.exists(): return ["Maitencillo"]
    try:
        if path.suffix == ".json":
            with open(path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            return sorted(list(raw.get("series", {}).keys()))
        elif path.suffix == ".parquet":
            df = pd.read_parquet(path)
            return sorted(df['barra_transf'].unique().tolist()) if 'barra_transf' in df.columns else ["Maitencillo"]
    except Exception:
        pass
        
    return sorted(["Maitencillo", "Arica", "Quillahua", "Arenales", "Crucero", "Cardones", 
                   "Polpaico", "Charrua", "Puerto Montt", "Diego de Almagro", "Andes", 
                   "Laguna Blanca", "Los Héroes", "Quillota", "Pan de Azucar"])

def live_fetch_cen(node_name):
    import requests
    start = (pd.Timestamp.now() - pd.Timedelta(days=15)).strftime("%Y-%m-%d")
    end = pd.Timestamp.now().strftime("%Y-%m-%d")
    url = "https://sipub.api.coordinador.cl/costo-marginal-online/v4/findByDate"
    api_key_header = {"user_key": "2b44048b9df6f8c42f3ff9aa1c153f32"}
    
    prices, dates = [], []
    for page in range(1, 4):
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

def live_fetch_cen(node_name):
    import requests
    start = (pd.Timestamp.now() - pd.Timedelta(days=15)).strftime("%Y-%m-%d")
    end = pd.Timestamp.now().strftime("%Y-%m-%d")
    url = "https://sipub.api.coordinador.cl/costo-marginal-online/v4/findByDate"
    api_key_header = {"user_key": "2b44048b9df6f8c42f3ff9aa1c153f32"}
    
    prices, dates = [], []
    for page in range(1, 4):
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

class BESSAI_App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.available_nodes = load_hubs()
        
        self.title("⚡ BESSAI Commercial Feasibility Studio")
        self.geometry("600x650")
        self.resizable(False, False)
        
        # Título
        self.label_title = ctk.CTkLabel(self, text="Estudio Institucional de Baterías BESS", font=ctk.CTkFont(size=20, weight="bold"))
        self.label_title.pack(pady=20)
        
        # Frame Inputs
        self.frame_inputs = ctk.CTkFrame(self)
        self.frame_inputs.pack(pady=10, padx=20, fill="x")
        
        # Nodo
        self.label_node = ctk.CTkLabel(self.frame_inputs, text="Barra/Nodo CEN:")
        self.label_node.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.entry_node = ctk.CTkComboBox(self.frame_inputs, values=self.available_nodes, width=200)
        self.entry_node.set("Maitencillo" if "Maitencillo" in self.available_nodes else self.available_nodes[0])
        self.entry_node.grid(row=0, column=1, padx=10, pady=10)
        
        # Capacidad
        self.label_cap = ctk.CTkLabel(self.frame_inputs, text="Capacidad BESS (MWh):")
        self.label_cap.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.entry_cap = ctk.CTkEntry(self.frame_inputs, placeholder_text="2")
        self.entry_cap.grid(row=1, column=1, padx=10, pady=10)
        
        # Potencia
        self.label_pow = ctk.CTkLabel(self.frame_inputs, text="Potencia Máxima (MW):")
        self.label_pow.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.entry_pow = ctk.CTkEntry(self.frame_inputs, placeholder_text="1")
        self.entry_pow.grid(row=2, column=1, padx=10, pady=10)
        
        # Degradacion
        self.label_deg = ctk.CTkLabel(self.frame_inputs, text="Degradación (USD/kWh):")
        self.label_deg.grid(row=3, column=0, padx=10, pady=10, sticky="w")
        self.entry_deg = ctk.CTkEntry(self.frame_inputs, placeholder_text="0.003")
        self.entry_deg.grid(row=3, column=1, padx=10, pady=10)
        
        # Button
        self.btn_run = ctk.CTkButton(self, text="🚀 Generar Reporte de Factibilidad", command=self.run_engine, font=ctk.CTkFont(weight="bold"))
        self.btn_run.pack(pady=20)
        
        # TextBox for Results
        self.textbox_log = ctk.CTkTextbox(self, width=540, height=200, corner_radius=10)
        self.textbox_log.pack(pady=10)
        self.textbox_log.insert("0.0", "Esperando Parámetros...\n")
        self.textbox_log.configure(state="disabled")

    def log(self, text):
        self.textbox_log.configure(state="normal")
        self.textbox_log.insert("end", text + "\n")
        self.textbox_log.see("end")
        self.textbox_log.configure(state="disabled")
        self.update_idletasks()

    def run_engine(self):
        self.textbox_log.configure(state="normal")
        self.textbox_log.delete("0.0", "end")
        self.textbox_log.configure(state="disabled")
        
        node = self.entry_node.get() or "Maitencillo"
        cap = float(self.entry_cap.get() or "2.0")
        power = float(self.entry_pow.get() or "1.0")
        deg = float(self.entry_deg.get() or "0.003")
        
        self.log(f"Iniciando cálculo agresivo V4 para {node}...")
        
        alt_path = "data/training_dataset.parquet"
        data_path = "bessai-web/data/cmg_data.json"
        
        path = Path(data_path) if Path(data_path).exists() else Path(alt_path)
        if not path.exists():
            self.log(f"❌ Error: {path} no encontrado.")
            return
            
        dates = []
        prices = []
        try:
            if path.suffix == ".parquet":
                df = pd.read_parquet(path)
                if 'barra_transf' in df.columns:
                    df = df[df['barra_transf'].str.contains(node, case=False, na=False)]
                if df.empty:
                    raise Exception("Parquet miss")
                time_col = 'fecha_minuto' if 'fecha_minuto' in df.columns else df.columns[0]
                price_col = 'cmg_usd_mwh' if 'cmg_usd_mwh' in df.columns else df.columns[1]
                df = df.sort_values(time_col)
                dates = df[time_col].astype(str).tolist()
                prices = df[price_col].astype(float).tolist()
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                series = raw.get("series", {})
                found = next((k for k in series.keys() if node.lower() in k.lower()), None)
                if not found:
                    raise Exception("JSON miss")
                data = series[found]
                dates = [x['t'] for x in data]
                prices = [float(x['v']) for x in data]
                node = found
        except Exception as e:
            self.log(f"⚠️ Nodo {node} no hallado en DB. Iniciando Híbrido en vivo (CEN)...")
            self.update_idletasks()
            dates, prices = live_fetch_cen(node)
            if not dates:
                self.log(f"❌ Error 403 API CEN: Token antidumping activado. Descargue '.parquet'.")
                return
            
        records = len(prices)
        if records == 0:
            self.log("❌ Sin datos.")
            return
            
        mean_cmg = sum(prices) / records
        max_cmg = max(prices)
        self.log(f"✅ DB {node}: {records} registros extraidos.")
        self.log(f"📊 Promedio: {mean_cmg:.2f} USD/MWh | Max Spike: {max_cmg:.2f} USD")
        
        # Algorithm
        from collections import defaultdict
        by_day = defaultdict(list)
        for d, p in zip(dates, prices):
            by_day[str(d)[:10]].append(p)
            
        ideal_revenue = 0.0
        ideal_cycles = 0.0
        for day, day_prices in by_day.items():
            if len(day_prices) < 20: continue
            sorted_p = sorted(day_prices)
            blocks_to_fill = int(cap / (power * 0.25))
            if blocks_to_fill > len(sorted_p) // 2: blocks_to_fill = len(sorted_p) // 2
            buy_cost = sum(sorted_p[:blocks_to_fill]) * (power * 0.25)
            sell_rev = sum(sorted_p[-blocks_to_fill:]) * (power * 0.25)
            deg_cost_daily = (cap * 2 * 1000) * deg
            
            net_profit = (sell_rev - buy_cost) - deg_cost_daily
            if net_profit > 0:
                ideal_revenue += net_profit
                ideal_cycles += 1
                
        ann_mult = 365.0 / len(by_day) if len(by_day) > 0 else 1.0
        ann_ideal_rev = ideal_revenue * ann_mult
        
        self.log(f"\n💰 Rentabilidad Bruta Anualizada (Foresight Perfecto):")
        self.log(f"    US$ {ann_ideal_rev:,.2f} / año")
        self.log(f"    Rentabilidad Específica: US$ {(ann_ideal_rev/cap):,.2f} / MWh")
        self.log(f"    Ciclos Anuales Estimados: {ideal_cycles * ann_mult:,.0f} ")

if __name__ == "__main__":
    app = BESSAI_App()
    app.mainloop()
