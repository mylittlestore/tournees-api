"""
FastAPI — API REST pour l'app mobile des chauffeurs
Hébergé sur Render.com
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import json, os, pandas as pd
from datetime import date
from pathlib import Path

app = FastAPI(title="Tournées API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSION_FILE = "tournees_session.json"
BASE_DIR     = Path(__file__).parent

# Servir la PWA
pwa_dir = BASE_DIR / "pwa"
if pwa_dir.exists():
    app.mount("/app", StaticFiles(directory=str(pwa_dir), html=True), name="pwa")

@app.get("/")
def root():
    return {"status": "ok", "date": str(date.today())}

def charger_session():
    if not os.path.exists(SESSION_FILE):
        raise HTTPException(404, "Aucune tournée chargée — uploadez d'abord le fichier session")
    with open(SESSION_FILE, encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/chauffeurs")
def liste_chauffeurs():
    session = charger_session()
    routes = pd.DataFrame(session.get("routes", []))
    if routes.empty:
        raise HTTPException(404, "Tournées vides")
    chauffeurs = [c for c in routes["chauffeur_final"].unique() if c != "NON_ASSIGNE"]
    return {"date": str(date.today()), "chauffeurs": sorted(chauffeurs)}

@app.get("/api/tournee/{chauffeur}")
def get_tournee(chauffeur: str):
    session = charger_session()
    routes = pd.DataFrame(session.get("routes", []))
    if routes.empty:
        raise HTTPException(404, "Tournées vides")
    ch = chauffeur.upper()
    g  = routes[routes["chauffeur_final"] == ch]
    if g.empty:
        raise HTTPException(404, f"Chauffeur {ch} introuvable")
    g = g.sort_values("ordre_livraison")
    arrets = []
    for _, row in g.iterrows():
        arrets.append({
            "ordre":    int(row["ordre_livraison"]),
            "adresse":  str(row["adresse"]),
            "cp":       str(int(row.get("cp", 0))),
            "commune":  str(row.get("commune", "")),
            "lat":      float(row["lat"]),
            "lon":      float(row["lon"]),
            "nb_colis": int(row["nb_colis"]),
            "refs":     [r.strip() for r in str(row.get("colis_liste","")).split(",") if r.strip()],
        })
    return {
        "chauffeur":  ch,
        "date":       str(date.today()),
        "nb_arrets":  len(arrets),
        "nb_colis":   int(g["nb_colis"].sum()),
        "depot":      {"lat": 50.892487, "lon": 4.425370, "label": "Dépôt Haren"},
        "arrets":     arrets,
    }

# Upload session depuis Streamlit
from fastapi import UploadFile, File
@app.post("/api/upload-session")
async def upload_session(file: UploadFile = File(...)):
    content = await file.read()
    with open(SESSION_FILE, "wb") as f:
        f.write(content)
    return {"ok": True, "size": len(content)}

# État livraisons
livraisons_etat = {}

@app.post("/api/livrer/{chauffeur}/{ordre}")
def marquer_livre(chauffeur: str, ordre: int):
    ch = chauffeur.upper()
    if ch not in livraisons_etat:
        livraisons_etat[ch] = {}
    livraisons_etat[ch][ordre] = True
    return {"ok": True}

@app.get("/api/etat/{chauffeur}")
def get_etat(chauffeur: str):
    return {"chauffeur": chauffeur.upper(), "livres": livraisons_etat.get(chauffeur.upper(), {})}
