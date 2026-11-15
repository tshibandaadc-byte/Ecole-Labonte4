// =========================================
// models/authModel.js
// =========================================
const pool = require('../config/db');

// Cherche un compte par téléphone, email ou matricule d'élève
async function trouverParIdentifiant(identifiant) {
  const direct = await pool.query(
    `SELECT id, nom, prenom, role, mot_de_passe, actif
     FROM utilisateurs
     WHERE telephone = $1 OR email = $1`,
    [identifiant]
  );
  if (direct.rows.length > 0) return direct.rows[0];

  const parMatricule = await pool.query(
    `SELECT u.id, u.nom, u.prenom, u.role, u.mot_de_passe, u.actif
     FROM eleves e
     JOIN utilisateurs u ON u.id = e.utilisateur_id
     WHERE e.matricule = $1`,
    [identifiant]
  );
  return parMatricule.rows[0] || null;
}

// Pour un professeur : retrouve professeurs.id (à mettre dans le token)
async function professeurIdDe(utilisateurId) {
  const { rows } = await pool.query(
    `SELECT id FROM professeurs WHERE utilisateur_id = $1`,
    [utilisateurId]
  );
  return rows[0] ? rows[0].id : null;
}

module.exports = { trouverParIdentifiant, professeurIdDe };
