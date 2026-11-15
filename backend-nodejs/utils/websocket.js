// =========================================
// utils/websocket.js
// Messagerie temps réel — à brancher sur le serveur HTTP existant
// =========================================
const { WebSocketServer } = require('ws');
const jwt = require('jsonwebtoken');
const messageModel = require('../models/messageModel');

// Map utilisateurId -> ws connection
const connexions = new Map();

function demarrerWebSocket(httpServer) {
  const wss = new WebSocketServer({ server: httpServer, path: '/ws' });

  wss.on('connection', (ws, req) => {
    // Authentification via ?token=... dans l'URL de connexion
    const url = new URL(req.url, `http://${req.headers.host}`);
    const token = url.searchParams.get('token');

    let utilisateur;
    try {
      utilisateur = jwt.verify(token, process.env.JWT_SECRET || 'change_moi_en_prod');
    } catch (err) {
      ws.close(4001, 'Token invalide');
      return;
    }

    connexions.set(utilisateur.id, ws);
    console.log(`🔌 Utilisateur ${utilisateur.id} connecté au WebSocket`);

    ws.on('message', async (data) => {
      try {
        const payload = JSON.parse(data.toString());
        // payload attendu : { destinataire_id, contenu }
        if (!payload.destinataire_id || !payload.contenu) return;

        const message = await messageModel.envoyerMessage({
          expediteur_id: utilisateur.id,
          destinataire_id: payload.destinataire_id,
          contenu: payload.contenu,
        });

        // Envoyer au destinataire s'il est connecté
        const wsDestinataire = connexions.get(payload.destinataire_id);
        if (wsDestinataire && wsDestinataire.readyState === wsDestinataire.OPEN) {
          wsDestinataire.send(JSON.stringify({ type: 'nouveau_message', data: message }));
        }
        // Confirmer à l'expéditeur
        ws.send(JSON.stringify({ type: 'message_envoye', data: message }));
      } catch (err) {
        ws.send(JSON.stringify({ type: 'erreur', message: err.message }));
      }
    });

    ws.on('close', () => {
      connexions.delete(utilisateur.id);
      console.log(`🔌 Utilisateur ${utilisateur.id} déconnecté`);
    });
  });

  return wss;
}

module.exports = { demarrerWebSocket };
