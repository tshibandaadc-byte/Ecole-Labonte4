# =========================================
# creer_tables.py — Crée toutes les tables en BDD
# Usage : python creer_tables.py
# =========================================
from app.core.database import engine, Base
from app.models import models  # noqa: F401 — importe tous les modèles pour les enregistrer

if __name__ == "__main__":
    print("Création des tables dans PostgreSQL...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables créées avec succès.")
