-- =========================================================
-- BASE DE DONNÉES : ECOLE_LA_BONTE
-- Script complet prêt à exécuter (PostgreSQL 13+)
-- =========================================================

-- Décommenter si besoin de repartir de zéro (⚠️ destructif) :
-- DROP DATABASE IF EXISTS ecole_la_bonte;
-- CREATE DATABASE ecole_la_bonte;
-- \c ecole_la_bonte

BEGIN;

-- 1. UTILISATEURS (table mère)
CREATE TABLE IF NOT EXISTS utilisateurs (
  id            SERIAL PRIMARY KEY,
  nom           VARCHAR(100) NOT NULL,
  prenom        VARCHAR(100) NOT NULL,
  telephone     VARCHAR(20) UNIQUE,
  email         VARCHAR(150) UNIQUE,
  mot_de_passe  VARCHAR(255) NOT NULL,
  role          VARCHAR(30) NOT NULL CHECK (role IN
                ('eleve','parent','professeur','assistant','direction','promoteur')),
  photo_url     VARCHAR(255),
  actif         BOOLEAN DEFAULT TRUE,
  date_creation TIMESTAMP DEFAULT NOW(),
  CONSTRAINT chk_contact CHECK (telephone IS NOT NULL OR email IS NOT NULL)
);

-- 2. PROMOTIONS
CREATE TABLE IF NOT EXISTS promotions (
  id      SERIAL PRIMARY KEY,
  annee   INT NOT NULL UNIQUE,
  libelle VARCHAR(50)
);

-- 3. CLASSES
CREATE TABLE IF NOT EXISTS classes (
  id                    SERIAL PRIMARY KEY,
  nom                   VARCHAR(50) NOT NULL,
  niveau                INT NOT NULL CHECK (niveau BETWEEN 1 AND 6),
  promotion_id          INT REFERENCES promotions(id) ON DELETE SET NULL,
  prof_principal_id     INT REFERENCES utilisateurs(id) ON DELETE SET NULL,
  annee_scolaire        VARCHAR(20) NOT NULL
);

-- 4. ÉLÈVES
CREATE TABLE IF NOT EXISTS eleves (
  id                SERIAL PRIMARY KEY,
  utilisateur_id    INT UNIQUE REFERENCES utilisateurs(id) ON DELETE CASCADE,
  matricule         VARCHAR(20) UNIQUE NOT NULL,
  date_naissance    DATE NOT NULL,
  lieu_naissance    VARCHAR(100),
  sexe              CHAR(1) CHECK (sexe IN ('M','F')),
  tuteur_id         INT REFERENCES utilisateurs(id) ON DELETE SET NULL,
  classe_id         INT REFERENCES classes(id) ON DELETE SET NULL,
  annee_entree      INT NOT NULL,
  statut            VARCHAR(20) DEFAULT 'actif'
                    CHECK (statut IN ('actif','inactif','transfere','diplome'))
);

-- 5. PARENTS
CREATE TABLE IF NOT EXISTS parents (
  id              SERIAL PRIMARY KEY,
  utilisateur_id  INT UNIQUE REFERENCES utilisateurs(id) ON DELETE CASCADE,
  profession      VARCHAR(100),
  adresse         TEXT
);

-- 6. PROFESSEURS
CREATE TABLE IF NOT EXISTS professeurs (
  id              SERIAL PRIMARY KEY,
  utilisateur_id  INT UNIQUE REFERENCES utilisateurs(id) ON DELETE CASCADE,
  specialite      VARCHAR(100),
  statut          VARCHAR(30) DEFAULT 'permanent'
);

-- 7. ASSISTANTS
CREATE TABLE IF NOT EXISTS assistants (
  id              SERIAL PRIMARY KEY,
  utilisateur_id  INT UNIQUE REFERENCES utilisateurs(id) ON DELETE CASCADE,
  fonction        VARCHAR(100)
);

-- 8. MATIÈRES
CREATE TABLE IF NOT EXISTS matieres (
  id          SERIAL PRIMARY KEY,
  nom         VARCHAR(100) NOT NULL,
  coefficient INT DEFAULT 1 CHECK (coefficient > 0),
  classe_id   INT REFERENCES classes(id) ON DELETE CASCADE
);

-- 9. AFFECTATIONS
CREATE TABLE IF NOT EXISTS affectations (
  id              SERIAL PRIMARY KEY,
  professeur_id   INT REFERENCES professeurs(id) ON DELETE CASCADE,
  matiere_id      INT REFERENCES matieres(id) ON DELETE CASCADE,
  classe_id       INT REFERENCES classes(id) ON DELETE CASCADE,
  UNIQUE (professeur_id, matiere_id, classe_id)
);

