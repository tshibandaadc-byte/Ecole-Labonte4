// =========================================
// models/eleveModel.js
// =========================================
const pool = require('../config/db');

/**
 * Génère le prochain matricule pour une année donnée : <annee>-NNNN.
 * Utilise une table de compteurs (compteurs_matricule) mise à jour via
 * INSERT ... ON CONFLICT ... RETURNING, atomique au niveau PostgreSQL :
 * deux inscriptions simultanées pour la même année ne peuvent jamais
 * recevoir le même numéro (contrairement à un COUNT(*), qui peut être
 * lu deux fois avec la même valeur avant qu'aucune des deux
 * transactions n'ait inséré sa ligne).
 */
async function genererMatricule(client, annee) {
  const { rows } = await client.query(
    `INSERT INTO compteurs_matricule (annee, dernier)
     VALUES ($1, 1)
     ON CONFLICT (annee) DO UPDATE SET dernier = compteurs_matricule.dernier + 1
     RETURNING dernier`,
    [annee]
  );

  const sequence = String(rows[0].dernier).padStart(4, '0');
  return `${annee}-${sequence}`;
}

/**
 * Crée le compte utilisateur (role='eleve') + la fiche eleves,
 * et gère le parent/tuteur (création si téléphone inconnu, ou
 * rattachement si le tuteur existe déjà).
 * Tout est exécuté dans une transaction SQL unique.
 */
async function creerInscriptionEleve(donnees) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    const {
      nom,
      prenom,
      date_naissance,
      lieu_naissance,
      sexe,
      classe_id,
      mot_de_passe_hash,
      telephone,
      email,
      tuteur_nom,
      tuteur_telephone,
    } = donnees;

    const anneeEntree = new Date().getFullYear();

    // 1. Résoudre le tuteur : existe-t-il déjà par téléphone ?
    let tuteurId = null;
    if (tuteur_telephone) {
      const tuteurExistant = await client.query(
        `SELECT id FROM utilisateurs WHERE telephone = $1`,
        [tuteur_telephone]
      );

      if (tuteurExistant.rows.length > 0) {
        tuteurId = tuteurExistant.rows[0].id;
      } else {
        // Créer un compte "parent" minimal (mot de passe temporaire,
        // à faire changer lors de sa première connexion)
        const nouveauTuteur = await client.query(
          `INSERT INTO utilisateurs (nom, prenom, telephone, mot_de_passe, role)
           VALUES ($1, $2, $3, $4, 'parent')
           RETURNING id`,
          [tuteur_nom || 'Tuteur', prenom, tuteur_telephone, mot_de_passe_hash]
        );
        tuteurId = nouveauTuteur.rows[0].id;

        await client.query(
          `INSERT INTO parents (utilisateur_id) VALUES ($1)`,
          [tuteurId]
        );
      }
    }

    // 2. Créer le compte utilisateur de l'élève
    const nouvelUtilisateur = await client.query(
      `INSERT INTO utilisateurs (nom, prenom, telephone, email, mot_de_passe, role)
       VALUES ($1, $2, $3, $4, $5, 'eleve')
       RETURNING id, nom, prenom, telephone, email, role, date_creation`,
      [nom, prenom, telephone || null, email || null, mot_de_passe_hash]
    );
    const utilisateur = nouvelUtilisateur.rows[0];

    // 3. Générer le matricule (verrouillage transactionnel)
    const matricule = await genererMatricule(client, anneeEntree);

    // 4. Créer la fiche élève
    const nouvelEleve = await client.query(
      `INSERT INTO eleves
        (utilisateur_id, matricule, date_naissance, lieu_naissance, sexe,
         tuteur_id, classe_id, annee_entree, statut)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'actif')
       RETURNING id, matricule, date_naissance, lieu_naissance, sexe,
                 classe_id, annee_entree, statut`,
      [
        utilisateur.id,
        matricule,
        date_naissance,
        lieu_naissance || null,
        sexe,
        tuteurId,
        classe_id,
        anneeEntree,
      ]
    );

    await client.query('COMMIT');

    return {
      utilisateur,
      eleve: nouvelEleve.rows[0],
      tuteur_id: tuteurId,
    };
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

async function trouverParMatricule(matricule) {
  const { rows } = await pool.query(
    `SELECT e.*, u.nom, u.prenom, u.telephone, u.email, u.photo_url
     FROM eleves e
     JOIN utilisateurs u ON u.id = e.utilisateur_id
     WHERE e.matricule = $1`,
    [matricule]
  );
  return rows[0] || null;
}

async function trouverParId(eleveId) {
  const { rows } = await pool.query(
    `SELECT e.*, u.nom, u.prenom, u.telephone, u.email, u.photo_url,
            c.nom AS classe_nom, c.niveau
     FROM eleves e
     JOIN utilisateurs u ON u.id = e.utilisateur_id
     LEFT JOIN classes c ON c.id = e.classe_id
     WHERE e.id = $1`,
    [eleveId]
  );
  return rows[0] || null;
}

async function listerParClasse(classeId) {
  const { rows } = await pool.query(
    `SELECT e.id, e.matricule, e.statut, u.nom, u.prenom, u.photo_url
     FROM eleves e
     JOIN utilisateurs u ON u.id = e.utilisateur_id
     WHERE e.classe_id = $1
     ORDER BY u.nom, u.prenom`,
    [classeId]
  );
  return rows;
}

async function trouverParUtilisateur(utilisateurId) {
  const { rows } = await pool.query(
    `SELECT e.*, u.nom, u.prenom, u.telephone, u.email, u.photo_url,
            c.nom AS classe_nom, c.niveau
     FROM eleves e
     JOIN utilisateurs u ON u.id = e.utilisateur_id
     LEFT JOIN classes c ON c.id = e.classe_id
     WHERE e.utilisateur_id = $1`,
    [utilisateurId]
  );
  return rows[0] || null;
}

async function listerEnfantsDuTuteur(tuteurId) {
  const { rows } = await pool.query(
    `SELECT e.id, e.matricule, e.statut, e.classe_id, u.nom, u.prenom, u.photo_url
     FROM eleves e
     JOIN utilisateurs u ON u.id = e.utilisateur_id
     WHERE e.tuteur_id = $1
     ORDER BY u.nom, u.prenom`,
    [tuteurId]
  );
  return rows;
}

module.exports = {
  trouverParUtilisateur,
  listerEnfantsDuTuteur,
  creerInscriptionEleve,
  trouverParMatricule,
  trouverParId,
  listerParClasse,
};
