import requests, base64

# Step 1: Get captcha
res = requests.get("http://127.0.0.1:5001/api/v1/getCaptcha").json()
session_id = res["sessionId"]
print("Session:", session_id)

# Step 2: Show captcha
data = res["image"].split(",")[1]
with open("captcha.png", "wb") as f:
    f.write(base64.b64decode(data))
print("Open captcha.png and type what you see:")

captcha = input("Captcha: ")
gstin = input("GSTIN: ")

# Step 3: Submit
payload = {"sessionId": session_id, "GSTIN": gstin, "captcha": captcha}
res2 = requests.post("http://127.0.0.1:5001/api/v1/getGSTDetails", json=payload)
print(res2.json())