-- 10. NOTES
CREATE TABLE IF NOT EXISTS notes (
  id              SERIAL PRIMARY KEY,
  eleve_id        INT REFERENCES eleves(id) ON DELETE CASCADE,
  matiere_id      INT REFERENCES matieres(id) ON DELETE CASCADE,
  professeur_id   INT REFERENCES professeurs(id) ON DELETE SET NULL,
  type_eval       VARCHAR(50),
  note            DECIMAL(4,2) CHECK (note >= 0 AND note <= 20),
  coefficient     INT DEFAULT 1,
  periode         VARCHAR(20) NOT NULL,
  date_eval       DATE,
  date_saisie     TIMESTAMP DEFAULT NOW()
);

-- 11. BULLETINS
CREATE TABLE IF NOT EXISTS bulletins (
  id                SERIAL PRIMARY KEY,
  eleve_id          INT REFERENCES eleves(id) ON DELETE CASCADE,
  periode           VARCHAR(20) NOT NULL,
  moyenne           DECIMAL(4,2),
  rang              INT,
  statut            VARCHAR(20) DEFAULT 'brouillon' CHECK (statut IN ('brouillon','publie')),
  pdf_url           VARCHAR(255),
  date_publication  TIMESTAMP,
  UNIQUE (eleve_id, periode)
);

-- 12. FRAIS
CREATE TABLE IF NOT EXISTS frais (
  id              SERIAL PRIMARY KEY,
  classe_id       INT REFERENCES classes(id) ON DELETE CASCADE,
  libelle         VARCHAR(100) NOT NULL,
  montant         DECIMAL(12,2) NOT NULL CHECK (montant >= 0),
  echeance        DATE,
  annee_scolaire  VARCHAR(20) NOT NULL
);

-- 13. PAIEMENTS
-- Compteur de matricules par année d'entrée. Chaque ligne est mise à jour
-- de façon atomique (INSERT ... ON CONFLICT ... RETURNING), ce qui évite
-- le problème du COUNT(*) : deux inscriptions simultanées ne peuvent
-- jamais recevoir le même matricule.
CREATE TABLE IF NOT EXISTS compteurs_matricule (
  annee   INT PRIMARY KEY,
  dernier INT NOT NULL DEFAULT 0
);

-- Séquence dédiée aux numéros de reçu (REC-AAAA-NNNNNN).
-- nextval() est atomique au niveau PostgreSQL : deux paiements simultanés
-- reçoivent toujours deux valeurs différentes, sans risque de doublon.
CREATE SEQUENCE IF NOT EXISTS seq_recu_paiement START 1;

CREATE TABLE IF NOT EXISTS paiements (
  id                SERIAL PRIMARY KEY,
  eleve_id          INT REFERENCES eleves(id) ON DELETE CASCADE,
  frais_id          INT REFERENCES frais(id) ON DELETE CASCADE,
  montant_paye      DECIMAL(12,2) NOT NULL CHECK (montant_paye > 0),
  date_paiement     TIMESTAMP DEFAULT NOW(),
  mode              VARCHAR(30) CHECK (mode IN ('especes','mobile_money','carte','virement')),
  reference         VARCHAR(100),
  recu_num          VARCHAR(50) UNIQUE NOT NULL,
  encaisse_par      INT REFERENCES utilisateurs(id) ON DELETE SET NULL
);

-- 14. PRÉSENCES
CREATE TABLE IF NOT EXISTS presences (
  id          SERIAL PRIMARY KEY,
  eleve_id    INT REFERENCES eleves(id) ON DELETE CASCADE,
  date_jour   DATE NOT NULL,
  statut      VARCHAR(20) CHECK (statut IN ('present','absent','retard','excuse')),
  motif       TEXT,
  saisi_par   INT REFERENCES utilisateurs(id) ON DELETE SET NULL,
  UNIQUE (eleve_id, date_jour)
);

-- 15. COMMUNIQUÉS
CREATE TABLE IF NOT EXISTS communiques (
  id           SERIAL PRIMARY KEY,
  auteur_id    INT REFERENCES utilisateurs(id) ON DELETE SET NULL,
  titre        VARCHAR(200) NOT NULL,
  contenu      TEXT NOT NULL,
  categorie    VARCHAR(30) CHECK (categorie IN ('urgent','academique','evenement','general')),
  cible        VARCHAR(50) DEFAULT 'tous',
  date_pub     TIMESTAMP DEFAULT NOW()
);

