import requests
import json

PROJECT_ID = "ikugmkhbmyohkdbfupnx"
CHIAVE_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlrdWdta2hibXlvaGtkYmZ1cG54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NTg3ODYsImV4cCI6MjA5OTQzNDc4Nn0.W0ASwL4tJxwd_ziYXImw0aXdj3RACSGObUd0tjKyN5w"

# Create bucket named "ricevute"
url = f"https://{PROJECT_ID}.supabase.co/storage/v1/bucket"
headers = {
    "apikey": CHIAVE_SUPABASE,
    "Authorization": f"Bearer {CHIAVE_SUPABASE}",
    "Content-Type": "application/json"
}

data = {
    "name": "ricevute"
}

try:
    r = requests.post(url, headers=headers, json=data, timeout=20)
    print(f"Status: {r.status_code}")
    print(json.dumps(r.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")