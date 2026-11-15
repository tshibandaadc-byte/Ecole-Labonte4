# =========================================
# app/routers/note_router.py
# =========================================
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import utilisateur_courant, exiger_role
from app.schemas.autres_schemas import (
    SaisirNoteRequete, SaisirNotesGroupeesRequete, PublierBulletinRequete,
)
from app.services import note_service

router = APIRouter(tags=["Notes & Bulletins"])


@router.post("/api/notes", status_code=201)
def saisir(
    donnees: SaisirNoteRequete,
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(exiger_role("professeur")),
):
    prof_id = note_service.professeur_id_de_utilisateur(db, utilisateur["id"])
    note = note_service.saisir_note(db, donnees, professeur_id=prof_id)
    return {"success": True, "message": "Note enregistrée.", "data": note}


@router.post("/api/notes/groupe", status_code=201)
def saisir_groupe(
    donnees: SaisirNotesGroupeesRequete,
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(exiger_role("professeur")),
):
    prof_id = note_service.professeur_id_de_utilisateur(db, utilisateur["id"])
    resultats = note_service.saisir_notes_groupees(db, donnees.notes, professeur_id=prof_id)
    return {"success": True, "message": f"{len(resultats)} notes enregistrées.", "data": resultats}


@router.get("/api/notes/eleve/{eleve_id}")
def lister_par_eleve(
    eleve_id: int,
    periode: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(utilisateur_courant),
):
    notes = note_service.lister_par_eleve(db, eleve_id, periode)
    moyenne = note_service.calculer_moyenne(db, eleve_id, periode) if periode else None
    return {"success": True, "data": {"notes": notes, "moyenne": moyenne}}


@router.get("/api/bulletins/{eleve_id}/{periode}")
def obtenir_ou_generer_bulletin(
    eleve_id: int,
    periode: str,
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(utilisateur_courant),
):
    bulletin = note_service.generer_bulletin(db, eleve_id, periode)
    return {"success": True, "data": bulletin}


@router.post("/api/bulletins/{eleve_id}/{periode}/publier")
def publier(
    eleve_id: int,
    periode: str,
    donnees: PublierBulletinRequete,
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(exiger_role("professeur", "direction", "promoteur")),
):
    bulletin = note_service.publier_bulletin(db, eleve_id, periode, donnees.pdf_url)
    return {"success": True, "message": "Bulletin publié.", "data": bulletin}
