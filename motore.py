import requests
import json
from datetime import datetime
import time

# RETE DI STAZIONI (Lombardia, Trentino, Emilia, Liguria)
# Puoi aggiungere tutte le coordinate delle centraline che vuoi qui sotto
STAZIONI = [
    # LOMBARDIA
    {"nome": "Passo Maniva (ARPA)", "lat": 45.823, "lng": 10.410, "regione": "Lombardia"},
    {"nome": "Bovegno (ARPA)", "lat": 45.750, "lng": 10.275, "regione": "Lombardia"},
    {"nome": "Aprica / Corteno", "lat": 46.152, "lng": 10.153, "regione": "Lombardia"},
    # TRENTINO
    {"nome": "Predazzo / Val di Fiemme", "lat": 46.312, "lng": 11.600, "regione": "Trentino"},
    {"nome": "Madonna di Campiglio", "lat": 46.230, "lng": 10.826, "regione": "Trentino"},
    # EMILIA ROMAGNA
    {"nome": "Cerreto Laghi", "lat": 44.294, "lng": 10.222, "regione": "Emilia Romagna"},
    {"nome": "Borgo Val di Taro", "lat": 44.488, "lng": 9.767, "regione": "Emilia Romagna"},
    # LIGURIA
    {"nome": "Santo Stefano d'Aveto", "lat": 44.545, "lng": 9.450, "regione": "Liguria"},
    {"nome": "Sassello", "lat": 44.478, "lng": 8.490, "regione": "Liguria"}
]

risultati = []
print("Avvio scaricamento dati notturno...")

for s in STAZIONI:
    try:
        # Il robot interroga il server per la centralina
        url = f"https://api.open-meteo.com/v1/forecast?latitude={s['lat']}&longitude={s['lng']}&current=soil_temperature_0cm,soil_moisture_0_to_7cm&daily=precipitation_sum&past_days=14&timezone=Europe%2FRome"
        
        req = requests.get(url, timeout=10)
        req.raise_for_status() # Se il server è giù o in manutenzione (es. Errore 500), genera un'eccezione
        
        dati = req.json()
        
        # Elimina i dati vecchi: calcola solo ESATTAMENTE gli ultimi 14 gg
        pioggia_14gg = sum(px for px in dati['daily']['precipitation_sum'][:14] if px is not None)
        temp_suolo = dati['current']['soil_temperature_0cm']
        umidita_suolo = dati['current']['soil_moisture_0_to_7cm']
        
        risultati.append({
            "nome": s['nome'], "regione": s['regione'], "lat": s['lat'], "lng": s['lng'],
            "status": "ok", # IL SERVER HA RISPOSTO
            "pioggia_14gg": round(pioggia_14gg, 1),
            "temp_suolo": temp_suolo,
            "umidita_suolo": umidita_suolo
        })
        print(f"✅ {s['nome']}: Dati raccolti con successo.")
        
    except Exception as e:
        # IL BYPASS: Se il server è in manutenzione o cade la linea
        print(f"❌ Errore server per {s['nome']} (Manutenzione/Offline).")
        risultati.append({
            "nome": s['nome'], "regione": s['regione'], "lat": s['lat'], "lng": s['lng'],
            "status": "errore", # REGISTRA IL SERVER DOWN
            "pioggia_14gg": None, "temp_suolo": None, "umidita_suolo": None
        })
        
    time.sleep(0.5) # Pausa di cortesia per non farsi bloccare

dati_finali = {
    "ultimo_aggiornamento": datetime.now().strftime("%d/%m/%Y %H:%M"),
    "stazioni": risultati
}

with open("stazioni_meteo.json", "w") as f:
    json.dump(dati_finali, f)

print("File JSON aggiornato e ripulito dai dati vecchi. Pronto per la mappa!")
