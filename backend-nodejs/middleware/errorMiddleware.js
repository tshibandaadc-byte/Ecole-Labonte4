// =========================================
// middleware/errorMiddleware.js
// =========================================

// Erreur métier personnalisée (400, 404, 409...)
class AppError extends Error {
  constructor(message, statusCode = 400) {
    super(message);
    this.statusCode = statusCode;
    this.isOperational = true;
  }
}

// 404 générique
function notFoundHandler(req, res, next) {
  next(new AppError(`Route non trouvée : ${req.originalUrl}`, 404));
}

// Handler final — doit être le DERNIER middleware
function errorHandler(err, req, res, next) {
  const statusCode = err.statusCode || 500;

  // Erreurs PostgreSQL courantes
  if (err.code === '23505') {
    // violation contrainte UNIQUE
    return res.status(409).json({
      success: false,
      message: 'Une ressource avec ces informations existe déjà (doublon).',
      detail: err.detail,
    });
  }
  if (err.code === '23503') {
    // violation clé étrangère
    return res.status(400).json({
      success: false,
      message: 'Référence invalide (clé étrangère non trouvée).',
      detail: err.detail,
    });
  }

  console.error(`[ERREUR] ${statusCode} - ${err.message}`);
  if (!err.isOperational) console.error(err.stack);

  res.status(statusCode).json({
    success: false,
    message: err.isOperational ? err.message : 'Erreur interne du serveur.',
  });
}

module.exports = { AppError, notFoundHandler, errorHandler };
