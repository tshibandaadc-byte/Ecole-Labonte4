// =========================================
// models/paiementModel.js
// =========================================
const pool = require('../config/db');

async function listerFraisParEleve(eleveId) {
  const { rows } = await pool.query(
    `SELECT f.id, f.libelle, f.montant, f.echeance, f.annee_scolaire,
            COALESCE(SUM(p.montant_paye), 0) AS total_paye,
            f.montant - COALESCE(SUM(p.montant_paye), 0) AS reste_a_payer
     FROM frais f
     JOIN eleves e ON e.classe_id = f.classe_id
     LEFT JOIN paiements p ON p.frais_id = f.id AND p.eleve_id = e.id
     WHERE e.id = $1
     GROUP BY f.id
     ORDER BY f.echeance`,
    [eleveId]
  );
  return rows;
}

// Génère un numéro de reçu unique : REC-AAAA-XXXXXX
// Génère un numéro de reçu unique : REC-<année>-<n° sur 6 chiffres>.
// Utilise la séquence PostgreSQL seq_recu_paiement (nextval), dont
// l'incrémentation est atomique : deux paiements enregistrés en même
// temps reçoivent toujours deux numéros différents.
async function genererNumeroRecu(client) {
  const annee = new Date().getFullYear();
  const { rows } = await client.query(`SELECT nextval('seq_recu_paiement') AS sequence`);
  const sequence = String(rows[0].sequence).padStart(6, '0');
  return `REC-${annee}-${sequence}`;
}

async function enregistrerPaiement({ eleve_id, frais_id, montant_paye, mode, reference, encaisse_par }) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // Vérifier que le frais existe et récupérer le solde restant
    const fraisResult = await client.query(
      `SELECT f.montant, COALESCE(SUM(p.montant_paye), 0) AS deja_paye
       FROM frais f
       LEFT JOIN paiements p ON p.frais_id = f.id AND p.eleve_id = $2
       WHERE f.id = $1
       GROUP BY f.montant`,
      [frais_id, eleve_id]
    );

    if (fraisResult.rows.length === 0) {
      throw Object.assign(new Error('Frais introuvable.'), { statusCode: 404, isOperational: true });
    }

    const { montant, deja_paye } = fraisResult.rows[0];
    const resteAvant = parseFloat(montant) - parseFloat(deja_paye);

    if (montant_paye > resteAvant) {
      throw Object.assign(
        new Error(`Le montant dépasse le solde restant (${resteAvant} FCFA).`),
        { statusCode: 400, isOperational: true }
      );
    }

    const recu_num = await genererNumeroRecu(client);

    const { rows } = await client.query(
      `INSERT INTO paiements (eleve_id, frais_id, montant_paye, mode, reference, recu_num, encaisse_par)
       VALUES ($1, $2, $3, $4, $5, $6, $7)
       RETURNING *`,
      [eleve_id, frais_id, montant_paye, mode, reference || null, recu_num, encaisse_par]
    );

    await client.query('COMMIT');
    return rows[0];
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

async function historiquePaiements(eleveId) {
  const { rows } = await pool.query(
    `SELECT p.*, f.libelle AS frais_libelle
     FROM paiements p
     JOIN frais f ON f.id = p.frais_id
     WHERE p.eleve_id = $1
     ORDER BY p.date_paiement DESC`,
    [eleveId]
  );
  return rows;
}

// Statistiques pour le dashboard Assistant/Direction
async function paiementsDuJour() {
  const { rows } = await pool.query(
    `SELECT COUNT(*) AS nb_paiements, COALESCE(SUM(montant_paye), 0) AS total
     FROM paiements
     WHERE date_paiement::date = CURRENT_DATE`
  );
  return rows[0];
}

async function tauxRecouvrement(anneeScolaire) {
  const { rows } = await pool.query(
    `SELECT
       COALESCE(SUM(f.montant), 0) AS total_attendu,
       COALESCE((SELECT SUM(montant_paye) FROM paiements p
                 JOIN frais f2 ON f2.id = p.frais_id
                 WHERE f2.annee_scolaire = $1), 0) AS total_percu
     FROM frais f
     WHERE f.annee_scolaire = $1`,
    [anneeScolaire]
  );
  const { total_attendu, total_percu } = rows[0];
  const taux = total_attendu > 0 ? Math.round((total_percu / total_attendu) * 10000) / 100 : 0;
  return { total_attendu: parseFloat(total_attendu), total_percu: parseFloat(total_percu), taux_pourcentage: taux };
}

module.exports = {
  listerFraisParEleve,
  enregistrerPaiement,
  historiquePaiements,
  paiementsDuJour,
  tauxRecouvrement,
};
