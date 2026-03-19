import requests
import json
import time

input_img = "test_input.jpg"
ref_img = "test_ref.jpg"

print("Hitting API...")
url = "http://127.0.0.1:8000/generate-preset"
with open(input_img, "rb") as f1, open(ref_img, "rb") as f2:
    files = {
        "input_image": ("input.jpg", f1, "image/jpeg"),
        "reference_image": ("ref.jpg", f2, "image/jpeg")
    }
    t0 = time.time()
    response = requests.post(url, files=files)
    t1 = time.time()

print(f"Time taken: {t1-t0:.2f}s")
print("Response:", response.status_code)
try:
    print(json.dumps(response.json(), indent=2))
except:
    print(response.text)
