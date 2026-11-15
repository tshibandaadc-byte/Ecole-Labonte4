// =========================================
// controllers/noteController.js
// =========================================
const noteModel = require('../models/noteModel');
const { AppError } = require('../middleware/errorMiddleware');

// POST /api/notes  — saisie d'une note unique (par un professeur)
async function saisir(req, res, next) {
  try {
    const { eleve_id, matiere_id, type_eval, note, coefficient, periode, date_eval } = req.body;

    if (!eleve_id || !matiere_id || note === undefined || !periode) {
      throw new AppError('eleve_id, matiere_id, note et periode sont requis.', 400);
    }
    if (note < 0 || note > 20) {
      throw new AppError('La note doit être comprise entre 0 et 20.', 400);
    }

    const professeur_id = req.utilisateur.professeur_id || null; // injecté par le token si dispo

    const resultat = await noteModel.saisirNote({
      eleve_id, matiere_id, professeur_id, type_eval, note, coefficient, periode, date_eval,
    });

    res.status(201).json({ success: true, message: 'Note enregistrée.', data: resultat });
  } catch (err) {
    next(err);
  }
}

// POST /api/notes/groupe  — saisie groupée pour toute une classe
async function saisirGroupe(req, res, next) {
  try {
    const { notes } = req.body;
    if (!Array.isArray(notes) || notes.length === 0) {
      throw new AppError('Le champ "notes" doit être un tableau non vide.', 400);
    }
    for (const n of notes) {
      if (n.note < 0 || n.note > 20) {
        throw new AppError(`Note invalide (${n.note}) pour l'élève ${n.eleve_id}.`, 400);
      }
    }
    const resultats = await noteModel.saisirNotesGroupees(notes);
    res.status(201).json({ success: true, message: `${resultats.length} notes enregistrées.`, data: resultats });
  } catch (err) {
    next(err);
  }
}

// GET /api/notes/eleve/:id?periode=Trimestre 1
async function listerParEleve(req, res, next) {
  try {
    const { periode } = req.query;
    const notes = await noteModel.listerParEleve(req.params.id, periode);
    const moyenne = periode ? await noteModel.calculerMoyenne(req.params.id, periode) : null;
    res.json({ success: true, data: { notes, moyenne } });
  } catch (err) {
    next(err);
  }
}

// GET /api/bulletins/:eleveId/:periode
async function obtenirOuGenererBulletin(req, res, next) {
  try {
    const { eleveId, periode } = req.params;
    let bulletin = await noteModel.obtenirBulletin(eleveId, periode);
    if (!bulletin) {
      bulletin = await noteModel.genererBulletin(eleveId, periode);
    }
    res.json({ success: true, data: bulletin });
  } catch (err) {
    next(err);
  }
}

// POST /api/bulletins/:eleveId/:periode/publier  (direction/professeur principal)
async function publier(req, res, next) {
  try {
    const { eleveId, periode } = req.params;
    const bulletin = await noteModel.genererBulletin(eleveId, periode); // recalcule avant publication
    const publie = await noteModel.publierBulletin(bulletin.id, req.body.pdf_url);
    res.json({ success: true, message: 'Bulletin publié.', data: publie });
  } catch (err) {
    next(err);
  }
}

module.exports = { saisir, saisirGroupe, listerParEleve, obtenirOuGenererBulletin, publier };
