# =========================================
# app/services/eleve_service.py
# =========================================
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from fastapi import HTTPException

from app.models.models import Utilisateur, Eleve, Parent
from app.core.security import hacher_mot_de_passe
from app.schemas.eleve_schemas import InscriptionEleveRequete


def generer_matricule(db: Session, annee: int) -> str:
    """
    Génère le prochain matricule pour une année donnée : <annee>-NNNN.
    Utilise une table de compteurs (compteurs_matricule) mise à jour via
    INSERT ... ON CONFLICT ... RETURNING, qui est atomique au niveau
    PostgreSQL : deux inscriptions simultanées pour la même année ne
    peuvent jamais recevoir le même numéro (contrairement à un COUNT(*),
    qui peut être lu deux fois avec la même valeur avant qu'aucune des
    deux transactions n'ait inséré sa ligne).
    """
    resultat = db.execute(
        text(
            """
            INSERT INTO compteurs_matricule (annee, dernier)
            VALUES (:annee, 1)
            ON CONFLICT (annee) DO UPDATE SET dernier = compteurs_matricule.dernier + 1
            RETURNING dernier
            """
        ),
        {"annee": annee},
    )
    sequence = resultat.scalar()
    return f"{annee}-{str(sequence).zfill(4)}"


def creer_inscription_eleve(db: Session, donnees: InscriptionEleveRequete) -> dict:
    """
    Crée le compte utilisateur (role='eleve') + la fiche eleves, et gère le
    parent/tuteur (création si téléphone inconnu, rattachement sinon).
    Toute l'opération est transactionnelle : soit tout réussit, soit rien n'est
    enregistré (rollback automatique en cas d'erreur).
    """
    try:
        annee_entree = datetime.now().year

        # 1. Résoudre le tuteur
        tuteur_id = None
        if donnees.tuteur_telephone:
            tuteur_existant = (
                db.query(Utilisateur)
                .filter(Utilisateur.telephone == donnees.tuteur_telephone)
                .first()
            )
            if tuteur_existant:
                tuteur_id = tuteur_existant.id
            else:
                nouveau_tuteur = Utilisateur(
                    nom=donnees.tuteur_nom or "Tuteur",
                    prenom=donnees.prenom,
                    telephone=donnees.tuteur_telephone,
                    mot_de_passe=hacher_mot_de_passe(donnees.mot_de_passe),
                    role="parent",
                )
                db.add(nouveau_tuteur)
                db.flush()  # obtient l'id sans committer
                tuteur_id = nouveau_tuteur.id
                db.add(Parent(utilisateur_id=tuteur_id))

        # 2. Créer le compte utilisateur de l'élève
        nouvel_utilisateur = Utilisateur(
            nom=donnees.nom,
            prenom=donnees.prenom,
            telephone=donnees.telephone,
            email=donnees.email,
            mot_de_passe=hacher_mot_de_passe(donnees.mot_de_passe),
            role="eleve",
        )
        db.add(nouvel_utilisateur)
        db.flush()

        # 3. Générer le matricule (verrouillage transactionnel)
        matricule = generer_matricule(db, annee_entree)

        # 4. Créer la fiche élève
        nouvel_eleve = Eleve(
            utilisateur_id=nouvel_utilisateur.id,
            matricule=matricule,
            date_naissance=donnees.date_naissance,
            lieu_naissance=donnees.lieu_naissance,
            sexe=donnees.sexe,
            tuteur_id=tuteur_id,
            classe_id=donnees.classe_id,
            annee_entree=annee_entree,
            statut="actif",
        )
        db.add(nouvel_eleve)

        db.commit()
        db.refresh(nouvel_eleve)
        db.refresh(nouvel_utilisateur)

        return {
            "eleve": nouvel_eleve,
            "utilisateur": nouvel_utilisateur,
            "tuteur_id": tuteur_id,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'inscription : {str(e)}")


def trouver_par_matricule(db: Session, matricule: str) -> Eleve:
    eleve = db.query(Eleve).filter(Eleve.matricule == matricule).first()
    if not eleve:
        raise HTTPException(status_code=404, detail="Aucun élève trouvé avec ce matricule.")
    return eleve


def trouver_par_id(db: Session, eleve_id: int) -> Eleve:
    eleve = db.query(Eleve).filter(Eleve.id == eleve_id).first()
    if not eleve:
        raise HTTPException(status_code=404, detail="Élève non trouvé.")
    return eleve


def lister_par_classe(db: Session, classe_id: int):
    return db.query(Eleve).filter(Eleve.classe_id == classe_id).all()


def trouver_eleve_de_utilisateur(db: Session, utilisateur_id: int) -> Eleve:
    """Retourne la fiche élève liée au compte connecté (role='eleve')."""
    eleve = db.query(Eleve).filter(Eleve.utilisateur_id == utilisateur_id).first()
    if not eleve:
        raise HTTPException(status_code=404, detail="Aucune fiche élève liée à ce compte.")
    return eleve


def trouver_enfants_du_tuteur(db: Session, tuteur_id: int):
    """Retourne les élèves dont le compte connecté (role='parent') est le tuteur."""
    return db.query(Eleve).filter(Eleve.tuteur_id == tuteur_id).all()
