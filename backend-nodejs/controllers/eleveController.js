// =========================================
// controllers/eleveController.js
// =========================================
const bcrypt = require('bcrypt');
const eleveModel = require('../models/eleveModel');
const { validerInscriptionEleve } = require('../utils/validation');
const { AppError } = require('../middleware/errorMiddleware');

const SALT_ROUNDS = 10;

// POST /api/eleves/inscription
async function inscrire(req, res, next) {
  try {
    validerInscriptionEleve(req.body);

    const mot_de_passe_hash = await bcrypt.hash(req.body.mot_de_passe, SALT_ROUNDS);

    const resultat = await eleveModel.creerInscriptionEleve({
      ...req.body,
      mot_de_passe_hash,
    });

    res.status(201).json({
      success: true,
      message: 'Inscription réussie.',
      data: {
        matricule: resultat.eleve.matricule,
        eleve: {
          id: resultat.eleve.id,
          nom: resultat.utilisateur.nom,
          prenom: resultat.utilisateur.prenom,
          classe_id: resultat.eleve.classe_id,
          date_naissance: resultat.eleve.date_naissance,
        },
      },
    });
  } catch (err) {
    next(err);
  }
}

// GET /api/eleves/moi
async function monProfil(req, res, next) {
  try {
    if (req.utilisateur.role === 'parent') {
      const enfants = await eleveModel.listerEnfantsDuTuteur(req.utilisateur.id);
      return res.json({ success: true, data: enfants, total: enfants.length });
    }
    const eleve = await eleveModel.trouverParUtilisateur(req.utilisateur.id);
    if (!eleve) throw new AppError('Aucune fiche élève liée à ce compte.', 404);
    res.json({ success: true, data: eleve });
  } catch (err) {
    next(err);
  }
}

// GET /api/eleves/matricule/:matricule
async function obtenirParMatricule(req, res, next) {
  try {
    const eleve = await eleveModel.trouverParMatricule(req.params.matricule);
    if (!eleve) {
      throw new AppError('Aucun élève trouvé avec ce matricule.', 404);
    }
    res.json({ success: true, data: eleve });
  } catch (err) {
    next(err);
  }
}

// GET /api/eleves/:id
async function obtenirParId(req, res, next) {
  try {
    const eleve = await eleveModel.trouverParId(req.params.id);
    if (!eleve) {
      throw new AppError('Élève non trouvé.', 404);
    }
    res.json({ success: true, data: eleve });
  } catch (err) {
    next(err);
  }
}

// GET /api/eleves/classe/:classeId
async function listerParClasse(req, res, next) {
  try {
    const eleves = await eleveModel.listerParClasse(req.params.classeId);
    res.json({ success: true, data: eleves, total: eleves.length });
  } catch (err) {
    next(err);
  }
}

module.exports = { monProfil, inscrire, obtenirParMatricule, obtenirParId, listerParClasse };
