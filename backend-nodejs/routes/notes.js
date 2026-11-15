// =========================================
// routes/notes.js
// =========================================
const express = require('express');
const router = express.Router();
const noteController = require('../controllers/noteController');
const { verifierToken, verifierRole } = require('../middleware/authMiddleware');

// Saisie de notes — professeurs uniquement
router.post('/notes', verifierToken, verifierRole('professeur'), noteController.saisir);
router.post('/notes/groupe', verifierToken, verifierRole('professeur'), noteController.saisirGroupe);

// Consultation des notes — élève, parent, professeur, assistant, direction
router.get('/notes/eleve/:id', verifierToken, noteController.listerParEleve);

// Bulletins
router.get('/bulletins/:eleveId/:periode', verifierToken, noteController.obtenirOuGenererBulletin);
router.post(
  '/bulletins/:eleveId/:periode/publier',
  verifierToken,
  verifierRole('professeur', 'direction', 'promoteur'),
  noteController.publier
);

module.exports = router;
