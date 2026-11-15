# =========================================
# app/services/paiement_service.py
# =========================================
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException

from app.models.models import Paiement
from app.schemas.autres_schemas import PaiementRequete


def lister_frais_par_eleve(db: Session, eleve_id: int):
    resultat = db.execute(
        text(
            """
            SELECT f.id, f.libelle, f.montant, f.echeance, f.annee_scolaire,
                   COALESCE(SUM(p.montant_paye), 0) AS total_paye,
                   f.montant - COALESCE(SUM(p.montant_paye), 0) AS reste_a_payer
            FROM frais f
            JOIN eleves e ON e.classe_id = f.classe_id
            LEFT JOIN paiements p ON p.frais_id = f.id AND p.eleve_id = e.id
            WHERE e.id = :eleve_id
            GROUP BY f.id
            ORDER BY f.echeance
            """
        ),
        {"eleve_id": eleve_id},
    )
    return [dict(row._mapping) for row in resultat]


def generer_numero_recu(db: Session) -> str:
    """
    Génère un numéro de reçu unique : REC-<année>-<n° de séquence sur 6 chiffres>.
    Utilise une séquence PostgreSQL (nextval), dont l'incrémentation est
    atomique : même si deux paiements sont enregistrés au même instant,
    chacun reçoit un numéro différent — contrairement à un COUNT(*) qui
    peut lire la même valeur avant que l'autre transaction n'ait inséré sa ligne.
    """
    annee = datetime.now().year
    resultat = db.execute(text("SELECT nextval('seq_recu_paiement')"))
    sequence = resultat.scalar()
    return f"REC-{annee}-{str(sequence).zfill(6)}"


def enregistrer_paiement(db: Session, donnees: PaiementRequete, encaisse_par: int) -> Paiement:
    try:
        resultat = db.execute(
            text(
                """
                SELECT f.montant, COALESCE(SUM(p.montant_paye), 0) AS deja_paye
                FROM frais f
                LEFT JOIN paiements p ON p.frais_id = f.id AND p.eleve_id = :eleve_id
                WHERE f.id = :frais_id
                GROUP BY f.montant
                """
            ),
            {"frais_id": donnees.frais_id, "eleve_id": donnees.eleve_id},
        )
        row = resultat.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Frais introuvable.")

        reste_avant = float(row.montant) - float(row.deja_paye)
        if donnees.montant_paye > reste_avant:
            raise HTTPException(
                status_code=400,
                detail=f"Le montant dépasse le solde restant ({reste_avant} FCFA).",
            )

        recu_num = generer_numero_recu(db)

        paiement = Paiement(
            eleve_id=donnees.eleve_id,
            frais_id=donnees.frais_id,
            montant_paye=donnees.montant_paye,
            mode=donnees.mode,
            reference=donnees.reference,
            recu_num=recu_num,
            encaisse_par=encaisse_par,
        )
        db.add(paiement)
        db.commit()
        db.refresh(paiement)
        return paiement

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erreur lors du paiement : {str(e)}")


def historique_paiements(db: Session, eleve_id: int):
    return db.query(Paiement).filter(Paiement.eleve_id == eleve_id).order_by(
        Paiement.date_paiement.desc()
    ).all()


def paiements_du_jour(db: Session) -> dict:
    resultat = db.execute(
        text(
            """
            SELECT COUNT(*) AS nb_paiements, COALESCE(SUM(montant_paye), 0) AS total
            FROM paiements WHERE date_paiement::date = CURRENT_DATE
            """
        )
    )
    row = resultat.fetchone()
    return {"nb_paiements": row.nb_paiements, "total": float(row.total)}


def taux_recouvrement(db: Session, annee_scolaire: str) -> dict:
    resultat = db.execute(
        text(
            """
            SELECT
              COALESCE(SUM(f.montant), 0) AS total_attendu,
              COALESCE((SELECT SUM(montant_paye) FROM paiements p
                        JOIN frais f2 ON f2.id = p.frais_id
                        WHERE f2.annee_scolaire = :annee), 0) AS total_percu
            FROM frais f WHERE f.annee_scolaire = :annee
            """
        ),
        {"annee": annee_scolaire},
    )
    row = resultat.fetchone()
    total_attendu = float(row.total_attendu)
    total_percu = float(row.total_percu)
    taux = round((total_percu / total_attendu) * 100, 2) if total_attendu > 0 else 0
    return {"total_attendu": total_attendu, "total_percu": total_percu, "taux_pourcentage": taux}
