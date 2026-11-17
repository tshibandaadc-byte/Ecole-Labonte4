# ÉCOLE SHEMEC — portail scolaire Flask / PWA

Application scolaire pour École Shemec à Lubumbashi, République démocratique du Congo. Le dépôt historique `Ecole-Labonte4` est conservé; le nom de produit affiché dans l'application est désormais **École Shemec**.

## Organisation scolaire congolaise

Les nouvelles inscriptions dans le portail Flask utilisent maintenant trois cycles :
- **Maternelle** : 1re, 2e et 3e année maternelle.
- **Primaire** : 1re à 6e année primaire.
- **Secondaire** : 1re à 6e secondaire, avec une option/section sélectionnable.

Le référentiel est centralisé dans `school_structure.py`. Les validations empêchent d'affecter une classe à un cycle incorrect. Les champs historiques `faculte` et `filiere` restent en base pour compatibilité; deux colonnes facultatives `niveau_scolaire` et `option_scolaire` sont ajoutées automatiquement au démarrage, sans effacer les anciens dossiers. Les nouveaux matricules sont générés par l'application à partir de l'année, du code du cycle et du code de classe.

L'écran d'administration **Structure scolaire** présente les classes et les options disponibles. Les options affichées constituent un référentiel initial à faire confirmer par la Direction avant la rentrée.

## Technologies
- Python 3.11+ et Flask
- Flask-SQLAlchemy, Flask-Login
- SQLite en développement; PostgreSQL conseillé en production
- HTML/Jinja, CSS, JavaScript et PWA installable
- PDF avec ReportLab

## Fonctions déjà présentes dans le portail Flask
- Connexion par rôle : administration, enseignant, parent et élève.
- Site public, demande d'admission et espaces de connexion.
- Dossiers élèves, matricules attribués par la Direction, comptes élèves, photos, QR codes et historique académique.
- Notes sur 20, bulletins PDF, affectations enseignants, emploi du temps et présences.
- Frais scolaires et paiements suivis séparément en CDF et USD; reçus PDF.
- Messagerie interne, assistant de recherche scolaire, comptes utilisateurs.
- Personnel, contrats, avances, paies et bulletins PDF.
- Années scolaires et trimestres/périodes.
- Bibliothèque : catalogue, emprunts, retours et pénalités configurables.
- Transport : bus, chauffeurs, itinéraires et affectation des élèves.
- Cantine : menus, commandes et stocks avec alertes de seuil.
- Comptabilité : recettes et dépenses distinctes par devise.
- Journal des opérations (audit) et interface responsive/PWA.

## Installation locale sous Windows / VS Code
1. Installer Python 3.11 ou plus récent depuis https://www.python.org/downloads/ en activant l'option **Add Python to PATH**.
2. Ouvrir le dossier du dépôt dans VS Code puis le terminal PowerShell.
3. Exécuter :

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
$env:SECRET_KEY = "remplacer-par-une-cle-longue-et-aleatoire"
$env:ADMIN_PASSWORD = "choisir-un-mot-de-passe-long-et-unique"
py app.py
```

Ouvrir http://127.0.0.1:5000. Au premier lancement, le compte administrateur est créé avec l'adresse `admin@shemec.cd` et la valeur définie dans `ADMIN_PASSWORD`. Ne pas réutiliser un mot de passe de démonstration.

Si PowerShell bloque l'activation :
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

## Déploiement Render
1. Créer un Blueprint Render depuis ce dépôt.
2. Définir `ADMIN_PASSWORD` comme variable secrète avec un mot de passe unique.
3. Le blueprint installe les dépendances, lance Gunicorn et provisionne PostgreSQL.
4. Vérifier les sauvegardes PostgreSQL et le stockage persistant des photos avant de saisir des données réelles.

## Installer comme application
- Android : ouvrir l'URL HTTPS dans Chrome, menu ⋮, Installer l'application.
- iPhone : ouvrir l'URL HTTPS dans Safari, Partager, Sur l'écran d'accueil.
- PC : utiliser l'icône Installer de Chrome ou Edge.

## À connecter ou renforcer avant une mise en production réelle
- Passerelle de paiement Mobile Money (M-Pesa, Airtel Money, Orange Money) avec vérification serveur des transactions.
- Fournisseur SMS et API WhatsApp Business.
- Protection CSRF sur tous les formulaires, limitation des tentatives de connexion et récupération sécurisée des mots de passe.
- Sauvegardes automatiques testées et restauration, stockage persistant sécurisé des photos.
- Compléter les écritures d'audit sur toutes les opérations sensibles, les exports financiers et les rapports PDF/Excel.
- Tester chaque rôle et les autorisations avec des comptes distincts; faire valider les règles scolaires, les frais et les périodes par la Direction.

Les modules ajoutés sont une base de gestion opérationnelle. Les paiements électroniques, les notifications externes et les sauvegardes de production ne sont pas activés simplement par la présence de leurs écrans ou modèles : ils nécessitent des prestataires et une configuration réels.
