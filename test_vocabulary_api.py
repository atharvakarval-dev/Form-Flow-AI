import requests
import json
import time

BASE_URL = "http://localhost:8001"

def test_vocabulary_api():
    print(f"Testing Vocabulary API at {BASE_URL}...")
    
    # 1. Health Check
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=2)
        print(f"Health Check: {r.status_code}")
        if r.status_code != 200:
            print("Backend not healthy. Aborting.")
            return
    except Exception as e:
        print(f"Backend not reachable: {e}")
        return

    # 2. Get Corrections (Test for 500 Error Fix)
    try:
        print("Fetching corrections...")
        r = requests.get(f"{BASE_URL}/vocabulary/corrections")
        print(f"Get Corrections Status: {r.status_code}")
        if r.status_code == 200:
            print(f"Corrections: {len(r.json())} items found.")
            print("✅ 500 Error Fixed!")
        else:
            print(f"❌ Failed: {r.status_code} - {r.text}")
            return
    except Exception as e:
        print(f"❌ Error fetching corrections: {e}")
        return

    # 3. Add Correction
    try:
        print("Adding test correction...")
        payload = {
            "heard": "Github",
            "correct": "GitHub",
            "context": "Coding"
        }
        r = requests.post(f"{BASE_URL}/vocabulary/correction", json=payload)
        print(f"Add Status: {r.status_code}")
        if r.status_code == 200:
            new_id = r.json()['id']
            print(f"✅ Added correction ID: {new_id}")
            
            # 4. Apply Correction
            print("Testing application...")
            apply_r = requests.post(f"{BASE_URL}/vocabulary/apply?text=Check Github repo")
            res = apply_r.json()
            if res['corrected'] == "Check GitHub repo":
                print("✅ Correction applied successfully!")
            else:
                print(f"❌ Correction failed. Got: {res['corrected']}")

            # 5. Delete (Clean up)
            print(f"Deleting correction {new_id}...")
            requests.delete(f"{BASE_URL}/vocabulary/correction/{new_id}")
            print("✅ Cleaned up.")
            
        else:
            print(f"❌ Add Failed: {r.text}")

    except Exception as e:
        print(f"❌ Error during add/test flow: {e}")

if __name__ == "__main__":
    test_vocabulary_api()
