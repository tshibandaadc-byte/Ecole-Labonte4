# =========================================
# app/schemas/autres_schemas.py
# =========================================
from datetime import date
from typing import Optional, List
from pydantic import BaseModel, field_validator


# --- Notes ---
class SaisirNoteRequete(BaseModel):
    eleve_id: int
    matiere_id: int
    type_eval: Optional[str] = None
    note: float
    coefficient: int = 1
    periode: str
    date_eval: Optional[date] = None

    @field_validator("note")
    @classmethod
    def valider_note(cls, v):
        if v < 0 or v > 20:
            raise ValueError("La note doit être comprise entre 0 et 20.")
        return v


class SaisirNotesGroupeesRequete(BaseModel):
    notes: List[SaisirNoteRequete]


class PublierBulletinRequete(BaseModel):
    pdf_url: Optional[str] = None


# --- Paiements ---
class PaiementRequete(BaseModel):
    eleve_id: int
    frais_id: int
    montant_paye: float
    mode: str
    reference: Optional[str] = None

    @field_validator("montant_paye")
    @classmethod
    def valider_montant(cls, v):
        if v <= 0:
            raise ValueError("Le montant payé doit être positif.")
        return v

    @field_validator("mode")
    @classmethod
    def valider_mode(cls, v):
        modes_valides = {"especes", "mobile_money", "carte", "virement"}
        if v not in modes_valides:
            raise ValueError(f"Mode de paiement invalide. Valeurs acceptées : {modes_valides}")
        return v


# --- Communiqués ---
class CommuniqueRequete(BaseModel):
    titre: str
    contenu: str
    categorie: Optional[str] = "general"
    cible: Optional[str] = "tous"


# --- Messagerie ---
class MessageRequete(BaseModel):
    destinataire_id: int
    contenu: str

    @field_validator("contenu")
    @classmethod
    def valider_contenu(cls, v):
        if not v.strip():
            raise ValueError("Le contenu du message ne peut pas être vide.")
        return v
