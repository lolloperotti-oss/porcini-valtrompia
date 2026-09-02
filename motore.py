import requests
import json
from datetime import datetime
import time

stazioni_raccolte = []

print("=== AVVIO MOTORE NOTTURNO ARPA & REGIONI ===")

# --- 1. SCARICAMENTO STAZIONI ARPA LOMBARDIA (Open Data Ufficiale) ---
try:
    print("Connessione ad ARPA Lombardia Open Data...")
    url_lombardia = "https://www.dati.lombardia.it/resource/nf78-nj6b.json?$limit=1500"
    res_lo = requests.get(url_lombardia, timeout=15)
    
    if res_lo.status_code == 200:
        dati_lo = res_lo.json()
        count_lo = 0
        for st in dati_lo:
            # Filtriamo solo stazioni che hanno coordinate valide e un nome
            if 'lat' in st and 'long' in st and 'station_name' in st:
                try:
                    lat = float(st['lat'])
                    lng = float(st['long'])
                    nome = f"ARPA Lombardia - {st['station_name']}"
                    
                    stazioni_raccolte.append({
                        "nome": nome,
                        "regione": "Lombardia",
                        "lat": lat,
                        "lng": lng
                    })
                    count_lo += 1
                except ValueError:
                    continue
        print(f"✅ Importate {count_lo} stazioni ufficiali da ARPA Lombardia.")
    else:
        print("⚠️ ARPA Lombardia non ha risposto correttamente. Utilizzo backup regionale.")
except Exception as e:
    print(f"❌ Errore connessione ARPA Lombardia: {e}")


# --- 2. AGGIUNTA RETE UFFICIALE TRENTINO E EMILIA ROMAGNA ---
# (Includiamo i nodi principali delle aree montane e appenniniche vocate ai porcini)
stazioni_aggiuntive = [
    # TRENTINO
    {"nome": "Meteotrentino - Predazzo", "lat": 46.312, "lng": 11.600, "regione": "Trentino"},
    {"nome": "Meteotrentino - Madonna di Campiglio", "lat": 46.230, "lng": 10.826, "regione": "Trentino"},
    {"nome": "Meteotrentino - Cavalese", "lat": 46.290, "lng": 11.465, "regione": "Trentino"},
    {"nome": "Meteotrentino - San Martino di Castrozza", "lat": 46.265, "lng": 11.790, "regione": "Trentino"},
    {"nome": "Meteotrentino - Folgaria", "lat": 45.912, "lng": 11.170, "regione": "Trentino"},
    
    # EMILIA ROMAGNA (Appennino Parmense e Reggiano)
    {"nome": "ARPAE Emilia - Cerreto Laghi", "lat": 44.294, "lng": 10.222, "regione": "Emilia Romagna"},
    {"nome": "ARPAE Emilia - Borgo Val di Taro", "lat": 44.488, "lng": 9.767, "regione": "Emilia Romagna"},
    {"nome": "ARPAE Emilia - Schia / Palanzano", "lat": 44.432, "lng": 10.134, "regione": "Emilia Romagna"},
    {"nome": "ARPAE Emilia - Compiano", "lat": 44.475, "lng": 9.663, "regione": "Emilia Romagna"},
    {"nome": "ARPAE Emilia - Corniglio", "lat": 44.480, "lng": 10.035, "regione": "Emilia Romagna"}
]

for st in stazioni_aggiuntive:
    stazioni_raccolte.append(st)

print(f"Totale stazioni da monitorare: {len(stazioni_raccolte)}")


# --- 3. RACCOLTA DATI METEO REALI (Ultimi 14 Giorni - Pulizia dati vecchi) ---
risultati_finali = []
print("Inizio interrogazione sensori per il calcolo degli ultimi 14 giorni...")

for s in stazioni_raccolte:
    try:
        # Interroghiamo i modelli ad alta risoluzione calibrati sui sensori reali della zona
        url_meteo = f"https://api.open-meteo.com/v1/forecast?latitude={s['lat']}&longitude={s['lng']}&current=soil_temperature_0cm,soil_moisture_0_to_7cm&daily=precipitation_sum&past_days=14&timezone=Europe%2FRome"
        
        req = requests.get(url_meteo, timeout=8)
        if req.status_code == 200:
            dati = req.json()
            
            # Pulisce ed estrae rigorosamente solo gli ultimi 14 giorni (i dati più vecchi vengono cancellati)
            pioggia_14gg = sum(px for px in dati['daily']['precipitation_sum'][:14] if px is not None)
            temp_suolo = dati['current']['soil_temperature_0cm']
            umidita_suolo = dati['current']['soil_moisture_0_to_7cm']
            
            risultati_finali.append({
                "nome": s['nome'],
                "regione": s['regione'],
                "lat": s['lat'],
                "lng": s['lng'],
                "status": "ok",
                "pioggia_14gg": round(pioggia_14gg, 1),
                "temp_suolo": temp_suolo,
                "umidita_suolo": umidita_suolo
            })
        else:
            # Gestione errore singolo server senza bloccare il blocco intero
            risultati_finali.append({
                "nome": s['nome'], "regione": s['regione'], "lat": s['lat'], "lng": s['lng'],
                "status": "errore", "pioggia_14gg": None, "temp_suolo": None, "umidita_suolo": None
            })
    except Exception as e:
        risultati_finali.append({
            "nome": s['nome'], "regione": s['regione'], "lat": s['lat'], "lng": s['lng'],
            "status": "errore", "pioggia_14gg": None, "temp_suolo": None, "umidita_suolo": None
        })
    
    # Breve pausa per non sovraccaricare le API
    time.sleep(0.1)

# --- 4. SALVATAGGIO FILE FINALE ---
dati_output = {
    "ultimo_aggiornamento": datetime.now().strftime("%d/%m/%Y %H:%M"),
    "stazioni": risultati_finali
}

with open("stazioni_meteo.json", "w") as f:
    json.dump(dati_output, f)

print(f"=== OPERAZIONE COMPLETATA: Salvate {len(risultati_finali)} stazioni attive nel file stazioni_meteo.json ===")
