import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from backend.stock_service import StockService
import time

def verify():
    ss = StockService()
    print("Starts search for '600519' (Moutai)...")
    start = time.time()
    results = ss.search_stocks("600519")
    end = time.time()
    
    print(f"Search took {end - start:.2f}s")
    print(f"Found {len(results)} results.")
    
    for r in results:
        print(f"Code: {r['code']}, Name: {r['name']}")
        print(f"  Industry: {r.get('industry')}")
        print(f"  PE: {r.get('pe')}, Div: {r.get('dividend')}, Ratio: {r.get('ratio')}")
        print(f"  Stock5d: {r.get('stock5d')}, Industry5d: {r.get('industry5d')}")
        
    if not results:
        print("No results found!")
        return

    # Check if we got enrichment
    first = results[0]
    if first.get('pe') is not None or first.get('ratio') is not None:
        print("SUCCESS: Enrichment data present.")
    else:
        print("WARNING: Enrichment data MISSING (Maybe pywencai failed or returned nothing).")

if __name__ == "__main__":
    verify()
