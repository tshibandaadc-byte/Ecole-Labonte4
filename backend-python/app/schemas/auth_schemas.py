# =========================================
# app/schemas/auth_schemas.py
# =========================================
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional


class ConnexionRequete(BaseModel):
    identifiant: str  # téléphone, email ou matricule
    mot_de_passe: str


class TokenReponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    utilisateur: dict


class InscriptionUtilisateurRequete(BaseModel):
    nom: str
    prenom: str
    telephone: Optional[str] = None
    email: Optional[EmailStr] = None
    mot_de_passe: str
    role: str

    @field_validator("mot_de_passe")
    @classmethod
    def valider_longueur_mdp(cls, v):
        if len(v) < 6:
            raise ValueError("Le mot de passe doit contenir au moins 6 caractères.")
        return v

    @field_validator("role")
    @classmethod
    def valider_role(cls, v):
        roles_valides = {"eleve", "parent", "professeur", "assistant", "direction", "promoteur"}
        if v not in roles_valides:
            raise ValueError(f"Rôle invalide. Valeurs acceptées : {roles_valides}")
        return v
