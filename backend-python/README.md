# École La Bonté — Backend Python (FastAPI)

Backend complet en Python pour l'application École La Bonté : authentification,
inscription élèves (avec matricule automatique), notes/bulletins,
paiements/frais, communiqués et messagerie.

## 1. Prérequis

- Python 3.10 ou plus récent
- PostgreSQL installé et démarré sur ta machine
  (télécharge-le ici si besoin : https://www.postgresql.org/download/)

## 2. Installation

Ouvre un terminal dans ce dossier (`backend-python`) et exécute :

```bash
# Créer un environnement virtuel (recommandé)
python -m venv venv

# L'activer
# Sur Windows :
venv\Scripts\activate
# Sur Mac/Linux :
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt
```

## 3. Configuration de la base de données

1. Crée la base de données PostgreSQL :

```bash
psql -U postgres -c "CREATE DATABASE ecole_la_bonte;"
```

2. Copie `.env.example` en `.env` et adapte les identifiants :

```bash
cp .env.example .env
```

Ouvre `.env` et remplace `DB_USER`, `DB_PASSWORD` par tes vrais identifiants
PostgreSQL si différents de `postgres` / `postgres`.

3. Crée toutes les tables :

```bash
python creer_tables.py
```

Tu peux aussi utiliser le script SQL fourni (`sql/schema.sql`, si tu l'as
copié depuis le backend Node.js) directement dans `psql` — les deux méthodes
créent la même structure.

## 4. Lancer le serveur

```bash
uvicorn main:app --reload
```

Le serveur démarre sur **http://localhost:8000**

- Documentation interactive (Swagger) : http://localhost:8000/docs
- Vérification santé : http://localhost:8000/api/health

La doc Swagger te permet de tester chaque route directement dans le
navigateur, avec formulaires générés automatiquement — pratique pour
vérifier que tout fonctionne sans écrire de code côté client.

## 5. Structure du projet

```
backend-python/
├── app/
│   ├── core/          # config, connexion DB, sécurité JWT
│   ├── models/        # modèles SQLAlchemy (21 tables)
│   ├── schemas/        # schémas Pydantic (validation entrée/sortie)
│   ├── services/       # logique métier (inscription, notes, paiements...)
│   └── routers/        # routes API (endpoints HTTP)
├── main.py             # point d'entrée
├── creer_tables.py      # script de création des tables
├── requirements.txt
└── .env.example
```

## 6. Principales routes

| Méthode | Route | Description |
|---|---|---|
| POST | /api/auth/login | Connexion (téléphone/email/matricule + mot de passe) |
| POST | /api/eleves/inscription | Inscription élève + génération matricule |
| GET | /api/eleves/{id} | Fiche élève |
| POST | /api/notes | Saisie d'une note (professeur) |
| GET | /api/notes/eleve/{id}?periode=Trimestre 1 | Notes d'un élève |
| GET | /api/bulletins/{eleve_id}/{periode} | Bulletin (généré ou existant) |
| GET | /api/frais/eleve/{id} | Frais d'un élève |
| POST | /api/paiements | Enregistrer un paiement |
| POST | /api/communiques | Publier un communiqué |
| GET | /api/communiques | Lister les communiqués |
| POST | /api/messages | Envoyer un message |
| GET | /api/messages | Lister ses conversations |

Toutes les routes sauf `/api/auth/login` et `/api/eleves/inscription`
nécessitent un header `Authorization: Bearer <token>` obtenu via le login.

## 7. Notes importantes

- Le matricule est généré automatiquement au format `AAAA-XXXX`
  (ex: 2026-0042), avec un verrou transactionnel en base de données pour
  éviter les doublons si deux inscriptions arrivent en même temps.
- Les mots de passe sont hachés avec bcrypt avant stockage.
- Ce backend n'a pas encore de gestion de fichiers (photos, PDF) ni de
  notifications push — à ajouter avec un service comme AWS S3 ou Firebase
  selon les besoins.