-- 16. NOTIFICATIONS
CREATE TABLE IF NOT EXISTS notifications (
  id              SERIAL PRIMARY KEY,
  destinataire_id INT REFERENCES utilisateurs(id) ON DELETE CASCADE,
  titre           VARCHAR(200),
  message         TEXT,
  lu              BOOLEAN DEFAULT FALSE,
  date_envoi      TIMESTAMP DEFAULT NOW()
);

-- 17. EMPLOI DU TEMPS
CREATE TABLE IF NOT EXISTS emploi_du_temps (
  id             SERIAL PRIMARY KEY,
  classe_id      INT REFERENCES classes(id) ON DELETE CASCADE,
  jour           VARCHAR(20) NOT NULL CHECK (jour IN
                 ('Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi')),
  heure_debut    TIME NOT NULL,
  heure_fin      TIME NOT NULL,
  matiere_id     INT REFERENCES matieres(id) ON DELETE CASCADE,
  professeur_id  INT REFERENCES professeurs(id) ON DELETE SET NULL,
  salle          VARCHAR(50),
  CHECK (heure_fin > heure_debut)
);

-- 18. ÉVÉNEMENTS
CREATE TABLE IF NOT EXISTS evenements (
  id          SERIAL PRIMARY KEY,
  titre       VARCHAR(200) NOT NULL,
  description TEXT,
  date_debut  TIMESTAMP NOT NULL,
  date_fin    TIMESTAMP,
  type        VARCHAR(50),
  cible       VARCHAR(50) DEFAULT 'tous'
);

-- 19. DEVOIRS
CREATE TABLE IF NOT EXISTS devoirs (
  id             SERIAL PRIMARY KEY,
  matiere_id     INT REFERENCES matieres(id) ON DELETE CASCADE,
  classe_id      INT REFERENCES classes(id) ON DELETE CASCADE,
  professeur_id  INT REFERENCES professeurs(id) ON DELETE SET NULL,
  titre          VARCHAR(200) NOT NULL,
  description    TEXT,
  date_limite    DATE,
  fichier_url    VARCHAR(255),
  date_creation  TIMESTAMP DEFAULT NOW()
);

-- 20. MESSAGERIE
CREATE TABLE IF NOT EXISTS conversations (
  id            SERIAL PRIMARY KEY,
  user1_id      INT REFERENCES utilisateurs(id) ON DELETE CASCADE,
  user2_id      INT REFERENCES utilisateurs(id) ON DELETE CASCADE,
  date_creation TIMESTAMP DEFAULT NOW(),
  UNIQUE (user1_id, user2_id)
);

CREATE TABLE IF NOT EXISTS messages (
  id               SERIAL PRIMARY KEY,
  conversation_id  INT REFERENCES conversations(id) ON DELETE CASCADE,
  expediteur_id    INT REFERENCES utilisateurs(id) ON DELETE CASCADE,
  contenu          TEXT NOT NULL,
  lu               BOOLEAN DEFAULT FALSE,
  date_envoi       TIMESTAMP DEFAULT NOW()
);

-- 21. DOCUMENTS
CREATE TABLE IF NOT EXISTS documents (
  id            SERIAL PRIMARY KEY,
  eleve_id      INT REFERENCES eleves(id) ON DELETE CASCADE,
  type_doc      VARCHAR(50),
  fichier_url   VARCHAR(255) NOT NULL,
  date_ajout    TIMESTAMP DEFAULT NOW()
);

-- =========================================================
-- INDEX POUR PERFORMANCE
-- =========================================================
CREATE INDEX IF NOT EXISTS idx_eleves_matricule ON eleves(matricule);
CREATE INDEX IF NOT EXISTS idx_eleves_classe ON eleves(classe_id);
CREATE INDEX IF NOT EXISTS idx_eleves_annee_entree ON eleves(annee_entree);
CREATE INDEX IF NOT EXISTS idx_notes_eleve ON notes(eleve_id);
CREATE INDEX IF NOT EXISTS idx_notes_periode ON notes(periode);
CREATE INDEX IF NOT EXISTS idx_paiements_eleve ON paiements(eleve_id);
CREATE INDEX IF NOT EXISTS idx_presences_eleve ON presences(eleve_id);
CREATE INDEX IF NOT EXISTS idx_presences_date ON presences(date_jour);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_notifications_destinataire ON notifications(destinataire_id);
CREATE INDEX IF NOT EXISTS idx_communiques_date ON communiques(date_pub DESC);
CREATE INDEX IF NOT EXISTS idx_edt_classe_jour ON emploi_du_temps(classe_id, jour);

COMMIT;

-- =========================================================
-- FIN DU SCRIPT
-- =========================================================
