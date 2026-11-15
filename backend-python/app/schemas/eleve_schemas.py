# =========================================
# app/schemas/eleve_schemas.py
# =========================================
from datetime import date
from typing import Optional
from pydantic import BaseModel, field_validator


class InscriptionEleveRequete(BaseModel):
    nom: str
    prenom: str
    date_naissance: date
    lieu_naissance: Optional[str] = None
    sexe: str
    classe_id: int
    mot_de_passe: str
    telephone: Optional[str] = None
    email: Optional[str] = None
    tuteur_nom: Optional[str] = None
    tuteur_telephone: Optional[str] = None

    @field_validator("sexe")
    @classmethod
    def valider_sexe(cls, v):
        if v not in ("M", "F"):
            raise ValueError("Le sexe doit être 'M' ou 'F'.")
        return v

    @field_validator("mot_de_passe")
    @classmethod
    def valider_mdp(cls, v):
        if len(v) < 6:
            raise ValueError("Le mot de passe doit contenir au moins 6 caractères.")
        return v

    @field_validator("date_naissance")
    @classmethod
    def valider_age(cls, v):
        aujourdhui = date.today()
        age = aujourdhui.year - v.year - ((aujourdhui.month, aujourdhui.day) < (v.month, v.day))
        if age < 2 or age > 25:
            raise ValueError("La date de naissance semble invalide pour une inscription scolaire.")
        return v


class EleveReponse(BaseModel):
    id: int
    nom: str
    prenom: str
    matricule: str
    classe_id: Optional[int]
    date_naissance: date

    class Config:
        from_attributes = True
