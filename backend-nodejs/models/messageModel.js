// =========================================
// models/messageModel.js
// =========================================
const pool = require('../config/db');

// Trouve ou crée la conversation entre deux utilisateurs
async function obtenirOuCreerConversation(user1Id, user2Id) {
  // Normaliser l'ordre pour respecter la contrainte UNIQUE(user1_id, user2_id)
  const [a, b] = [user1Id, user2Id].sort((x, y) => x - y);

  const existante = await pool.query(
    `SELECT * FROM conversations WHERE user1_id = $1 AND user2_id = $2`,
    [a, b]
  );
  if (existante.rows.length > 0) return existante.rows[0];

  const { rows } = await pool.query(
    `INSERT INTO conversations (user1_id, user2_id) VALUES ($1, $2) RETURNING *`,
    [a, b]
  );
  return rows[0];
}

async function envoyerMessage({ expediteur_id, destinataire_id, contenu }) {
  const conversation = await obtenirOuCreerConversation(expediteur_id, destinataire_id);

  const { rows } = await pool.query(
    `INSERT INTO messages (conversation_id, expediteur_id, contenu)
     VALUES ($1, $2, $3)
     RETURNING *`,
    [conversation.id, expediteur_id, contenu]
  );
  return { ...rows[0], conversation_id: conversation.id };
}

async function listerConversations(utilisateurId) {
  const { rows } = await pool.query(
    `SELECT c.id AS conversation_id,
            CASE WHEN c.user1_id = $1 THEN c.user2_id ELSE c.user1_id END AS autre_utilisateur_id,
            u.nom, u.prenom, u.photo_url, u.role,
            m.contenu AS dernier_message, m.date_envoi AS dernier_envoi,
            (SELECT COUNT(*) FROM messages
             WHERE conversation_id = c.id AND lu = FALSE AND expediteur_id != $1) AS non_lus
     FROM conversations c
     JOIN utilisateurs u ON u.id = CASE WHEN c.user1_id = $1 THEN c.user2_id ELSE c.user1_id END
     LEFT JOIN LATERAL (
       SELECT contenu, date_envoi FROM messages
       WHERE conversation_id = c.id
       ORDER BY date_envoi DESC LIMIT 1
     ) m ON TRUE
     WHERE c.user1_id = $1 OR c.user2_id = $1
     ORDER BY m.date_envoi DESC NULLS LAST`,
    [utilisateurId]
  );
  return rows;
}

async function listerMessages(conversationId, utilisateurId) {
  const { rows } = await pool.query(
    `SELECT * FROM messages WHERE conversation_id = $1 ORDER BY date_envoi ASC`,
    [conversationId]
  );
  // Marquer comme lus les messages reçus (pas envoyés par l'utilisateur courant)
  await pool.query(
    `UPDATE messages SET lu = TRUE
     WHERE conversation_id = $1 AND expediteur_id != $2 AND lu = FALSE`,
    [conversationId, utilisateurId]
  );
  return rows;
}

module.exports = { envoyerMessage, listerConversations, listerMessages, obtenirOuCreerConversation };
