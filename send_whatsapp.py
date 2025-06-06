import os
import requests
import sys
from datetime import datetime

API_TOKEN = os.environ['WHAPI_TOKEN']
GROUP_ID = os.environ['WHAPI_GROUP_ID']
ACTION = os.environ['WHAPI_ACTION']  # "poll" or "reminder"

BASE_URL = 'https://gate.whapi.cloud'
HEADERS = {
    'Authorization': f'Bearer {API_TOKEN}',
    'Content-Type': 'application/json',
}

# Determine room based on day of week
# weekday() → Monday=0, Sunday=6
day_of_week = datetime.utcnow().weekday()
if day_of_week in [6, 0, 3]:  # Sunday (6), Monday (0), Thursday (3)
    room = "03.500"
else:  # Tuesday (1), Wednesday (2)
    room = "03.501"

def send_poll():
    url = f'{BASE_URL}/messages/poll'
    payload = {
        "to": GROUP_ID,
        "title": f"{room} מנחה ב-13:30, חדר",
        "options": ["מגיע", "תקראו לי אם חסר"],
        "count": 1
    }
    r = requests.post(url, headers=HEADERS, json=payload)
    print('Poll sent:', r.status_code, r.text)

def send_reminder():
    url = f'{BASE_URL}/messages/text'
    payload = {
        "to": GROUP_ID,
        "text": f"{room} תזכורת: אם עוד לא עניתם לסקר – זה הזמן! נתראה ב־13:30, חדר"
    }
    r = requests.post(url, headers=HEADERS, json=payload)
    print('Reminder sent:', r.status_code, r.text)

if ACTION == 'poll':
    send_poll()
elif ACTION == 'reminder':
    send_reminder()
else:
    print(f"Unknown action: {ACTION}")
    sys.exit(1)
