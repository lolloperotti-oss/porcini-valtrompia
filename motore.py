import requests
import json
import os
from datetime import datetime, timedelta

# ============================================================
# CONFIG
# ============================================================
# Bounding box larga sulla Valtrompia e dintorni (Brescia nord-ovest)
BBOX = {"lat_min": 45.60, "lat_max": 45.90, "lng_min": 10.05, "lng_max": 10.50}
STORICO_FILE = "storico_pioggia.json"   # accumulo locale, committato dal workflow ogni notte
OUTPUT_FILE = "stazioni_meteo.json"
GIORNI_FINESTRA = 14

session = requests.Session()
session.headers.update({"User-Agent": "cerca-porcini-valtrompia/1.0"})


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ============================================================
# 1. ANAGRAFICA ARPA — trova i sensori Precipitazione/Temperatura
#    dentro la bounding box (campi reali: idsensore, nomestazione,
#    tipologia, provincia, lat, lng — NON 'station_name'/'long')
# ============================================================
def scarica_anagrafica_arpa():
    log("Scarico anagrafica sensori ARPA Lombardia (nf78-nj6b)...")
    url = "https://www.dati.lombardia.it/resource/nf78-nj6b.json"
    params = {"$limit": 5000}
    try:
        r = session.get(url, params=params, timeout=20)
        r.raise_for_status()
        dati = r.json()
    except Exception as e:
        log(f"❌ Errore anagrafica ARPA: {e}")
        return {}

    stazioni = {}  # idstazione -> {nomestazione, lat, lng, quota, sensori:{tipologia:idsensore}}
    for row in dati:
        try:
            lat = float(row.get("lat", 0))
            lng = float(row.get("lng", 0))
        except (TypeError, ValueError):
            continue
        if not (BBOX["lat_min"] <= lat <= BBOX["lat_max"] and BBOX["lng_min"] <= lng <= BBOX["lng_max"]):
            continue
        tipologia = row.get("tipologia", "")
        if tipologia not in ("Precipitazione", "Temperatura"):
            continue
        idstazione = row.get("idstazione")
        nomestazione = row.get("nomestazione", "Sconosciuta")
        idsensore = row.get("idsensore")
        if idstazione not in stazioni:
            stazioni[idstazione] = {
                "nome": f"ARPA Lombardia - {nomestazione}",
                "regione": "Lombardia",
                "lat": lat,
                "lng": lng,
                "sensori": {}
            }
        stazioni[idstazione]["sensori"][tipologia] = idsensore

    log(f"✅ Trovate {len(stazioni)} stazioni ARPA reali in Val Trompia e dintorni.")
    return stazioni


# ============================================================
# 2. LETTURE REALI (647i-nhxk, dati del mese in corso).
#    stato 'VV'/'VA' = dato validato/valido.
# ============================================================
def scarica_letture(idsensori, giorno_da):
    if not idsensori:
        return {}
    log(f"Scarico letture reali per {len(idsensori)} sensori da {giorno_da}...")
    url = "https://www.dati.lombardia.it/resource/647i-nhxk.json"
    id_list = ",".join(f"'{i}'" for i in idsensori)
    where = f"idsensore in ({id_list}) AND data >= '{giorno_da}T00:00:00' AND (stato='VV' OR stato='VA')"
    try:
        r = session.get(url, params={"$where": where, "$limit": 200000}, timeout=30)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        log(f"⚠️ Errore letture ARPA (dataset mese-corrente, normale a inizio mese): {e}")
        return {}

    per_sensore = {}
    for row in rows:
        idsens = row.get("idsensore")
        try:
            valore = float(row.get("valore"))
        except (TypeError, ValueError):
            continue
        per_sensore.setdefault(idsens, []).append((row.get("data"), valore))
    return per_sensore


# ============================================================
# 3. STORICO LOCALE — accumula un giorno alla volta per costruirsi
#    una vera finestra di 14gg indipendente dal reset mensile ARPA
# ============================================================
def aggiorna_storico(stazioni, letture_oggi):
    storico = {}
    if os.path.exists(STORICO_FILE):
        try:
            with open(STORICO_FILE) as f:
                storico = json.load(f)
        except Exception:
            storico = {}

    oggi = datetime.now().strftime("%Y-%m-%d")
    for idstazione, info in stazioni.items():
        sensori = info["sensori"]
        pioggia_oggi = 0.0
        if "Precipitazione" in sensori:
            valori = letture_oggi.get(sensori["Precipitazione"], [])
            pioggia_oggi = round(sum(v for _, v in valori), 1)

        storico.setdefault(idstazione, {})
        storico[idstazione][oggi] = pioggia_oggi

        # pulizia: tieni solo gli ultimi 30 giorni per non far crescere il file all'infinito
        soglia = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        storico[idstazione] = {d: v for d, v in storico[idstazione].items() if d >= soglia}

    with open(STORICO_FILE, "w") as f:
        json.dump(storico, f)
    return storico


def pioggia_14gg_da_storico(storico, idstazione):
    if idstazione not in storico:
        return None
    soglia = (datetime.now() - timedelta(days=GIORNI_FINESTRA)).strftime("%Y-%m-%d")
    valori = [v for d, v in storico[idstazione].items() if d >= soglia]
    if not valori:
        return None
    return round(sum(valori), 1)


