# =========================================
# app/routers/communication_router.py
# =========================================
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import utilisateur_courant, exiger_role
from app.schemas.autres_schemas import CommuniqueRequete, MessageRequete
from app.services import communication_service

router = APIRouter(tags=["Communiqués & Messagerie"])


# --- Communiqués ---
@router.post("/api/communiques", status_code=201)
def publier(
    donnees: CommuniqueRequete,
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(exiger_role("assistant", "direction", "promoteur")),
):
    communique = communication_service.publier_communique(db, donnees, auteur_id=utilisateur["id"])
    return {"success": True, "message": "Communiqué publié.", "data": communique}


@router.get("/api/communiques")
def lister(
    cible: Optional[str] = Query(None),
    limite: int = Query(50),
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(utilisateur_courant),
):
    communiques = communication_service.lister_communiques(db, cible, limite)
    return {"success": True, "data": communiques}


# --- Messagerie ---
@router.post("/api/messages", status_code=201)
def envoyer(
    donnees: MessageRequete,
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(utilisateur_courant),
):
    message = communication_service.envoyer_message(
        db, expediteur_id=utilisateur["id"], destinataire_id=donnees.destinataire_id,
        contenu=donnees.contenu,
    )
    return {"success": True, "data": message}


@router.get("/api/messages")
def lister_conversations(
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(utilisateur_courant),
):
    conversations = communication_service.lister_conversations(db, utilisateur["id"])
    return {"success": True, "data": conversations}


@router.get("/api/messages/{conversation_id}")
def lister_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(utilisateur_courant),
):
    messages = communication_service.lister_messages(db, conversation_id, utilisateur["id"])
    return {"success": True, "data": messages}
