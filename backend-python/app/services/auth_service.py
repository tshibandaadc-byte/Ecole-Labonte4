# =========================================
# app/services/auth_service.py
# =========================================
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException

from app.models.models import Utilisateur, Eleve
from app.core.security import verifier_mot_de_passe, creer_token


def connecter(db: Session, identifiant: str, mot_de_passe: str) -> dict:
    """Authentifie par téléphone, email ou matricule d'élève."""
    utilisateur = (
        db.query(Utilisateur)
        .filter(or_(Utilisateur.telephone == identifiant, Utilisateur.email == identifiant))
        .first()
    )

    # Si pas trouvé directement, essayer via le matricule (élève)
    if not utilisateur:
        eleve = db.query(Eleve).filter(Eleve.matricule == identifiant).first()
        if eleve:
            utilisateur = db.query(Utilisateur).filter(Utilisateur.id == eleve.utilisateur_id).first()

    if not utilisateur or not verifier_mot_de_passe(mot_de_passe, utilisateur.mot_de_passe):
        raise HTTPException(status_code=401, detail="Identifiants incorrects.")

    if not utilisateur.actif:
        raise HTTPException(status_code=403, detail="Ce compte a été désactivé.")

    payload = {"id": utilisateur.id, "role": utilisateur.role, "nom": utilisateur.nom, "prenom": utilisateur.prenom}
    token = creer_token(payload)

    return {
        "access_token": token,
        "token_type": "bearer",
        "utilisateur": payload,
    }
