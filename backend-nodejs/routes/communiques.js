// =========================================
// routes/communiques.js
// =========================================
const express = require('express');
const router = express.Router();
const communiqueController = require('../controllers/communiqueController');
const messageController = require('../controllers/messageController');
const { verifierToken, verifierRole } = require('../middleware/authMiddleware');

// --- Communiqués ---
router.post(
  '/communiques',
  verifierToken,
  verifierRole('assistant', 'direction', 'promoteur'),
  communiqueController.publier
);
router.get('/communiques', verifierToken, communiqueController.lister);

// --- Messagerie ---
router.post('/messages', verifierToken, messageController.envoyer);
router.get('/messages', verifierToken, messageController.listerConversations);
router.get('/messages/:conversationId', verifierToken, messageController.listerMessages);

module.exports = router;
