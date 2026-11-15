// =========================================
// controllers/paiementController.js
// =========================================
const paiementModel = require('../models/paiementModel');
const { AppError } = require('../middleware/errorMiddleware');

// GET /api/frais/eleve/:id
async function listerFrais(req, res, next) {
  try {
    const frais = await paiementModel.listerFraisParEleve(req.params.id);
    res.json({ success: true, data: frais });
  } catch (err) {
    next(err);
  }
}

// POST /api/paiements
async function payer(req, res, next) {
  try {
    const { eleve_id, frais_id, montant_paye, mode, reference } = req.body;

    if (!eleve_id || !frais_id || !montant_paye || !mode) {
      throw new AppError('eleve_id, frais_id, montant_paye et mode sont requis.', 400);
    }
    if (montant_paye <= 0) {
      throw new AppError('Le montant payé doit être positif.', 400);
    }

    const encaisse_par = req.utilisateur.id;

    const paiement = await paiementModel.enregistrerPaiement({
      eleve_id, frais_id, montant_paye, mode, reference, encaisse_par,
    });

    res.status(201).json({ success: true, message: 'Paiement enregistré.', data: paiement });
  } catch (err) {
    next(err);
  }
}

// GET /api/paiements/eleve/:id
async function historique(req, res, next) {
  try {
    const paiements = await paiementModel.historiquePaiements(req.params.id);
    res.json({ success: true, data: paiements });
  } catch (err) {
    next(err);
  }
}

// GET /api/paiements/stats/jour  (dashboard assistant)
async function statsDuJour(req, res, next) {
  try {
    const stats = await paiementModel.paiementsDuJour();
    res.json({ success: true, data: stats });
  } catch (err) {
    next(err);
  }
}

// GET /api/paiements/stats/recouvrement?annee=2026-2027  (dashboard direction)
async function statsRecouvrement(req, res, next) {
  try {
    const annee = req.query.annee;
    if (!annee) throw new AppError("Le paramètre 'annee' est requis (ex: 2026-2027).", 400);
    const stats = await paiementModel.tauxRecouvrement(annee);
    res.json({ success: true, data: stats });
  } catch (err) {
    next(err);
  }
}

module.exports = { listerFrais, payer, historique, statsDuJour, statsRecouvrement };
