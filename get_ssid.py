import requests

# Replace these with your Pocket Option login credentials
EMAIL = "othekwande7@gmail.com" 
PASSWORD = "Othembela@7"

def get_session_key(email, password):
    url = "https://api.pocketoption.com/v1/user/login"
    data = {
        "email": email,
        "password": password
    }

    response = requests.post(url, json=data)
    if response.status_code == 200:
        result = response.json()
        ssid = result.get("data", {}).get("ssid")
        if ssid:
            print("✅ Your Pocket Option session key (SSID) is:")
            print(ssid)
        else:
            print("❌ Could not find SSID in response.")
    else:
        print(f"❌ Login failed: {response.status_code} {response.text}")

get_session_key(EMAIL, PASSWORD)
