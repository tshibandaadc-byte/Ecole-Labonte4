# =========================================
# app/services/note_service.py
# =========================================
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException

from app.models.models import Note, Bulletin, Professeur
from app.schemas.autres_schemas import SaisirNoteRequete


def saisir_note(db: Session, donnees: SaisirNoteRequete, professeur_id: int | None) -> Note:
    note = Note(
        eleve_id=donnees.eleve_id,
        matiere_id=donnees.matiere_id,
        professeur_id=professeur_id,
        type_eval=donnees.type_eval,
        note=donnees.note,
        coefficient=donnees.coefficient,
        periode=donnees.periode,
        date_eval=donnees.date_eval,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def saisir_notes_groupees(db: Session, notes: list[SaisirNoteRequete], professeur_id: int | None) -> list[Note]:
    try:
        objets = []
        for n in notes:
            note = Note(
                eleve_id=n.eleve_id, matiere_id=n.matiere_id, professeur_id=professeur_id,
                type_eval=n.type_eval, note=n.note, coefficient=n.coefficient,
                periode=n.periode, date_eval=n.date_eval,
            )
            db.add(note)
            objets.append(note)
        db.commit()
        for o in objets:
            db.refresh(o)
        return objets
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erreur lors de la saisie groupée : {str(e)}")


def lister_par_eleve(db: Session, eleve_id: int, periode: str | None = None):
    requete = db.query(Note).filter(Note.eleve_id == eleve_id)
    if periode:
        requete = requete.filter(Note.periode == periode)
    return requete.all()


def calculer_moyenne(db: Session, eleve_id: int, periode: str) -> float | None:
    resultat = db.execute(
        text(
            """
            SELECT ROUND(SUM(note * coefficient) / NULLIF(SUM(coefficient), 0), 2) AS moyenne
            FROM notes WHERE eleve_id = :eleve_id AND periode = :periode
            """
        ),
        {"eleve_id": eleve_id, "periode": periode},
    )
    row = resultat.fetchone()
    return float(row.moyenne) if row and row.moyenne is not None else None


def calculer_rang(db: Session, eleve_id: int, periode: str) -> dict:
    resultat = db.execute(
        text(
            """
            WITH moyennes_classe AS (
              SELECT e.id AS eleve_id,
                     ROUND(SUM(n.note * n.coefficient) / NULLIF(SUM(n.coefficient), 0), 2) AS moyenne
              FROM eleves e
              JOIN notes n ON n.eleve_id = e.id AND n.periode = :periode
              WHERE e.classe_id = (SELECT classe_id FROM eleves WHERE id = :eleve_id)
              GROUP BY e.id
            ),
            classement AS (
              SELECT eleve_id, moyenne, RANK() OVER (ORDER BY moyenne DESC) AS rang
              FROM moyennes_classe
            )
            SELECT rang, (SELECT COUNT(*) FROM moyennes_classe) AS total_classe
            FROM classement WHERE eleve_id = :eleve_id
            """
        ),
        {"eleve_id": eleve_id, "periode": periode},
    )
    row = resultat.fetchone()
    return {"rang": row.rang if row else None, "total_classe": row.total_classe if row else 0}


def generer_bulletin(db: Session, eleve_id: int, periode: str) -> Bulletin:
    moyenne = calculer_moyenne(db, eleve_id, periode)
    infos_rang = calculer_rang(db, eleve_id, periode)

    bulletin = db.query(Bulletin).filter(
        Bulletin.eleve_id == eleve_id, Bulletin.periode == periode
    ).first()

    if bulletin:
        bulletin.moyenne = moyenne
        bulletin.rang = infos_rang["rang"]
    else:
        bulletin = Bulletin(
            eleve_id=eleve_id, periode=periode, moyenne=moyenne,
            rang=infos_rang["rang"], statut="brouillon",
        )
        db.add(bulletin)

    db.commit()
    db.refresh(bulletin)
    return bulletin


def publier_bulletin(db: Session, eleve_id: int, periode: str, pdf_url: str | None) -> Bulletin:
    bulletin = generer_bulletin(db, eleve_id, periode)  # recalcule avant publication
    bulletin.statut = "publie"
    bulletin.pdf_url = pdf_url
    from sqlalchemy.sql import func
    bulletin.date_publication = func.now()
    db.commit()
    db.refresh(bulletin)
    return bulletin


def professeur_id_de_utilisateur(db: Session, utilisateur_id: int) -> int | None:
    """Retrouve professeurs.id à partir du compte connecté."""
    prof = db.query(Professeur).filter(Professeur.utilisateur_id == utilisateur_id).first()
    return prof.id if prof else None
