# =========================================
# main.py — Point d'entrée FastAPI
# =========================================
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.config import settings, verifier_config_production
from app.routers import auth_router, eleve_router, note_router, paiement_router, communication_router

# Bloque le démarrage si JWT_SECRET ou CORS_ORIGINS sont encore aux valeurs
# par défaut en environnement de production (ENVIRONMENT=prod dans .env).
verifier_config_production()

app = FastAPI(
    title="API École La Bonté",
    description="Backend pour l'application de gestion scolaire École La Bonté",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # domaines autorisés, définis via .env (CORS_ORIGINS)
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Routes
app.include_router(auth_router.router)
app.include_router(eleve_router.router)
app.include_router(note_router.router)
app.include_router(paiement_router.router)
app.include_router(communication_router.router)


@app.get("/api/health")
def health():
    return {"success": True, "message": "API École La Bonté opérationnelle."}


@app.exception_handler(IntegrityError)
def gerer_erreur_integrite(request: Request, exc: IntegrityError):
    """Traduit les violations de contraintes SQL (doublons, clés étrangères) en réponses claires."""
    message = str(exc.orig)
    if "unique" in message.lower():
        detail = "Une ressource avec ces informations existe déjà (doublon)."
    elif "foreign key" in message.lower():
        detail = "Référence invalide (clé étrangère non trouvée)."
    else:
        detail = "Erreur d'intégrité des données."
    return JSONResponse(status_code=409, content={"success": False, "message": detail})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
