// =========================================
// middleware/authMiddleware.js
// =========================================
const jwt = require('jsonwebtoken');
const { AppError } = require('./errorMiddleware');

// Vérifie le token JWT envoyé dans le header Authorization: Bearer <token>
function verifierToken(req, res, next) {
  try {
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      throw new AppError('Authentification requise. Token manquant.', 401);
    }
    const token = authHeader.split(' ')[1];
    const decoded = jwt.verify(token, process.env.JWT_SECRET || 'change_moi_en_prod');
    req.utilisateur = decoded; // { id, role, nom, prenom }
    next();
  } catch (err) {
    if (err.name === 'JsonWebTokenError' || err.name === 'TokenExpiredError') {
      return next(new AppError('Token invalide ou expiré.', 401));
    }
    next(err);
  }
}

// Vérifie que l'utilisateur connecté a un des rôles autorisés
// Usage : verifierRole('assistant', 'direction')
function verifierRole(...rolesAutorises) {
  return (req, res, next) => {
    if (!req.utilisateur) {
      return next(new AppError('Authentification requise.', 401));
    }
    if (!rolesAutorises.includes(req.utilisateur.role)) {
      return next(
        new AppError(
          `Accès refusé. Rôle requis : ${rolesAutorises.join(' ou ')}.`,
          403
        )
      );
    }
    next();
  };
}

module.exports = { verifierToken, verifierRole };