# ============================================================
# 4. STAZIONI DI SCORTA (Trentino / Emilia) — via Open-Meteo,
#    tenute come prima per copertura fuori Lombardia
# ============================================================
STAZIONI_SCORTA = [
    {"nome": "Meteotrentino - Predazzo", "lat": 46.312, "lng": 11.600, "regione": "Trentino"},
    {"nome": "Meteotrentino - Madonna di Campiglio", "lat": 46.230, "lng": 10.826, "regione": "Trentino"},
    {"nome": "Meteotrentino - Cavalese", "lat": 46.290, "lng": 11.465, "regione": "Trentino"},
    {"nome": "Meteotrentino - San Martino di Castrozza", "lat": 46.265, "lng": 11.790, "regione": "Trentino"},
    {"nome": "Meteotrentino - Folgaria", "lat": 45.912, "lng": 11.170, "regione": "Trentino"},
    {"nome": "ARPAE Emilia - Cerreto Laghi", "lat": 44.294, "lng": 10.222, "regione": "Emilia Romagna"},
    {"nome": "ARPAE Emilia - Borgo Val di Taro", "lat": 44.488, "lng": 9.767, "regione": "Emilia Romagna"},
    {"nome": "ARPAE Emilia - Schia / Palanzano", "lat": 44.432, "lng": 10.134, "regione": "Emilia Romagna"},
    {"nome": "ARPAE Emilia - Compiano", "lat": 44.475, "lng": 9.663, "regione": "Emilia Romagna"},
    {"nome": "ARPAE Emilia - Corniglio", "lat": 44.480, "lng": 10.035, "regione": "Emilia Romagna"},
]


def dati_open_meteo(lat, lng):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lng,
        "current": "soil_temperature_0cm,soil_moisture_0_to_7cm",
        "daily": "precipitation_sum", "past_days": GIORNI_FINESTRA,
        "timezone": "Europe/Rome"
    }
    r = session.get(url, params=params, timeout=10)
    r.raise_for_status()
    j = r.json()
    pioggia = sum(v for v in j["daily"]["precipitation_sum"] if v is not None)
    return {
        "pioggia_14gg": round(pioggia, 1),
        "temp_suolo": j["current"]["soil_temperature_0cm"],
        "umidita_suolo": j["current"]["soil_moisture_0_to_7cm"]
    }


# ============================================================
# MAIN
# ============================================================
def main():
    log("=== AVVIO MOTORE NOTTURNO ARPA + SCORTA ===")
    risultati = []

    # --- ARPA Lombardia (dato reale) ---
    stazioni_arpa = scarica_anagrafica_arpa()
    tutti_idsensori = [s["sensori"][t] for s in stazioni_arpa.values() for t in s["sensori"]]
    giorno_da = datetime.now().replace(day=1).strftime("%Y-%m-%d")  # da inizio mese corrente
    letture = scarica_letture(tutti_idsensori, giorno_da)
    storico = aggiorna_storico(stazioni_arpa, letture)

    for idstazione, info in stazioni_arpa.items():
        pioggia = pioggia_14gg_da_storico(storico, idstazione)
        temp = None
        if "Temperatura" in info["sensori"]:
            valori_t = letture.get(info["sensori"]["Temperatura"], [])
            if valori_t:
                valori_t.sort(key=lambda x: x[0])
                temp = valori_t[-1][1]  # lettura più recente
        risultati.append({
            "nome": info["nome"], "regione": info["regione"],
            "lat": info["lat"], "lng": info["lng"],
            "status": "ok" if pioggia is not None else "parziale (storico in accumulo)",
            "pioggia_14gg": pioggia,
            "temp_aria": temp,
            "fonte": "ARPA Lombardia (dato reale)"
        })

    # --- Scorta Trentino/Emilia (Open-Meteo) ---
    log("Scarico dati di scorta Trentino/Emilia da Open-Meteo...")
    for s in STAZIONI_SCORTA:
        try:
            m = dati_open_meteo(s["lat"], s["lng"])
            risultati.append({
                "nome": s["nome"], "regione": s["regione"],
                "lat": s["lat"], "lng": s["lng"],
                "status": "ok", **m,
                "fonte": "Open-Meteo (modello, non centralina fisica)"
            })
        except Exception as e:
            risultati.append({
                "nome": s["nome"], "regione": s["regione"],
                "lat": s["lat"], "lng": s["lng"],
                "status": "errore", "pioggia_14gg": None, "temp_suolo": None, "umidita_suolo": None
            })

    output = {
        "ultimo_aggiornamento": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "nota": "Pioggia Lombardia = dato reale ARPA accumulato giorno per giorno da questo script (vedi storico_pioggia.json). Fuori Lombardia = modello Open-Meteo.",
        "stazioni": risultati
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, ensure_ascii=False)
    log(f"=== COMPLETATO: {len(risultati)} stazioni salvate in {OUTPUT_FILE} ===")


if __name__ == "__main__":
    main()
