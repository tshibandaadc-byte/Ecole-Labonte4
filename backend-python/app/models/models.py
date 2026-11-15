# =========================================
# app/models/models.py — Modèles SQLAlchemy (21 tables du plan)
# =========================================
from sqlalchemy import (
    Column, Integer, String, Boolean, Text, DateTime, Date, Time,
    DECIMAL, ForeignKey, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Utilisateur(Base):
    __tablename__ = "utilisateurs"

    id = Column(Integer, primary_key=True)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100), nullable=False)
    telephone = Column(String(20), unique=True)
    email = Column(String(150), unique=True)
    mot_de_passe = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False)
    photo_url = Column(String(255))
    actif = Column(Boolean, default=True)
    date_creation = Column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "role IN ('eleve','parent','professeur','assistant','direction','promoteur')",
            name="chk_role_valide",
        ),
    )


class Promotion(Base):
    __tablename__ = "promotions"

    id = Column(Integer, primary_key=True)
    annee = Column(Integer, nullable=False, unique=True)
    libelle = Column(String(50))


class Classe(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True)
    nom = Column(String(50), nullable=False)
    niveau = Column(Integer, nullable=False)
    promotion_id = Column(Integer, ForeignKey("promotions.id", ondelete="SET NULL"))
    prof_principal_id = Column(Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"))
    annee_scolaire = Column(String(20), nullable=False)

    __table_args__ = (CheckConstraint("niveau BETWEEN 1 AND 6", name="chk_niveau"),)


class Eleve(Base):
    __tablename__ = "eleves"

    id = Column(Integer, primary_key=True)
    utilisateur_id = Column(Integer, ForeignKey("utilisateurs.id", ondelete="CASCADE"), unique=True)
    matricule = Column(String(20), unique=True, nullable=False)
    date_naissance = Column(Date, nullable=False)
    lieu_naissance = Column(String(100))
    sexe = Column(String(1))
    tuteur_id = Column(Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"))
    classe_id = Column(Integer, ForeignKey("classes.id", ondelete="SET NULL"))
    annee_entree = Column(Integer, nullable=False)
    statut = Column(String(20), default="actif")

    utilisateur = relationship("Utilisateur", foreign_keys=[utilisateur_id])

    __table_args__ = (
        CheckConstraint("sexe IN ('M','F')", name="chk_sexe"),
        CheckConstraint(
            "statut IN ('actif','inactif','transfere','diplome')", name="chk_statut_eleve"
        ),
    )


class Parent(Base):
    __tablename__ = "parents"

    id = Column(Integer, primary_key=True)
    utilisateur_id = Column(Integer, ForeignKey("utilisateurs.id", ondelete="CASCADE"), unique=True)
    profession = Column(String(100))
    adresse = Column(Text)


class Professeur(Base):
    __tablename__ = "professeurs"

    id = Column(Integer, primary_key=True)
    utilisateur_id = Column(Integer, ForeignKey("utilisateurs.id", ondelete="CASCADE"), unique=True)
    specialite = Column(String(100))
    statut = Column(String(30), default="permanent")


class Assistant(Base):
    __tablename__ = "assistants"

    id = Column(Integer, primary_key=True)
    utilisateur_id = Column(Integer, ForeignKey("utilisateurs.id", ondelete="CASCADE"), unique=True)
    fonction = Column(String(100))


class Matiere(Base):
    __tablename__ = "matieres"

    id = Column(Integer, primary_key=True)
    nom = Column(String(100), nullable=False)
    coefficient = Column(Integer, default=1)
    classe_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"))


class Affectation(Base):
    __tablename__ = "affectations"

    id = Column(Integer, primary_key=True)
    professeur_id = Column(Integer, ForeignKey("professeurs.id", ondelete="CASCADE"))
    matiere_id = Column(Integer, ForeignKey("matieres.id", ondelete="CASCADE"))
    classe_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"))

    __table_args__ = (
        UniqueConstraint("professeur_id", "matiere_id", "classe_id", name="uq_affectation"),
    )


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True)
    eleve_id = Column(Integer, ForeignKey("eleves.id", ondelete="CASCADE"))
    matiere_id = Column(Integer, ForeignKey("matieres.id", ondelete="CASCADE"))
    professeur_id = Column(Integer, ForeignKey("professeurs.id", ondelete="SET NULL"))
    type_eval = Column(String(50))
    note = Column(DECIMAL(4, 2))
    coefficient = Column(Integer, default=1)
    periode = Column(String(20), nullable=False)
    date_eval = Column(Date)
    date_saisie = Column(DateTime, server_default=func.now())

    __table_args__ = (CheckConstraint("note >= 0 AND note <= 20", name="chk_note_range"),)


class Bulletin(Base):
    __tablename__ = "bulletins"

    id = Column(Integer, primary_key=True)
    eleve_id = Column(Integer, ForeignKey("eleves.id", ondelete="CASCADE"))
    periode = Column(String(20), nullable=False)
    moyenne = Column(DECIMAL(4, 2))
    rang = Column(Integer)
    statut = Column(String(20), default="brouillon")
    pdf_url = Column(String(255))
    date_publication = Column(DateTime)

    __table_args__ = (
        UniqueConstraint("eleve_id", "periode", name="uq_bulletin_periode"),
        CheckConstraint("statut IN ('brouillon','publie')", name="chk_statut_bulletin"),
    )


class Frais(Base):
    __tablename__ = "frais"

    id = Column(Integer, primary_key=True)
    classe_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"))
    libelle = Column(String(100), nullable=False)
    montant = Column(DECIMAL(12, 2), nullable=False)
    echeance = Column(Date)
    annee_scolaire = Column(String(20), nullable=False)


class Paiement(Base):
    __tablename__ = "paiements"

    id = Column(Integer, primary_key=True)
    eleve_id = Column(Integer, ForeignKey("eleves.id", ondelete="CASCADE"))
    frais_id = Column(Integer, ForeignKey("frais.id", ondelete="CASCADE"))
    montant_paye = Column(DECIMAL(12, 2), nullable=False)
    date_paiement = Column(DateTime, server_default=func.now())
    mode = Column(String(30))
    reference = Column(String(100))
    recu_num = Column(String(50), unique=True, nullable=False)
    encaisse_par = Column(Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"))

    __table_args__ = (
        CheckConstraint(
            "mode IN ('especes','mobile_money','carte','virement')", name="chk_mode_paiement"
        ),
    )


class Presence(Base):
    __tablename__ = "presences"

    id = Column(Integer, primary_key=True)
    eleve_id = Column(Integer, ForeignKey("eleves.id", ondelete="CASCADE"))
    date_jour = Column(Date, nullable=False)
    statut = Column(String(20))
    motif = Column(Text)
    saisi_par = Column(Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"))

    __table_args__ = (
        UniqueConstraint("eleve_id", "date_jour", name="uq_presence_jour"),
        CheckConstraint(
            "statut IN ('present','absent','retard','excuse')", name="chk_statut_presence"
        ),
    )


class Communique(Base):
    __tablename__ = "communiques"

    id = Column(Integer, primary_key=True)
    auteur_id = Column(Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"))
    titre = Column(String(200), nullable=False)
    contenu = Column(Text, nullable=False)
    categorie = Column(String(30))
    cible = Column(String(50), default="tous")
    date_pub = Column(DateTime, server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    destinataire_id = Column(Integer, ForeignKey("utilisateurs.id", ondelete="CASCADE"))
    titre = Column(String(200))
    message = Column(Text)
    lu = Column(Boolean, default=False)
    date_envoi = Column(DateTime, server_default=func.now())


class EmploiDuTemps(Base):
    __tablename__ = "emploi_du_temps"

    id = Column(Integer, primary_key=True)
    classe_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"))
    jour = Column(String(20), nullable=False)
    heure_debut = Column(Time, nullable=False)
    heure_fin = Column(Time, nullable=False)
    matiere_id = Column(Integer, ForeignKey("matieres.id", ondelete="CASCADE"))
    professeur_id = Column(Integer, ForeignKey("professeurs.id", ondelete="SET NULL"))
    salle = Column(String(50))


class Evenement(Base):
    __tablename__ = "evenements"

    id = Column(Integer, primary_key=True)
    titre = Column(String(200), nullable=False)
    description = Column(Text)
    date_debut = Column(DateTime, nullable=False)
    date_fin = Column(DateTime)
    type = Column(String(50))
    cible = Column(String(50), default="tous")


class Devoir(Base):
    __tablename__ = "devoirs"

    id = Column(Integer, primary_key=True)
    matiere_id = Column(Integer, ForeignKey("matieres.id", ondelete="CASCADE"))
    classe_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"))
    professeur_id = Column(Integer, ForeignKey("professeurs.id", ondelete="SET NULL"))
    titre = Column(String(200), nullable=False)
    description = Column(Text)
    date_limite = Column(Date)
    fichier_url = Column(String(255))
    date_creation = Column(DateTime, server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    user1_id = Column(Integer, ForeignKey("utilisateurs.id", ondelete="CASCADE"))
    user2_id = Column(Integer, ForeignKey("utilisateurs.id", ondelete="CASCADE"))
    date_creation = Column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("user1_id", "user2_id", name="uq_conversation"),)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"))
    expediteur_id = Column(Integer, ForeignKey("utilisateurs.id", ondelete="CASCADE"))
    contenu = Column(Text, nullable=False)
    lu = Column(Boolean, default=False)
    date_envoi = Column(DateTime, server_default=func.now())


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    eleve_id = Column(Integer, ForeignKey("eleves.id", ondelete="CASCADE"))
    type_doc = Column(String(50))
    fichier_url = Column(String(255), nullable=False)
    date_ajout = Column(DateTime, server_default=func.now())
