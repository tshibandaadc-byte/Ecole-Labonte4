// =========================================
// utils/validation.js
// =========================================
const { AppError } = require('../middleware/errorMiddleware');

const CLASSES_VALIDES_NIVEAUX = [1, 2, 3, 4, 5, 6];
const SEXES_VALIDES = ['M', 'F'];

function validerInscriptionEleve(body) {
  const erreurs = [];

  if (!body.nom || body.nom.trim().length < 2) {
    erreurs.push('Le nom est requis (2 caractères minimum).');
  }
  if (!body.prenom || body.prenom.trim().length < 2) {
    erreurs.push('Le prénom est requis (2 caractères minimum).');
  }
  if (!body.date_naissance || isNaN(Date.parse(body.date_naissance))) {
    erreurs.push('La date de naissance est requise et doit être valide (AAAA-MM-JJ).');
  } else {
    const age = calculerAge(body.date_naissance);
    if (age < 2 || age > 25) {
      erreurs.push('La date de naissance semble invalide pour une inscription scolaire.');
    }
  }
  if (!body.sexe || !SEXES_VALIDES.includes(body.sexe)) {
    erreurs.push("Le sexe doit être 'M' ou 'F'.");
  }
  if (!body.classe_id) {
    erreurs.push('La classe souhaitée est requise.');
  }
  if (!body.mot_de_passe || body.mot_de_passe.length < 6) {
    erreurs.push('Le mot de passe doit contenir au moins 6 caractères.');
  }
  if (!body.telephone && !body.email) {
    erreurs.push("Au moins un contact (téléphone ou email) est requis pour l'élève.");
  }
  if (!body.tuteur_telephone) {
    erreurs.push('Le téléphone du tuteur est requis.');
  }

  if (erreurs.length > 0) {
    throw new AppError(erreurs.join(' '), 400);
  }
}

function calculerAge(dateNaissance) {
  const naissance = new Date(dateNaissance);
  const aujourdHui = new Date();
  let age = aujourdHui.getFullYear() - naissance.getFullYear();
  const m = aujourdHui.getMonth() - naissance.getMonth();
  if (m < 0 || (m === 0 && aujourdHui.getDate() < naissance.getDate())) {
    age--;
  }
  return age;
}

module.exports = { validerInscriptionEleve, CLASSES_VALIDES_NIVEAUX };
