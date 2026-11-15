// =========================================
// routes/paiements.js
// =========================================
const express = require('express');
const router = express.Router();
const paiementController = require('../controllers/paiementController');
const { verifierToken, verifierRole } = require('../middleware/authMiddleware');

// Consultation des frais — élève, parent, assistant, direction
router.get('/frais/eleve/:id', verifierToken, paiementController.listerFrais);

// Enregistrer un paiement — assistant, direction (encaissement physique)
// ou parent/élève (paiement mobile money en self-service)
router.post(
  '/paiements',
  verifierToken,
  verifierRole('assistant', 'direction', 'promoteur', 'parent', 'eleve'),
  paiementController.payer
);

// Historique des paiements d'un élève
router.get('/paiements/eleve/:id', verifierToken, paiementController.historique);

// Statistiques — assistant, direction uniquement
router.get(
  '/paiements/stats/jour',
  verifierToken,
  verifierRole('assistant', 'direction', 'promoteur'),
  paiementController.statsDuJour
);
router.get(
  '/paiements/stats/recouvrement',
  verifierToken,
  verifierRole('direction', 'promoteur'),
  paiementController.statsRecouvrement
);

module.exports = router;
