// =========================================
// routes/eleves.js
// =========================================
const express = require('express');
const router = express.Router();
const eleveController = require('../controllers/eleveController');
const { verifierToken, verifierRole } = require('../middleware/authMiddleware');

// Inscription : ouverte (auto-inscription parent) ou réservée à
// l'assistant/direction selon le mode choisi par l'école.
// Ici : ouverte publiquement, comme prévu à l'Écran 5.
router.post('/inscription', eleveController.inscrire);

// Ma fiche (élève) ou mes enfants (parent) — doit rester AVANT '/:id'
router.get('/moi', verifierToken, eleveController.monProfil);

// Recherche par matricule — utile au secrétariat / à la direction
router.get(
  '/matricule/:matricule',
  verifierToken,
  verifierRole('assistant', 'direction', 'promoteur', 'professeur'),
  eleveController.obtenirParMatricule
);

// Fiche élève par ID — accessible à l'élève lui-même, son tuteur,
// et le personnel de l'école (le contrôle fin "c'est bien SON enfant"
// se fait via la comparaison req.utilisateur.id ↔ tuteur_id côté controller
// si besoin d'un contrôle plus strict).
router.get('/:id', verifierToken, eleveController.obtenirParId);

// Liste des élèves d'une classe — personnel uniquement
router.get(
  '/classe/:classeId',
  verifierToken,
  verifierRole('assistant', 'direction', 'promoteur', 'professeur'),
  eleveController.listerParClasse
);

module.exports = router;
