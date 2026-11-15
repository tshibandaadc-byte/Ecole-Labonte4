// =========================================
// models/communiqueModel.js
// =========================================
const pool = require('../config/db');

async function publierCommunique({ auteur_id, titre, contenu, categorie, cible }) {
  const { rows } = await pool.query(
    `INSERT INTO communiques (auteur_id, titre, contenu, categorie, cible)
     VALUES ($1, $2, $3, $4, $5)
     RETURNING *`,
    [auteur_id, titre, contenu, categorie || 'general', cible || 'tous']
  );
  return rows[0];
}

async function listerCommuniques({ cible, limite = 50 }) {
  const params = [limite];
  let filtre = '';
  if (cible) {
    params.push(cible);
    filtre = `AND (cible = $2 OR cible = 'tous')`;
  }
  const { rows } = await pool.query(
    `SELECT c.*, u.nom AS auteur_nom, u.prenom AS auteur_prenom
     FROM communiques c
     LEFT JOIN utilisateurs u ON u.id = c.auteur_id
     WHERE 1=1 ${filtre}
     ORDER BY c.date_pub DESC
     LIMIT $1`,
    params
  );
  return rows;
}

module.exports = { publierCommunique, listerCommuniques };
