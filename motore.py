import requests
import json
from datetime import datetime

# 1. Le tue zone in Val Trompia (potrai aggiungerne quante ne vuoi)
zone = [
    {"nome": "Vaghezza / Passo Piazze", "lat": 45.774, "lng": 10.317, "quota": 1350},
    {"nome": "Collio / Maniva", "lat": 45.805, "lng": 10.345, "quota": 1500},
    {"nome": "Pezzaze / Caregno", "lat": 45.735, "lng": 10.250, "quota": 1000},
    {"nome": "Bovegno / Lavacolo", "lat": 45.715, "lng": 10.275, "quota": 900}
]

risultati = []

print("Avvio raccolta dati meteo notturna...")

for z in zone:
    # 2. Scarica i dati meteo degli ultimi 14 giorni per quella coordinata esatta
    url = f"https://api.open-meteo.com/v1/forecast?latitude={z['lat']}&longitude={z['lng']}&current=temperature_2m,soil_moisture_0_to_7cm,wind_speed_10m&daily=precipitation_sum&past_days=14&timezone=Europe%2FRome"
    
    try:
        req = requests.get(url)
        dati = req.json()
        
        pioggia_14gg = sum(p for p in dati['daily']['precipitation_sum'][:14] if p is not None)
        temp_ora = dati['current']['temperature_2m']
        umidita_suolo = dati['current']['soil_moisture_0_to_7cm']
        
        # 3. Il tuo Algoritmo Segreto (da 0 a 100%)
        punteggio = 0
        if pioggia_14gg > 40: punteggio += 40
        elif pioggia_14gg > 20: punteggio += 20
        
        if 12 <= temp_ora <= 20: punteggio += 30
        
        if umidita_suolo > 0.30: punteggio += 30
        elif umidita_suolo < 0.20: punteggio -= 20 # Troppo secco
        
        # Limita tra 0 e 100
        punteggio = max(0, min(100, punteggio))
        
        risultati.append({
            "zona": z["nome"], "lat": z["lat"], "lng": z["lng"],
            "score": punteggio,
            "dati": { "pioggia_mm": round(pioggia_14gg,1), "temp": temp_ora, "umidita_suolo": umidita_suolo }
        })
        print(f"✅ {z['nome']} analizzata. Score: {punteggio}%")
    except Exception as e:
        print(f"❌ Errore con {z['nome']}: {e}")

# 4. Salva il file per la mappa
dati_finali = {
    "ultimo_aggiornamento": datetime.now().strftime("%d/%m/%Y %H:%M"),
    "zone": risultati
}

with open("previsioni.json", "w") as f:
    json.dump(dati_finali, f)

print("File previsioni.json generato con successo!")
