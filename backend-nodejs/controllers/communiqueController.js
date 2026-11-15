// =========================================
// controllers/communiqueController.js
// =========================================
const communiqueModel = require('../models/communiqueModel');
const { AppError } = require('../middleware/errorMiddleware');

// POST /api/communiques  — direction, assistant
async function publier(req, res, next) {
  try {
    const { titre, contenu, categorie, cible } = req.body;
    if (!titre || !contenu) {
      throw new AppError('Titre et contenu sont requis.', 400);
    }
    const communique = await communiqueModel.publierCommunique({
      auteur_id: req.utilisateur.id,
      titre,
      contenu,
      categorie,
      cible,
    });
    res.status(201).json({ success: true, message: 'Communiqué publié.', data: communique });
  } catch (err) {
    next(err);
  }
}

// GET /api/communiques
async function lister(req, res, next) {
  try {
    const { cible, limite } = req.query;
    const communiques = await communiqueModel.listerCommuniques({ cible, limite });
    res.json({ success: true, data: communiques });
  } catch (err) {
    next(err);
  }
}

module.exports = { publier, lister };
