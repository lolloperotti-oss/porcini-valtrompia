import requests
import json
from datetime import datetime
import time

# 1. LA TUA RETE DI STAZIONI METEO (Aggiungi tutte quelle che vuoi!)
STAZIONI = [
    # LOMBARDIA (Val Trompia e dintorni)
    {"nome": "Passo Maniva", "lat": 45.823, "lng": 10.410, "regione": "Lombardia"},
    {"nome": "Bovegno", "lat": 45.750, "lng": 10.275, "regione": "Lombardia"},
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
print(f"Avvio scaricamento dati per {len(STAZIONI)} stazioni...")

for s in STAZIONI:
    # Richiede i dati ad alta risoluzione interpolati per quella coordinata esatta
    url = f"https://api.open-meteo.com/v1/forecast?latitude={s['lat']}&longitude={s['lng']}&current=soil_temperature_0cm,soil_moisture_0_to_7cm&daily=precipitation_sum&past_days=14&timezone=Europe%2FRome"
    
    try:
        req = requests.get(url)
        dati = req.json()
        
        # Calcola i mm totali caduti ESATTAMENTE negli ultimi 14 giorni (elimina il resto)
        pioggia_14gg = sum(px for px in dati['daily']['precipitation_sum'][:14] if px is not None)
        temp_suolo = dati['current']['soil_temperature_0cm']
        umidita_suolo = dati['current']['soil_moisture_0_to_7cm']
        
        risultati.append({
            "nome": s['nome'], 
            "regione": s['regione'],
            "lat": s['lat'], 
            "lng": s['lng'],
            "pioggia_14gg": round(pioggia_14gg, 1),
            "temp_suolo": temp_suolo,
            "umidita_suolo": umidita_suolo
        })
        print(f"✅ Dati scaricati per: {s['nome']}")
        time.sleep(0.5) # Pausa per non intasare il server
    except Exception as e:
        print(f"❌ Errore con {s['nome']}: {e}")

# 2. SOVRASCRIVE IL FILE (i vecchi dati vengono eliminati definitivamente)
dati_finali = {
    "ultimo_aggiornamento": datetime.now().strftime("%d/%m/%Y %H:%M"),
    "stazioni": risultati
}

# Salveremo questo file che l'HTML leggerà
with open("stazioni_meteo.json", "w") as f:
    json.dump(dati_finali, f)

print("File stazioni_meteo.json generato con successo e ripulito dai dati vecchi!")
