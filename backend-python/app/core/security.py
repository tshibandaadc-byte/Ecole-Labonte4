# =========================================
# app/core/security.py — Mots de passe et JWT
# =========================================
from datetime import datetime, timedelta

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    return pwd_context.hash(mot_de_passe)


def verifier_mot_de_passe(mot_de_passe: str, hash_stocke: str) -> bool:
    return pwd_context.verify(mot_de_passe, hash_stocke)


def creer_token(donnees: dict) -> str:
    a_encoder = donnees.copy()
    expiration = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRES_MINUTES)
    a_encoder.update({"exp": expiration})
    return jwt.encode(a_encoder, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decoder_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
