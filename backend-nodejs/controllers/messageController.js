// =========================================
// controllers/messageController.js
// =========================================
const messageModel = require('../models/messageModel');
const { AppError } = require('../middleware/errorMiddleware');

// POST /api/messages
async function envoyer(req, res, next) {
  try {
    const { destinataire_id, contenu } = req.body;
    if (!destinataire_id || !contenu || !contenu.trim()) {
      throw new AppError('destinataire_id et contenu sont requis.', 400);
    }
    const message = await messageModel.envoyerMessage({
      expediteur_id: req.utilisateur.id,
      destinataire_id,
      contenu,
    });
    res.status(201).json({ success: true, data: message });
  } catch (err) {
    next(err);
  }
}

// GET /api/messages  — liste des conversations de l'utilisateur connecté
async function listerConversations(req, res, next) {
  try {
    const conversations = await messageModel.listerConversations(req.utilisateur.id);
    res.json({ success: true, data: conversations });
  } catch (err) {
    next(err);
  }
}

// GET /api/messages/:conversationId
async function listerMessages(req, res, next) {
  try {
    const messages = await messageModel.listerMessages(req.params.conversationId, req.utilisateur.id);
    res.json({ success: true, data: messages });
  } catch (err) {
    next(err);
  }
}

module.exports = { envoyer, listerConversations, listerMessages };
