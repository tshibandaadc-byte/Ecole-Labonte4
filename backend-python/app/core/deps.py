# =========================================
# app/core/deps.py — Dépendances d'authentification
# =========================================
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from app.core.security import decoder_token

securite = HTTPBearer()


def utilisateur_courant(identifiants: HTTPAuthorizationCredentials = Depends(securite)) -> dict:
    """Vérifie le token JWT et retourne les infos de l'utilisateur connecté."""
    try:
        payload = decoder_token(identifiants.credentials)
        return payload  # contient : id, role, nom, prenom
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalide.")


def exiger_role(*roles_autorises: str):
    """Fabrique une dépendance qui vérifie que l'utilisateur a un des rôles autorisés."""

    def verificateur(utilisateur: dict = Depends(utilisateur_courant)) -> dict:
        if utilisateur.get("role") not in roles_autorises:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé. Rôle requis : {' ou '.join(roles_autorises)}.",
            )
        return utilisateur

    return verificateur
