import requests
import json
import math
from datetime import datetime
import time

# --- 1. CONFIGURAZIONE SCANSIONE ---
CENTRO_LAT = 45.805  # Centro della zona (es. Collio / Maniva)
CENTRO_LNG = 10.345
RAGGIO_KM = 5.0      # Raggio di esplorazione
PASSO_GRIGLIA_KM = 0.8 # Distanza tra i punti di analisi (0.8 km)

# Regole Micologiche
PIOGGIA_OTTIMALE = 50.0  # mm in 14 giorni
TEMP_SUOLO_MIN = 12.0
TEMP_SUOLO_MAX = 20.0

risultati = []

print(f"Avvio Radar: scansione boschi raggio {RAGGIO_KM}km da {CENTRO_LAT},{CENTRO_LNG}")

# --- 2. FUNZIONE PER GENERARE LA GRIGLIA ---
def genera_griglia(lat, lng, raggio, passo):
    punti = []
    # 1 grado lat = ~111 km, 1 grado lng = ~111 * cos(lat)
    lat_step = passo / 111.0
    lng_step = passo / (111.0 * math.cos(math.radians(lat)))
    
    passi = int(raggio / passo)
    for i in range(-passi, passi + 1):
        for j in range(-passi, passi + 1):
            if math.sqrt(i**2 + j**2) * passo <= raggio:
                punti.append((lat + i * lat_step, lng + j * lng_step))
    return punti

punti_mappa = genera_griglia(CENTRO_LAT, CENTRO_LNG, RAGGIO_KM, PASSO_GRIGLIA_KM)
print(f"Generati {len(punti_mappa)} punti da analizzare.")

# --- 3. SCANSIONE SATELLITARE BOSCHI (OpenStreetMap / Overpass API) ---
# Usiamo un bounding box generale per trovare tutte le foreste nella zona
min_lat = min([p[0] for p in punti_mappa]) - 0.01
max_lat = max([p[0] for p in punti_mappa]) + 0.01
min_lng = min([p[1] for p in punti_mappa]) - 0.01
max_lng = max([p[1] for p in punti_mappa]) + 0.01

overpass_query = f"""
[out:json];
(
  way["landuse"="forest"]({min_lat},{min_lng},{max_lat},{max_lng});
  way["natural"="wood"]({min_lat},{min_lng},{max_lat},{max_lng});
);
out center;
"""

print("Interrogazione GIS per mappatura Faggi/Conifere...")
response = requests.post("http://overpass-api.de/api/interpreter", data=overpass_query)
boschi_osm = response.json().get('elements', [])

# Filtriamo solo i punti della griglia che cadono "vicino" a un bosco censito
punti_boschivi = []
for p in punti_mappa:
    for b in boschi_osm:
        if 'center' in b:
            # Calcolo distanza approssimativa (se < 400m consideriamo il punto coperto da bosco)
            dist = math.sqrt((p[0] - b['center']['lat'])**2 + (p[1] - b['center']['lon'])**2) * 111.0
            if dist < 0.4:
                # Cerca di capire l'habitat dai metadati OSM
                tags = b.get('tags', {})
                tipo = "Bosco Misto"
                if tags.get('leaf_type') == 'broadleaved': tipo = "Latifoglie (Faggio/Castagno)"
                elif tags.get('leaf_type') == 'needleleaved': tipo = "Conifere (Abete/Pino)"
                
                punti_boschivi.append({"lat": p[0], "lng": p[1], "tipo": tipo})
                break # Trovato un bosco per questo punto, passa al prossimo

print(f"Sopravvissuti {len(punti_boschivi)} punti boschivi idonei. Inizio Analisi Meteo/Micologica...")

# --- 4. INCROCIO METEO E ALGORITMO MICOLOGICO ---
# (Limitiamo a max 30 punti per non sovraccaricare l'API gratis)
for p in punti_boschivi[:30]:
    url_meteo = f"https://api.open-meteo.com/v1/forecast?latitude={p['lat']}&longitude={p['lng']}&current=soil_temperature_0cm,soil_moisture_0_to_7cm&daily=precipitation_sum&past_days=14&timezone=Europe%2FRome"
    
    try:
        req = requests.get(url_meteo)
        dati = req.json()
        
        pioggia_14gg = sum(px for px in dati['daily']['precipitation_sum'][:14] if px is not None)
        temp_suolo = dati['current']['soil_temperature_0cm']
        umidita_suolo = dati['current']['soil_moisture_0_to_7cm']
        
        # Sistema a Punti (Max 100)
        score = 0
        
        # Parametro 1: Acqua (0-45 punti)
        if pioggia_14gg >= PIOGGIA_OTTIMALE: score += 45
        elif pioggia_14gg > 20: score += int((pioggia_14gg / PIOGGIA_OTTIMALE) * 45)
        
        # Parametro 2: Temperatura Suolo (0-35 punti) - FONDAMENTALE PER I PORCINI
        if TEMP_SUOLO_MIN <= temp_suolo <= TEMP_SUOLO_MAX: score += 35
        elif 8 <= temp_suolo < TEMP_SUOLO_MIN: score += 15 # Un po' freddo
        
        # Parametro 3: Umidità superficiale / Lettiera (0-20 punti)
        if umidita_suolo > 0.28: score += 20
        elif umidita_suolo > 0.15: score += 10
        
        # Bonus Habitat: I porcini (edulis) preferiscono Faggio/Abete in certe condizioni
        if "Faggio" in p['tipo'] and temp_suolo > 15: score += 5
        elif "Conifere" in p['tipo'] and temp_suolo < 14: score += 5
        
        score = min(100, score) # Cap a 100%
        
        risultati.append({
            "lat": p['lat'], "lng": p['lng'], 
            "raggio": PASSO_GRIGLIA_KM * 500, # Per disegnare il cerchio sulla mappa
            "score": score,
            "tipo_bosco": p['tipo'],
            "dati": { "pioggia_mm": round(pioggia_14gg,1), "temp_suolo": temp_suolo, "umidita_suolo": umidita_suolo }
        })
        time.sleep(0.5) # Pausa gentile per non bloccare l'API meteo
    except Exception as e:
        pass

# --- 5. SALVATAGGIO ---
dati_finali = {
    "ultimo_aggiornamento": datetime.now().strftime("%d/%m/%Y %H:%M"),
    "zone": risultati
}

with open("previsioni.json", "w") as f:
    json.dump(dati_finali, f)

print(f"Analisi completata. Generata heatmap su {len(risultati)} micro-zone.")
