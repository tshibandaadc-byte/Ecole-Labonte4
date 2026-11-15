// =========================================
// models/noteModel.js
// =========================================
const pool = require('../config/db');

async function saisirNote({ eleve_id, matiere_id, professeur_id, type_eval, note, coefficient, periode, date_eval }) {
  const { rows } = await pool.query(
    `INSERT INTO notes (eleve_id, matiere_id, professeur_id, type_eval, note, coefficient, periode, date_eval)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
     RETURNING *`,
    [eleve_id, matiere_id, professeur_id, type_eval, note, coefficient || 1, periode, date_eval || null]
  );
  return rows[0];
}

// Saisie groupée (ex: notes d'une classe entière pour une évaluation)
async function saisirNotesGroupees(notesArray) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const resultats = [];
    for (const n of notesArray) {
      const { rows } = await client.query(
        `INSERT INTO notes (eleve_id, matiere_id, professeur_id, type_eval, note, coefficient, periode, date_eval)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
         RETURNING *`,
        [n.eleve_id, n.matiere_id, n.professeur_id, n.type_eval, n.note, n.coefficient || 1, n.periode, n.date_eval || null]
      );
      resultats.push(rows[0]);
    }
    await client.query('COMMIT');
    return resultats;
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

async function listerParEleve(eleveId, periode) {
  const params = [eleveId];
  let filtre = '';
  if (periode) {
    params.push(periode);
    filtre = 'AND n.periode = $2';
  }
  const { rows } = await pool.query(
    `SELECT n.id, n.note, n.coefficient, n.type_eval, n.periode, n.date_eval,
            m.nom AS matiere, m.coefficient AS matiere_coefficient
     FROM notes n
     JOIN matieres m ON m.id = n.matiere_id
     WHERE n.eleve_id = $1 ${filtre}
     ORDER BY m.nom, n.date_eval`,
    params
  );
  return rows;
}

// Calcule la moyenne pondérée d'un élève pour une période donnée
async function calculerMoyenne(eleveId, periode) {
  const { rows } = await pool.query(
    `SELECT
       ROUND(SUM(n.note * n.coefficient) / NULLIF(SUM(n.coefficient), 0), 2) AS moyenne
     FROM notes n
     WHERE n.eleve_id = $1 AND n.periode = $2`,
    [eleveId, periode]
  );
  return rows[0].moyenne;
}

// Calcule le rang d'un élève dans sa classe pour une période
async function calculerRang(eleveId, periode) {
  const { rows } = await pool.query(
    `WITH moyennes_classe AS (
       SELECT e.id AS eleve_id,
              ROUND(SUM(n.note * n.coefficient) / NULLIF(SUM(n.coefficient), 0), 2) AS moyenne
       FROM eleves e
       JOIN notes n ON n.eleve_id = e.id AND n.periode = $2
       WHERE e.classe_id = (SELECT classe_id FROM eleves WHERE id = $1)
       GROUP BY e.id
     ),
     classement AS (
       SELECT eleve_id, moyenne, RANK() OVER (ORDER BY moyenne DESC) AS rang
       FROM moyennes_classe
     )
     SELECT rang, (SELECT COUNT(*) FROM moyennes_classe) AS total_classe
     FROM classement
     WHERE eleve_id = $1`,
    [eleveId, periode]
  );
  return rows[0] || { rang: null, total_classe: 0 };
}

// Génère (ou met à jour) le bulletin d'un élève pour une période
async function genererBulletin(eleveId, periode) {
  const moyenne = await calculerMoyenne(eleveId, periode);
  const { rang, total_classe } = await calculerRang(eleveId, periode);

  const { rows } = await pool.query(
    `INSERT INTO bulletins (eleve_id, periode, moyenne, rang, statut)
     VALUES ($1, $2, $3, $4, 'brouillon')
     ON CONFLICT (eleve_id, periode)
     DO UPDATE SET moyenne = EXCLUDED.moyenne, rang = EXCLUDED.rang
     RETURNING *`,
    [eleveId, periode, moyenne, rang]
  );
  return { ...rows[0], total_classe };
}

async function publierBulletin(bulletinId, pdfUrl) {
  const { rows } = await pool.query(
    `UPDATE bulletins
     SET statut = 'publie', pdf_url = $2, date_publication = NOW()
     WHERE id = $1
     RETURNING *`,
    [bulletinId, pdfUrl || null]
  );
  return rows[0];
}

async function obtenirBulletin(eleveId, periode) {
  const { rows } = await pool.query(
    `SELECT * FROM bulletins WHERE eleve_id = $1 AND periode = $2`,
    [eleveId, periode]
  );
  return rows[0] || null;
}

module.exports = {
  saisirNote,
  saisirNotesGroupees,
  listerParEleve,
  calculerMoyenne,
  calculerRang,
  genererBulletin,
  publierBulletin,
  obtenirBulletin,
};
