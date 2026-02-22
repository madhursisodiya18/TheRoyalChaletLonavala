import requests
import time

data = {
    "date_range": "01/07/2025 to 05/07/2025",
    "guests": 2
}

url = "http://127.0.0.1:5000/api/calculate-price"

start = time.time()
response = requests.post(url, json=data)
elapsed = time.time() - start

print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
print(f"Elapsed time: {elapsed:.3f} seconds") 