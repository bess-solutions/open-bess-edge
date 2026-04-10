import requests
import json
from pathlib import Path

def main():
    url = "https://sipub.api.coordinador.cl/costo-marginal-online/v4/findByDate"
    headers = {
        "User-Agent": "open-bess-edge/2.10 (BESSAIEvolve data scraper)",
        "user_key": "2b44048b9df6f8c42f3ff9aa1c153f32"
    }
    params = {"startDate": "2024-03-10", "endDate": "2024-03-10", "limit": 10000, "page": 1}
    
    print("Hitting CEN V4 API to extract master nodes list...")
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    
    if resp.status_code != 200:
        print(f"Failed! Status: {resp.status_code}. Response: {resp.text[:200]}")
        return
        
    data = resp.json().get("data", [])
    nodes = sorted(list(set(item.get("barra_transf") for item in data if item.get("barra_transf"))))
    
    Path("data").mkdir(exist_ok=True)
    with open("data/nodes_master.json", "w", encoding="utf-8") as f:
        json.dump(nodes, f, ensure_ascii=False)
        
    print(f"SUCCESS! Extracted and saved {len(nodes)} nodes statically.")

if __name__ == "__main__":
    main()
