// =========================================
// controllers/authController.js
// =========================================
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const authModel = require('../models/authModel');
const { AppError } = require('../middleware/errorMiddleware');

// POST /api/auth/login  { identifiant, mot_de_passe }
async function login(req, res, next) {
  try {
    const { identifiant, mot_de_passe } = req.body;
    if (!identifiant || !mot_de_passe) {
      throw new AppError('Identifiant et mot de passe requis.', 400);
    }

    const utilisateur = await authModel.trouverParIdentifiant(identifiant.trim());
    // Même message si le compte n'existe pas ou si le mot de passe est faux
    // (on ne révèle pas lequel des deux est faux).
    if (!utilisateur || !(await bcrypt.compare(mot_de_passe, utilisateur.mot_de_passe))) {
      throw new AppError('Identifiants incorrects.', 401);
    }
    if (!utilisateur.actif) {
      throw new AppError('Ce compte a été désactivé.', 403);
    }

    const payload = {
      id: utilisateur.id,
      role: utilisateur.role,
      nom: utilisateur.nom,
      prenom: utilisateur.prenom,
    };
    if (utilisateur.role === 'professeur') {
      payload.professeur_id = await authModel.professeurIdDe(utilisateur.id);
    }

    const token = jwt.sign(payload, process.env.JWT_SECRET || 'change_moi_en_prod', {
      expiresIn: process.env.JWT_EXPIRES_IN || '7d',
    });

    res.json({ access_token: token, token_type: 'bearer', utilisateur: payload });
  } catch (err) {
    next(err);
  }
}

module.exports = { login };
