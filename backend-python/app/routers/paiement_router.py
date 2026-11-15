# =========================================
# app/routers/paiement_router.py
# =========================================
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import utilisateur_courant, exiger_role
from app.schemas.autres_schemas import PaiementRequete
from app.services import paiement_service

router = APIRouter(tags=["Paiements & Frais"])


@router.get("/api/frais/eleve/{eleve_id}")
def lister_frais(
    eleve_id: int,
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(utilisateur_courant),
):
    frais = paiement_service.lister_frais_par_eleve(db, eleve_id)
    return {"success": True, "data": frais}


@router.post("/api/paiements", status_code=201)
def payer(
    donnees: PaiementRequete,
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(
        exiger_role("assistant", "direction", "promoteur", "parent", "eleve")
    ),
):
    paiement = paiement_service.enregistrer_paiement(db, donnees, encaisse_par=utilisateur["id"])
    return {"success": True, "message": "Paiement enregistré.", "data": paiement}


@router.get("/api/paiements/eleve/{eleve_id}")
def historique(
    eleve_id: int,
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(utilisateur_courant),
):
    paiements = paiement_service.historique_paiements(db, eleve_id)
    return {"success": True, "data": paiements}


@router.get("/api/paiements/stats/jour")
def stats_du_jour(
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(exiger_role("assistant", "direction", "promoteur")),
):
    stats = paiement_service.paiements_du_jour(db)
    return {"success": True, "data": stats}


@router.get("/api/paiements/stats/recouvrement")
def stats_recouvrement(
    annee: str = Query(..., description="Ex: 2026-2027"),
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(exiger_role("direction", "promoteur")),
):
    stats = paiement_service.taux_recouvrement(db, annee)
    return {"success": True, "data": stats}
