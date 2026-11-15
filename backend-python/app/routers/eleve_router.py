# =========================================
# app/routers/eleve_router.py
# =========================================
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import utilisateur_courant, exiger_role
from app.schemas.eleve_schemas import InscriptionEleveRequete
from app.services import eleve_service

router = APIRouter(prefix="/api/eleves", tags=["Élèves"])


@router.post("/inscription", status_code=201)
def inscrire(donnees: InscriptionEleveRequete, db: Session = Depends(get_db)):
    resultat = eleve_service.creer_inscription_eleve(db, donnees)
    return {
        "success": True,
        "message": "Inscription réussie.",
        "data": {
            "matricule": resultat["eleve"].matricule,
            "eleve": {
                "id": resultat["eleve"].id,
                "nom": resultat["utilisateur"].nom,
                "prenom": resultat["utilisateur"].prenom,
                "classe_id": resultat["eleve"].classe_id,
                "date_naissance": str(resultat["eleve"].date_naissance),
            },
        },
    }


@router.get("/moi")
def mon_profil_eleve(
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(utilisateur_courant),
):
    """Élève connecté -> sa fiche. Parent connecté -> la liste de ses enfants."""
    if utilisateur["role"] == "parent":
        enfants = eleve_service.trouver_enfants_du_tuteur(db, utilisateur["id"])
        return {"success": True, "data": enfants, "total": len(enfants)}
    eleve = eleve_service.trouver_eleve_de_utilisateur(db, utilisateur["id"])
    return {"success": True, "data": eleve}


@router.get("/matricule/{matricule}")
def obtenir_par_matricule(
    matricule: str,
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(exiger_role("assistant", "direction", "promoteur", "professeur")),
):
    eleve = eleve_service.trouver_par_matricule(db, matricule)
    return {"success": True, "data": eleve}


@router.get("/classe/{classe_id}")
def lister_par_classe(
    classe_id: int,
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(exiger_role("assistant", "direction", "promoteur", "professeur")),
):
    eleves = eleve_service.lister_par_classe(db, classe_id)
    return {"success": True, "data": eleves, "total": len(eleves)}


@router.get("/{eleve_id}")
def obtenir_par_id(
    eleve_id: int,
    db: Session = Depends(get_db),
    utilisateur: dict = Depends(utilisateur_courant),
):
    eleve = eleve_service.trouver_par_id(db, eleve_id)
    return {"success": True, "data": eleve}
