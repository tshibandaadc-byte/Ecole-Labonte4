# ÉCOLE SHEMEC — application Flask PWA

Cette version Flask/PWA est intégrée au dépôt `Ecole-Labonte4` dans le compte GitHub `tshibandaadc-byte`. Les anciens prototypes et backends restent conservés.

## Fonctionnalités
- Connexion par rôle : administration, enseignant, parent, élève.
- Tableau de bord administratif : effectifs, enseignants, recettes et paiements.
- Gestion des élèves : photo obligatoire à l'inscription, matricule automatique AAAA-001, recherche, fiche, modification et suppression.
- Notes sur 20, suivi des paiements en francs congolais, messagerie interne, emploi du temps et registre des présences/absences.
- Taux de réussite calculé à partir des moyennes enregistrées avec un seuil provisoire de 10/20 (modifiable par la variable `PASS_MARK`).
- Création des comptes utilisateurs par l'administrateur et association facultative au dossier d'un élève.
- Interface responsive et installation PWA.

## Lancer sous Windows / VS Code
1. Installer Python 3.11+ depuis https://www.python.org/downloads/ (cocher Add Python to PATH).
2. Ouvrir le dossier du dépôt dans VS Code puis ouvrir Terminal.
3. Exécuter :

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py app.py
```

Ouvrir http://127.0.0.1:5000. Connexion locale initiale : `admin@shemec.cd` / `Shemec2026!`. Changer ce mot de passe immédiatement.

Si PowerShell bloque l'activation : `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, puis réactiver l'environnement.

## Déployer sur Render
1. Sur Render, choisir New > Blueprint et sélectionner ce dépôt.
2. Dans les paramètres du service, définir `ADMIN_PASSWORD` avec un mot de passe long et unique.
3. Le blueprint installe les dépendances, lance Gunicorn et crée une base PostgreSQL.
4. Une fois déployée, ouvrir l'URL HTTPS Render et se connecter avec `admin@shemec.cd` et le mot de passe défini.

## Installer comme application
- Android : ouvrir l'URL HTTPS dans Chrome, menu ⋮, Installer l'application.
- iPhone : ouvrir dans Safari, Partager, Sur l'écran d'accueil.
- PC : utiliser l'icône Installer de Chrome ou Edge.

## Points à finaliser avant usage réel
Cette branche est une première version fonctionnelle à valider. Avant de saisir des données personnelles réelles, ajouter une protection CSRF complète, des journaux d'audit, une politique de sauvegarde, un stockage persistant externe pour les photos, des procédures de récupération de mot de passe et une validation juridique de la gestion des données scolaires. Les rôles et restrictions d'accès sont à tester avec des comptes de chaque catégorie. Le taux de réussite utilise actuellement un seuil provisoire de 10/20 et toutes les notes enregistrées. L'école doit confirmer le seuil officiel et la période de calcul avant utilisation administrative.
