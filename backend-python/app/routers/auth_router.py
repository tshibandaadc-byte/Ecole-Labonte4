# =========================================
# app/routers/auth_router.py
# =========================================
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth_schemas import ConnexionRequete, TokenReponse
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["Authentification"])


@router.post("/login", response_model=TokenReponse)
def login(donnees: ConnexionRequete, db: Session = Depends(get_db)):
    return auth_service.connecter(db, donnees.identifiant, donnees.mot_de_passe)
