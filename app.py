import os
from datetime import datetime, date
import re
from functools import wraps
from pathlib import Path

from flask import Flask, request, redirect, url_for, flash, send_from_directory, render_template_string, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from markupsafe import escape

ROOT = Path(__file__).resolve().parent
UPLOADS = ROOT / "static" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-this-secret")
db_url = os.getenv("DATABASE_URL", "sqlite:///" + str(ROOT / "shemec.db"))
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config.update(SQLALCHEMY_DATABASE_URI=db_url, SQLALCHEMY_TRACK_MODIFICATIONS=False,
                  MAX_CONTENT_LENGTH=5 * 1024 * 1024, UPLOAD_FOLDER=str(UPLOADS))
db = SQLAlchemy(app)
login = LoginManager(app)
login.login_view = "connexion"
login.login_message = "Connectez-vous pour accéder à cette page."
ALLOWED = {"jpg", "jpeg", "png", "webp"}

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(140), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="eleve")
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=True)
    def set_password(self, raw): self.password = generate_password_hash(raw)
    def verify(self, raw): return check_password_hash(self.password, raw)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    matricule = db.Column(db.String(30), unique=True, nullable=False)
    nom = db.Column(db.String(160), nullable=False)
    photo = db.Column(db.String(255), nullable=False)
    faculte = db.Column(db.String(120), nullable=False)
    filiere = db.Column(db.String(120), nullable=False)
    promotion = db.Column(db.String(80), nullable=False)
    classe = db.Column(db.String(80), nullable=False)
    annee_inscription = db.Column(db.Integer, nullable=True)
    code_faculte = db.Column(db.String(2), nullable=True)
    code_filiere = db.Column(db.String(2), nullable=True)
    nombre_cours = db.Column(db.Integer, default=0)
    credits = db.Column(db.Integer, default=0)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.relationship("Grade", cascade="all,delete-orphan", backref="eleve")
    paiements = db.relationship("Payment", cascade="all,delete-orphan", backref="eleve")
    absences = db.relationship("Attendance", cascade="all,delete-orphan", backref="eleve")
    @property
    def moyenne(self):
        return round(sum(n.note for n in self.notes) / len(self.notes), 2) if self.notes else 0

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    cours = db.Column(db.String(140), nullable=False)
    note = db.Column(db.Float, nullable=False)
    periode = db.Column(db.String(80), default="Trimestre 1")
    annee_academique = db.Column(db.String(20), default="2026-2027")
    promotion = db.Column(db.String(80), default="")

class FacultyCatalog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(2), unique=True, nullable=False)
    nom = db.Column(db.String(140), unique=True, nullable=False)
    filieres = db.relationship("ProgramCatalog", cascade="all,delete-orphan", backref="faculte")

class ProgramCatalog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(2), nullable=False)
    nom = db.Column(db.String(140), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty_catalog.id"), nullable=False)
    __table_args__ = (db.UniqueConstraint("faculty_id", "code", name="uq_program_faculty_code"),
                      db.UniqueConstraint("faculty_id", "nom", name="uq_program_faculty_name"))

class StudentHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    annee_academique = db.Column(db.String(20), nullable=False)
    promotion = db.Column(db.String(80), nullable=False)
    faculte = db.Column(db.String(120), nullable=False)
    filiere = db.Column(db.String(120), nullable=False)
    cours = db.Column(db.String(140), nullable=False)
    credits = db.Column(db.Integer, default=0)
    note = db.Column(db.Float, nullable=True)
    decision = db.Column(db.String(80), default="")
    student = db.relationship("Student", backref=db.backref("historique", cascade="all,delete-orphan"))

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    libelle = db.Column(db.String(140), nullable=False)
    montant = db.Column(db.Integer, nullable=False)
    devise = db.Column(db.String(3), nullable=False, default="CDF")
    statut = db.Column(db.String(20), default="En attente")
    date_paiement = db.Column(db.Date, nullable=True)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    jour = db.Column(db.Date, nullable=False, default=date.today)
    statut = db.Column(db.String(20), nullable=False, default="Absent")
    motif = db.Column(db.String(255), default="")

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    destinataire = db.Column(db.String(80), default="Tous")
    sujet = db.Column(db.String(160), nullable=False)
    contenu = db.Column(db.Text, nullable=False)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    auteur = db.relationship("User")

class CourseSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    classe = db.Column(db.String(80), nullable=False)
    jour = db.Column(db.String(20), nullable=False)
    debut = db.Column(db.String(5), nullable=False)
    fin = db.Column(db.String(5), nullable=False)
    cours = db.Column(db.String(140), nullable=False)
    enseignant = db.Column(db.String(140), default="")

class TeacherAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    cours = db.Column(db.String(140), nullable=False)
    classe = db.Column(db.String(80), nullable=False)
    annee_academique = db.Column(db.String(20), nullable=False)
    volume_horaire = db.Column(db.Integer, nullable=False, default=0)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    enseignant = db.relationship("User", backref=db.backref("affectations", lazy=True))

@login.user_loader
def load_user(uid): return db.session.get(User, int(uid))

def admin_only(fn):
    @wraps(fn)
    @login_required
    def wrapped(*a, **kw):
        if current_user.role != "admin": abort(403)
        return fn(*a, **kw)
    return wrapped

import re
MATRICULE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{6}$")
def matricule_valide(value):
    return bool(MATRICULE_RE.fullmatch((value or "").strip()))

BASE = """
<!doctype html><html lang='fr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<meta name='theme-color' content='#075b49'><link rel='manifest' href='/manifest.json'><link rel='stylesheet' href='/static/style.css'>
<title>{{ title }} · École La Bonté</title></head><body>
{% if current_user.is_authenticated %}<div class='layout'><aside class='side'><a class='brand' href='/'> <b>✦</b><span>ÉCOLE LA BONTÉ<small>ESPACE SCOLAIRE</small></span></a>
<nav><a href='/'>▦ Tableau de bord</a>{% if current_user.role=='admin' %}<a href='/eleves'>♙ Élèves</a><a href='/facultes'>▦ Facultés & filières</a><a href='/historique'>▤ Historique académique</a><a href='/affectations'>♧ Affectations enseignants</a><a href='/comptes'>♧ Comptes utilisateurs</a>{% endif %}<a href='/assistant'>✧ Assistant scolaire</a>
<a href='/notes'>▤ Notes & résultats</a>{% if current_user.role in ['admin','enseignant'] %}<a href='/presences'>◷ Présences</a>{% endif %}<a href='/messages'>✉ Messages</a><a href='/finances'>◈ Finances</a><a href='/horaire'>▦ Emploi du temps</a></nav>
<div class='side-bottom'><b>{{ current_user.nom }}</b><small>{{ current_user.role|capitalize }}</small><a href='/deconnexion'>↪ Déconnexion</a></div></aside>
<main class='main'><header><div><small class='kicker'>ÉCOLE LA BONTÉ · LUBUMBASHI</small><h1>{{ title }}</h1></div><span class='avatar'>{{ current_user.nom[:1] }}</span></header>
{% with alerts=get_flashed_messages(with_categories=true) %}{% for cat,msg in alerts %}<div class='alert {{ cat }}'>{{ msg }}</div>{% endfor %}{% endwith %}
{{ content|safe }}</main><nav class='bottom-nav'><a href='/'>Accueil</a>{% if current_user.role=='admin' %}<a href='/eleves'>Élèves</a>{% endif %}{% if current_user.role in ['admin','enseignant'] %}<a href='/presences'>Présences</a>{% endif %}<a href='/notes'>Notes</a><a href='/messages'>Messages</a><a href='/finances'>Finances</a></nav></div>
{% else %}{% with alerts=get_flashed_messages(with_categories=true) %}{% for cat,msg in alerts %}<div class='alert {{ cat }}'>{{ msg }}</div>{% endfor %}{% endwith %}{{ content|safe }}{% endif %}
<script src='/static/app.js'></script></body></html>
"""

def page(title, template, **context):
    content = render_template_string(template, **context)
    return render_template_string(BASE, title=title, content=content)

LOGIN = """
<div class='login-page'><form class='login-card' method='post'><div class='mark'>✦</div><small class='kicker'>BIENVENUE À</small><h1>École La Bonté</h1><p>Votre espace scolaire numérique.</p>
<label>Matricule ou adresse e-mail<input name='identifier' required autocomplete='username'></label>
<label>Mot de passe<input type='password' name='password' required autocomplete='current-password'></label>
<button class='btn primary wide'>Se connecter</button><a href='/creer-compte-eleve'>Créer un compte Élève – École La Bonté, Chemègue, Lubumbashi</a><small class='muted'>Élèves · Parents · Enseignants · Administration</small></form></div>
"""
DASH_ADMIN = """
<section class='hero'><div><small>VUE GÉNÉRALE</small><h2>Bonjour, {{ current_user.nom }} 👋</h2><p>Bienvenue dans votre espace de gestion.</p></div><span>✦</span></section>
<div class='stats'><article><small>Élèves inscrits</small><strong>{{ total }}</strong><em>Effectif total</em></article><article><small>Enseignants</small><strong>{{ enseignants }}</strong><em>Personnel enseignant</em></article><article><small>Taux de réussite</small><strong>{{ reussite }}%</strong><em>Moyenne au seuil de 10/20</em></article><article><small>Recettes encaissées · CDF</small><strong>{{ recettes_cdf }} CDF</strong><em>Paiements confirmés</em></article><article><small>Recettes encaissées · USD</small><strong>{{ recettes_usd }} USD</strong><em>Paiements confirmés</em></article><article><small>Paiements payés</small><strong>{{ payes }}/{{ nb_paiements }}</strong><em>Suivi des frais</em></article></div>
<section class='panel'><div class='panel-head'><div><h2>Dernières inscriptions</h2><p>Les dossiers récemment ajoutés</p></div><a class='btn outline' href='/eleves'>Tous les élèves</a></div>
<div class='table-wrap'><table><tr><th>Élève</th><th>Matricule</th><th>Classe</th><th>Promotion</th><th></th></tr>{% for s in recents %}<tr><td><img class='mini' src='/static/uploads/{{ s.photo }}'> {{ s.nom }}</td><td>{{ s.matricule }}</td><td>{{ s.classe }}</td><td>{{ s.promotion }}</td><td><a href='/eleves/{{ s.id }}'>Détails →</a></td></tr>{% else %}<tr><td colspan='5'>Aucune inscription pour le moment.</td></tr>{% endfor %}</table></div></section>
"""
DASH_TEACHER = """
<section class='hero'><div><small>ESPACE ENSEIGNANT</small><h2>Bonjour, {{ current_user.nom }}</h2><p>Gérez les notes et consultez les horaires de cours.</p></div><span>✦</span></section>
<div class='quick'><a href='/notes'>▤ <b>Saisir les notes</b><small>Évaluer les élèves</small></a><a href='/horaire'>▦ <b>Emploi du temps</b><small>Voir les horaires</small></a><a href='/messages'>✉ <b>Messages</b><small>Communiquer avec l'école</small></a></div>
<section class='panel'><div class='panel-head'><div><h2>Mes cours affectés</h2><p>{{ affectations|length }} affectation(s)</p></div></div><div class='table-wrap'><table><tr><th>Cours</th><th>Classe</th><th>Année</th><th>Volume (h)</th></tr>{% for a in affectations %}<tr><td>{{ a.cours }}</td><td>{{ a.classe }}</td><td>{{ a.annee_academique }}</td><td>{{ a.volume_horaire }}</td></tr>{% else %}<tr><td colspan='4'>Aucun cours ne vous a encore été affecté. Contactez l'administration.</td></tr>{% endfor %}</table></div></section>
"""
DASH_USER = """
<section class='hero'><div><small>MON ESPACE SCOLAIRE</small><h2>Bienvenue, {{ current_user.nom }}</h2><p>Retrouvez vos informations et vos résultats.</p></div><span>✦</span></section>
{% if student %}<section class='panel profile'><img src='/static/uploads/{{ student.photo }}'><div><small>MATRICULE {{ student.matricule }}</small><h2>{{ student.nom }}</h2><p>{{ student.filiere }} · {{ student.classe }} · {{ student.promotion }}</p><b>Moyenne : {{ student.moyenne }}/20</b><p>Absences enregistrées : <strong>{{ absences }}</strong></p></div></section>{% else %}<section class='panel'>Votre compte n'est pas encore lié à un dossier élève. Contactez l'administration.</section>{% endif %}
<div class='quick'><a href='/notes'>▤ <b>Mes notes</b><small>Voir mes résultats</small></a><a href='/messages'>✉ <b>Messages</b><small>Contacter l'école</small></a><a href='/finances'>◈ <b>Paiements</b><small>Suivre mes frais</small></a></div>
"""
STUDENTS = """
<section class='panel'><div class='panel-head'><div><h2>Liste des élèves</h2><p>{{ students|length }} dossier(s)</p></div><a class='btn primary' href='/eleves/nouveau'>＋ Ajouter un élève</a></div>
<form class='search'><input name='q' value='{{ q }}' placeholder='Rechercher par nom ou matricule'><button class='btn dark'>Rechercher</button></form>
<div class='table-wrap'><table><tr><th>Élève</th><th>Matricule</th><th>Faculté / Filière</th><th>Classe</th><th>Moyenne</th><th></th></tr>{% for s in students %}<tr><td><img class='mini' src='/static/uploads/{{ s.photo }}'> {{ s.nom }}</td><td><span class='pill'>{{ s.matricule }}</span></td><td>{{ s.faculte }}<small class='sub'>{{ s.filiere }}</small></td><td>{{ s.classe }}</td><td>{{ s.moyenne }}/20</td><td><a href='/eleves/{{ s.id }}'>Ouvrir →</a></td></tr>{% else %}<tr><td colspan='6'>Aucun élève trouvé.</td></tr>{% endfor %}</table></div></section>
"""
STUDENT_FORM = """
<section class='panel'><h2>{{ 'Modifier le dossier' if s else 'Nouvelle inscription' }}</h2><p>La photo est obligatoire à la création. Le matricule de 14 chiffres est saisi manuellement par la Direction.</p>
<form method='post' enctype='multipart/form-data' class='form-grid'>
<label class='photo'>Photo de profil {% if not s %}*{% endif %}<input type='file' name='photo' accept='.jpg,.jpeg,.png,.webp' {% if not s %}required{% endif %}><img id='preview' src='{{ ("/static/uploads/"+s.photo) if s else "" }}' {% if not s %}hidden{% endif %}></label>
<label>Nom complet *<input name='nom' required value='{{ s.nom if s else "" }}'></label>
<label>Matricule attribué par la Direction *<input name='matricule' required pattern='[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{6}' placeholder='2026-01-02-000001' value='{{ s.matricule if s else "" }}'></label>
<label>Année d'inscription *<input type='number' name='annee_inscription' required value='{{ s.annee_inscription if s else "" }}'></label>
<label>Code faculté *<input name='code_faculte' pattern='[0-9]{2}' maxlength='2' required value='{{ s.code_faculte if s else "" }}'></label>
<label>Code filière *<input name='code_filiere' pattern='[0-9]{2}' maxlength='2' required value='{{ s.code_filiere if s else "" }}'></label>
{% if faculties %}
<label>Faculté du catalogue *<select name='faculty_catalog_id' id='faculty_catalog_id' required><option value=''>Choisir une faculté</option>{% for f in faculties %}<option value='{{ f.id }}' data-code='{{ f.code }}' {% if s and s.faculte==f.nom %}selected{% endif %}>{{ f.code }} · {{ f.nom }}</option>{% endfor %}</select></label>
<label>Filière du catalogue *<select name='program_catalog_id' id='program_catalog_id' required><option value=''>Choisir une filière</option>{% for f in faculties %}{% for p in f.filieres %}<option value='{{ p.id }}' data-faculty='{{ f.id }}' data-code='{{ p.code }}' {% if s and s.filiere==p.nom and s.faculte==f.nom %}selected{% endif %}>{{ p.code }} · {{ p.nom }}</option>{% endfor %}{% endfor %}</select></label>
<script>
(function(){
 const faculty=document.getElementById('faculty_catalog_id');
 const program=document.getElementById('program_catalog_id');
 if(!faculty||!program)return;
 const options=Array.from(program.options);
 function filterPrograms(){
   const selected=faculty.value, previous=program.value;
   options.forEach(o=>{if(o.value)o.hidden=(o.dataset.faculty!==selected);});
   if(program.selectedOptions.length && program.selectedOptions[0].hidden)program.value='';
   if(!program.value && previous){const match=options.find(o=>o.value===previous&&o.dataset.faculty===selected);if(match)program.value=previous;}
 }
 faculty.addEventListener('change',filterPrograms);filterPrograms();
})();
</script>
{% else %}
<label>Faculté *<input name='faculte' required value='{{ s.faculte if s else "" }}'></label>
<label>Filière *<input name='filiere' required value='{{ s.filiere if s else "" }}'></label>
{% endif %}
<label>Promotion *<input name='promotion' required placeholder='Promotion 2026 / G1 / L1' value='{{ s.promotion if s else "" }}'></label>
<label>Nombre de cours<input type='number' min='0' name='nombre_cours' value='{{ s.nombre_cours if s else 0 }}'></label>
<label>Nombre de crédits<input type='number' min='0' name='credits' value='{{ s.credits if s else 0 }}'></label>
<label>Classe *<input name='classe' required value='{{ s.classe if s else "" }}'></label>
<div class='actions'><a class='btn outline' href='/eleves'>Annuler</a><button class='btn primary'>Enregistrer</button></div></form></section>
"""
DETAIL = """
<section class='panel'><div class='profile'><img src='/static/uploads/{{ s.photo }}'><div><small>MATRICULE {{ s.matricule }}</small><h2>{{ s.nom }}</h2><p>{{ s.faculte }} · {{ s.filiere }}</p><span class='pill'>{{ s.promotion }} · {{ s.classe }}</span></div><div class='average'><strong>{{ s.moyenne }}</strong><small>Moyenne / 20</small></div></div>
<div class='details'><div><small>Faculté</small><b>{{ s.faculte }}</b></div><div><small>Filière</small><b>{{ s.filiere }}</b></div><div><small>Promotion</small><b>{{ s.promotion }}</b></div><div><small>Classe</small><b>{{ s.classe }}</b></div><div><small>Nombre de cours</small><b>{{ s.nombre_cours }}</b></div><div><small>Crédits</small><b>{{ s.credits }}</b></div></div>
<h3>Notes de l'élève</h3><div class='table-wrap'><table><tr><th>Cours</th><th>Période</th><th>Note</th></tr>{% for n in s.notes %}<tr><td>{{ n.cours }}</td><td>{{ n.periode }}</td><td>{{ n.note }}/20</td></tr>{% else %}<tr><td colspan='3'>Aucune note saisie.</td></tr>{% endfor %}</table></div>
<div class='actions'><a class='btn primary' href='/eleves/{{ s.id }}/modifier'>Modifier</a><form method='post' action='/eleves/{{ s.id }}/supprimer' onsubmit="return confirm('Supprimer ce dossier ?')"><button class='btn danger'>Supprimer</button></form></div></section>
"""
GRADES = """
{% if admin %}<section class='panel'><h2>Ajouter une note</h2><form method='post' class='inline-form'><label>Élève<select name='student_id' required>{% for s in students %}<option value='{{ s.id }}'>{{ s.nom }} · {{ s.matricule }}</option>{% endfor %}</select></label><label>Cours<input name='cours' required></label><label>Note / 20<input type='number' name='note' min='0' max='20' step='.01' required></label><label>Période<input name='periode' value='Trimestre 1'></label><button class='btn primary'>Enregistrer</button></form></section>{% endif %}
<section class='panel'><h2>Résultats et notes</h2><div class='table-wrap'><table><tr><th>Élève</th><th>Cours</th><th>Période</th><th>Note</th></tr>{% for n in notes %}<tr><td>{{ n.eleve.nom }}</td><td>{{ n.cours }}</td><td>{{ n.periode }}</td><td><b>{{ n.note }}/20</b></td></tr>{% else %}<tr><td colspan='4'>Aucune note disponible.</td></tr>{% endfor %}</table></div></section>
"""
FINANCES = """
{% if admin %}<section class='panel'><h2>Enregistrer un paiement</h2><form method='post' class='inline-form'><label>Élève<select name='student_id' required>{% for s in students %}<option value='{{ s.id }}'>{{ s.nom }} · {{ s.matricule }}</option>{% endfor %}</select></label><label>Libellé<input name='libelle' required placeholder='Frais scolaires'></label><label>Montant<input type='number' name='montant' min='0' step='1' required></label><label>Devise<select name='devise' required><option value='CDF'>CDF — Franc congolais</option><option value='USD'>USD — Dollar américain</option></select></label><label>Statut<select name='statut'><option>Payé</option><option>En attente</option></select></label><button class='btn primary'>Ajouter</button></form></section>{% endif %}
<section class='panel'><h2>Suivi des paiements</h2><div class='table-wrap'><table><tr><th>Élève</th><th>Libellé</th><th>Montant</th><th>Devise</th><th>Statut</th></tr>{% for p in paiements %}<tr><td>{{ p.eleve.nom }}</td><td>{{ p.libelle }}</td><td>{{ "{:,.0f}".format(p.montant).replace(",", " ") }}</td><td>{{ p.devise }}</td><td><span class='status {{ "paid" if p.statut=="Payé" else "pending" }}'>{{ p.statut }}</span></td></tr>{% else %}<tr><td colspan='4'>Aucun paiement.</td></tr>{% endfor %}</table></div></section>
"""
MESSAGES = """
<section class='panel'><h2>Nouveau message</h2><form method='post' class='message-form'><label>Destinataire<select name='destinataire'><option>Tous</option><option>Administration</option><option>Enseignants</option><option>Parents</option><option>Élèves</option></select></label><label>Objet<input name='sujet' required></label><label>Message<textarea name='contenu' rows='4' required></textarea></label><button class='btn primary'>Envoyer</button></form></section>
<section class='panel'><h2>Fil de communication</h2>{% for m in messages %}<article class='message'><b>{{ m.sujet }}</b><small>{{ m.auteur.nom }} · {{ m.destinataire }} · {{ m.cree_le.strftime('%d/%m/%Y %H:%M') }}</small><p>{{ m.contenu }}</p></article>{% else %}<p>Aucun message.</p>{% endfor %}</section>
"""
SCHEDULE = """
{% if admin %}<section class='panel'><h2>Ajouter un cours</h2><form method='post' class='inline-form'><label>Classe<input name='classe' required></label><label>Jour<select name='jour'>{% for j in jours %}<option>{{ j }}</option>{% endfor %}</select></label><label>Début<input type='time' name='debut' required></label><label>Fin<input type='time' name='fin' required></label><label>Cours<input name='cours' required></label><label>Enseignant<input name='enseignant'></label><button class='btn primary'>Ajouter</button></form></section>{% endif %}
<section class='panel'><h2>Horaire des cours</h2><div class='table-wrap'><table><tr><th>Jour</th><th>Heure</th><th>Classe</th><th>Cours</th><th>Enseignant</th></tr>{% for c in cours %}<tr><td>{{ c.jour }}</td><td>{{ c.debut }}–{{ c.fin }}</td><td>{{ c.classe }}</td><td>{{ c.cours }}</td><td>{{ c.enseignant }}</td></tr>{% else %}<tr><td colspan='5'>Aucun cours programmé.</td></tr>{% endfor %}</table></div></section>
"""
ACCOUNTS = """
<section class='panel'><h2>Créer un compte utilisateur</h2><p>Les comptes sont créés par l'administration. Pour un compte élève, liez-le à son dossier.</p>
<form method='post' class='inline-form'><label>Nom complet<input name='nom' required></label><label>E-mail<input name='email' type='email' required></label><label>Mot de passe provisoire<input name='password' type='password' minlength='10' required></label><label>Rôle<select name='role'><option value='eleve'>Élève</option><option value='parent'>Parent</option><option value='enseignant'>Enseignant</option><option value='admin'>Administrateur</option></select></label><label>Dossier élève (facultatif)<select name='student_id'><option value=''>Non lié</option>{% for s in students %}<option value='{{ s.id }}'>{{ s.nom }} · {{ s.matricule }}</option>{% endfor %}</select></label><button class='btn primary'>Créer le compte</button></form></section>
<section class='panel'><h2>Comptes existants</h2><div class='table-wrap'><table><tr><th>Nom</th><th>E-mail</th><th>Rôle</th></tr>{% for u in users %}<tr><td>{{ u.nom }}</td><td>{{ u.email }}</td><td>{{ u.role }}</td></tr>{% endfor %}</table></div></section>
"""

@app.route("/")
@login_required
def dashboard():
    if current_user.role == "enseignant":
        return page("Espace enseignant", DASH_TEACHER, affectations=TeacherAssignment.query.filter_by(teacher_id=current_user.id).order_by(TeacherAssignment.annee_academique.desc(), TeacherAssignment.classe).all())
    if current_user.role == "admin":
        eleves_avec_notes = [s for s in Student.query.all() if s.notes]
        seuil = float(os.getenv("PASS_MARK", "10"))
        reussite = round(100 * sum(1 for s in eleves_avec_notes if s.moyenne >= seuil) / len(eleves_avec_notes), 1) if eleves_avec_notes else 0
        return page("Tableau de bord", DASH_ADMIN, reussite=reussite, total=Student.query.count(),
            enseignants=User.query.filter_by(role="enseignant").count(),
            recettes_cdf=db.session.query(db.func.coalesce(db.func.sum(Payment.montant),0)).filter_by(statut="Payé",devise="CDF").scalar(),
            recettes_usd=db.session.query(db.func.coalesce(db.func.sum(Payment.montant),0)).filter_by(statut="Payé",devise="USD").scalar(),
            payes=Payment.query.filter_by(statut="Payé").count(), nb_paiements=Payment.query.count(),
            recents=Student.query.order_by(Student.cree_le.desc()).limit(6).all())
    student = db.session.get(Student, current_user.student_id) if current_user.student_id else None
    absences = Attendance.query.filter_by(student_id=student.id, statut="Absent").count() if student else 0
    return page("Mon espace", DASH_USER, student=student, absences=absences)

@app.route("/connexion", methods=["GET","POST"])
def connexion():
    if current_user.is_authenticated: return redirect(url_for("dashboard"))
    if request.method == "POST":
        identifier=request.form.get("identifier","").strip()
        user = User.query.filter_by(email=identifier.lower()).first()
        if not user and matricule_valide(identifier):
            student=Student.query.filter_by(matricule=identifier).first()
            user=User.query.filter_by(student_id=student.id).first() if student else None
        if user and user.verify(request.form.get("password","")):
            login_user(user); return redirect(url_for("dashboard"))
        flash("Adresse e-mail ou mot de passe incorrect.", "error")
    return page("Connexion", LOGIN)


@app.route("/creer-compte-eleve", methods=["GET","POST"])
def creer_compte_eleve():
    template="""<div class='login-page'><form class='login-card' method='post'><div class='mark'>✦</div><h1>Créer mon compte élève</h1><p>Utilisez le matricule remis par la Direction et choisissez votre mot de passe.</p><label>Matricule officiel<input name='matricule' required pattern='[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{6}' placeholder='2026-01-02-000001'></label><label>Mot de passe personnel<input type='password' name='password' minlength='10' required></label><label>Confirmer le mot de passe<input type='password' name='confirm' minlength='10' required></label><button class='btn primary wide'>Créer mon compte</button><a href='/connexion'>Retour</a></form></div>"""
    if request.method=="POST":
        matricule=request.form.get("matricule","").strip()
        student=Student.query.filter_by(matricule=matricule).first()
        if not matricule_valide(matricule) or not student:
            flash("Matricule non reconnu. Vérifiez auprès de la Direction.", "error")
        elif User.query.filter_by(student_id=student.id).first():
            flash("Un compte existe déjà pour ce matricule.", "error")
        elif len(request.form.get("password",""))<10 or request.form.get("password")!=request.form.get("confirm"):
            flash("Les mots de passe doivent être identiques et contenir au moins 10 caractères.", "error")
        else:
            u=User(nom=student.nom,email=matricule.replace("-","")+"@eleves.shemec.local",role="eleve",student_id=student.id)
            u.set_password(request.form["password"]); db.session.add(u); db.session.commit()
            flash("Compte créé. Connectez-vous avec votre matricule et votre mot de passe.", "success")
            return redirect(url_for("connexion"))
    return page("Créer un compte élève",template)

@app.route("/deconnexion")
@login_required
def deconnexion():
    logout_user(); return redirect(url_for("connexion"))

@app.route("/eleves")
@admin_only
def eleves():
    q = request.args.get("q","").strip()
    query = Student.query
    if q: query = query.filter(db.or_(Student.nom.ilike(f"%{q}%"), Student.matricule.ilike(f"%{q}%")))
    return page("Gestion des élèves", STUDENTS, students=query.order_by(Student.cree_le.desc()).all(), q=q)

@app.route("/eleves/nouveau", methods=["GET","POST"])
@admin_only
def eleve_nouveau():
    if request.method == "POST":
        photo = request.files.get("photo")
        if not photo or not photo.filename:
            flash("La photo de profil est obligatoire.", "error")
            return page("Nouvelle inscription", STUDENT_FORM, s=None, matricule="", faculties=FacultyCatalog.query.order_by(FacultyCatalog.code).all())
        ext = photo.filename.rsplit(".",1)[-1].lower()
        if ext not in ALLOWED:
            flash("Format accepté : JPG, PNG ou WEBP.", "error")
            return page("Nouvelle inscription", STUDENT_FORM, s=None, matricule="", faculties=FacultyCatalog.query.order_by(FacultyCatalog.code).all())
        filename = datetime.utcnow().strftime("%Y%m%d%H%M%S%f") + "_" + secure_filename(photo.filename)
        photo.save(UPLOADS / filename)
        matricule=request.form.get("matricule","").strip()
        annee=int(request.form["annee_inscription"]); cf=request.form["code_faculte"].strip(); cfi=request.form["code_filiere"].strip()
        if not matricule_valide(matricule) or Student.query.filter_by(matricule=matricule).first() or matricule.split("-")[:3] != [str(annee),cf,cfi]:
            (UPLOADS / filename).unlink(missing_ok=True)
            flash("Matricule invalide, déjà utilisé ou incohérent avec l'année, la faculté et la filière.", "error")
            return page("Nouvelle inscription", STUDENT_FORM, s=None, matricule="", faculties=FacultyCatalog.query.order_by(FacultyCatalog.code).all())
        faculty_id=request.form.get("faculty_catalog_id", "").strip()
        program_id=request.form.get("program_catalog_id", "").strip()
        if faculty_id or program_id:
            faculty=db.session.get(FacultyCatalog, int(faculty_id)) if faculty_id.isdigit() else None
            program=db.session.get(ProgramCatalog, int(program_id)) if program_id.isdigit() else None
            if not faculty or not program or program.faculty_id != faculty.id or [faculty.code, program.code] != [cf, cfi]:
                (UPLOADS / filename).unlink(missing_ok=True)
                flash("La faculté, la filière et leurs codes doivent correspondre au matricule.", "error")
                return page("Nouvelle inscription", STUDENT_FORM, s=None, matricule="", faculties=FacultyCatalog.query.order_by(FacultyCatalog.code).all())
            faculte_name, filiere_name = faculty.nom, program.nom
        else:
            faculte_name=request.form.get("faculte","").strip()
            filiere_name=request.form.get("filiere","").strip()
        s = Student(matricule=matricule, annee_inscription=annee, code_faculte=cf, code_filiere=cfi, nom=request.form["nom"].strip(), photo=filename,
            faculte=faculte_name, filiere=filiere_name,
            promotion=request.form["promotion"].strip(), classe=request.form["classe"].strip(),
            nombre_cours=int(request.form.get("nombre_cours") or 0), credits=int(request.form.get("credits") or 0))
        db.session.add(s); db.session.commit()
        flash("Inscription enregistrée : " + s.matricule, "success")
        return redirect(url_for("eleve_detail", sid=s.id))
    return page("Nouvelle inscription", STUDENT_FORM, s=None, matricule="", faculties=FacultyCatalog.query.order_by(FacultyCatalog.code).all())

@app.route("/eleves/<int:sid>")
@admin_only
def eleve_detail(sid):
    return page("Dossier de l'élève", DETAIL, s=db.get_or_404(Student,sid))

@app.route("/eleves/<int:sid>/modifier", methods=["GET","POST"])
@admin_only
def eleve_modifier(sid):
    s = db.get_or_404(Student,sid)
    if request.method == "POST":
        for field in ("nom","promotion","classe"):
            setattr(s, field, request.form[field].strip())
        faculty_id=request.form.get("faculty_catalog_id", "").strip()
        program_id=request.form.get("program_catalog_id", "").strip()
        if faculty_id or program_id:
            faculty=db.session.get(FacultyCatalog, int(faculty_id)) if faculty_id.isdigit() else None
            program=db.session.get(ProgramCatalog, int(program_id)) if program_id.isdigit() else None
            if not faculty or not program or program.faculty_id != faculty.id or [faculty.code, program.code] != [s.code_faculte, s.code_filiere]:
                flash("La faculté et la filière choisies doivent correspondre aux codes du matricule. Corrigez le matricule auprès de la Direction si nécessaire.", "error")
                return page("Modifier l'élève", STUDENT_FORM, s=s, matricule=s.matricule, faculties=FacultyCatalog.query.order_by(FacultyCatalog.code).all())
            s.faculte, s.filiere = faculty.nom, program.nom
        else:
            s.faculte=request.form.get("faculte",s.faculte).strip()
            s.filiere=request.form.get("filiere",s.filiere).strip()
        s.nombre_cours=int(request.form.get("nombre_cours") or 0); s.credits=int(request.form.get("credits") or 0)
        photo=request.files.get("photo")
        if photo and photo.filename:
            ext=photo.filename.rsplit(".",1)[-1].lower()
            if ext not in ALLOWED: flash("Format photo invalide.","error"); return page("Modifier l'élève",STUDENT_FORM,s=s,matricule=s.matricule,faculties=FacultyCatalog.query.order_by(FacultyCatalog.code).all())
            filename=datetime.utcnow().strftime("%Y%m%d%H%M%S%f")+"_"+secure_filename(photo.filename)
            photo.save(UPLOADS/filename); s.photo=filename
        db.session.commit(); flash("Dossier modifié.","success"); return redirect(url_for("eleve_detail",sid=s.id))
    return page("Modifier l'élève",STUDENT_FORM,s=s,matricule=s.matricule,faculties=FacultyCatalog.query.order_by(FacultyCatalog.code).all())

@app.route("/eleves/<int:sid>/supprimer", methods=["POST"])
@admin_only
def eleve_supprimer(sid):
    s=db.get_or_404(Student,sid); User.query.filter_by(student_id=sid).update({User.student_id: None}); db.session.delete(s); db.session.commit()
    flash("Dossier supprimé.","success"); return redirect(url_for("eleves"))

@app.route("/notes", methods=["GET","POST"])
@login_required
def notes():
    admin=current_user.role in ("admin","enseignant")
    if request.method=="POST":
        if not admin: abort(403)
        n=Grade(student_id=int(request.form["student_id"]),cours=request.form["cours"].strip(),
                note=float(request.form["note"]),periode=request.form.get("periode","Trimestre 1"))
        if not 0 <= n.note <= 20: abort(400)
        db.session.add(n); db.session.commit(); flash("Note enregistrée.","success"); return redirect(url_for("notes"))
    query=Grade.query.join(Student)
    if not admin:
        if not current_user.student_id: return page("Notes",GRADES,admin=False,notes=[])
        query=query.filter(Grade.student_id==current_user.student_id)
    return page("Notes & résultats",GRADES,admin=admin,notes=query.order_by(Grade.id.desc()).all(),
                students=Student.query.order_by(Student.nom).all() if admin else [])

@app.route("/finances", methods=["GET","POST"])
@login_required
def finances():
    admin=current_user.role=="admin"
    if request.method=="POST":
        if not admin: abort(403)
        devise=request.form.get("devise", "CDF").upper()
        if devise not in ("CDF", "USD"): abort(400)
        p=Payment(student_id=int(request.form["student_id"]),libelle=request.form["libelle"].strip(),
                  montant=int(request.form["montant"]),devise=devise,statut=request.form["statut"])
        db.session.add(p); db.session.commit(); flash("Paiement enregistré.","success"); return redirect(url_for("finances"))
    query=Payment.query.join(Student)
    if not admin:
        if not current_user.student_id: return page("Finances",FINANCES,admin=False,paiements=[])
        query=query.filter(Payment.student_id==current_user.student_id)
    return page("Finances scolaires",FINANCES,admin=admin,paiements=query.order_by(Payment.id.desc()).all(),
                students=Student.query.order_by(Student.nom).all() if admin else [])

@app.route("/messages", methods=["GET","POST"])
@login_required
def messages():
    if request.method=="POST":
        m=Message(user_id=current_user.id,destinataire=request.form["destinataire"],
                  sujet=request.form["sujet"].strip(),contenu=request.form["contenu"].strip())
        db.session.add(m); db.session.commit(); flash("Message envoyé.","success"); return redirect(url_for("messages"))
    if current_user.role == "admin":
        visibles = Message.query.order_by(Message.cree_le.desc()).all()
    else:
        destinataire = {"enseignant":"Enseignants", "parent":"Parents", "eleve":"Élèves"}.get(current_user.role, "Tous")
        visibles = Message.query.filter(db.or_(Message.user_id == current_user.id,
            Message.destinataire.in_(["Tous", destinataire]))).order_by(Message.cree_le.desc()).all()
    return page("Messages",MESSAGES,messages=visibles)

@app.route("/horaire", methods=["GET","POST"])
@login_required
def horaire():
    admin=current_user.role=="admin"
    if request.method=="POST":
        if not admin: abort(403)
        c=CourseSlot(classe=request.form["classe"].strip(),jour=request.form["jour"],debut=request.form["debut"],
            fin=request.form["fin"],cours=request.form["cours"].strip(),enseignant=request.form.get("enseignant","").strip())
        db.session.add(c); db.session.commit(); flash("Cours ajouté.","success"); return redirect(url_for("horaire"))
    return page("Emploi du temps",SCHEDULE,admin=admin,cours=CourseSlot.query.order_by(CourseSlot.jour,CourseSlot.debut).all(),
                jours=["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi"])


@app.route("/presences", methods=["GET","POST"])
@login_required
def presences():
    if current_user.role not in ("admin", "enseignant"): abort(403)

    if current_user.role not in ("admin","enseignant"): abort(403)
    if request.method == "POST":
        record = Attendance(student_id=int(request.form["student_id"]),
            jour=datetime.strptime(request.form["jour"], "%Y-%m-%d").date(),
            statut=request.form["statut"], motif=request.form.get("motif","").strip())
        db.session.add(record); db.session.commit()
        flash("Présence enregistrée.", "success")
        return redirect(url_for("presences"))
    students = Student.query.order_by(Student.nom).all()
    records = Attendance.query.order_by(Attendance.jour.desc(), Attendance.id.desc()).limit(150).all()
    template = """
    <section class='panel'><h2>Enregistrer une présence ou une absence</h2>
    <form method='post' class='inline-form'><label>Élève<select name='student_id' required>{% for s in students %}<option value='{{ s.id }}'>{{ s.nom }} · {{ s.matricule }}</option>{% endfor %}</select></label>
    <label>Date<input type='date' name='jour' value='{{ today }}' required></label><label>Statut<select name='statut'><option>Présent</option><option>Absent</option><option>Retard</option></select></label><label>Motif<input name='motif'></label><button class='btn primary'>Enregistrer</button></form></section>
    <section class='panel'><h2>Registre des présences</h2><div class='table-wrap'><table><tr><th>Date</th><th>Élève</th><th>Matricule</th><th>Statut</th><th>Motif</th></tr>{% for r in records %}<tr><td>{{ r.jour.strftime('%d/%m/%Y') }}</td><td>{{ r.eleve.nom }}</td><td>{{ r.eleve.matricule }}</td><td>{{ r.statut }}</td><td>{{ r.motif }}</td></tr>{% else %}<tr><td colspan='5'>Aucun relevé.</td></tr>{% endfor %}</table></div></section>
    """
    return page("Présences & absences", template, students=students, records=records, today=date.today().isoformat())

@app.route("/assistant", methods=["GET","POST"])
@login_required
def assistant():
    template="""<section class='panel'><h2>Assistant scolaire — recherche dans les dossiers</h2><p>Recherchez un matricule ou un nom. L'assistant interroge la base de données selon vos autorisations.</p><form method='post' class='search'><input name='q' placeholder='Matricule officiel ou nom' required><button class='btn primary'>Rechercher</button></form>{% if s %}<div class='profile'><img src='/static/uploads/{{ s.photo }}'><div><b>{{ s.nom }}</b><p>Matricule : {{ s.matricule }}</p><p>{{ s.faculte }} · {{ s.filiere }} · {{ s.promotion }}</p><b>Moyenne : {{ s.moyenne }}/20</b></div></div><h3>Parcours annuel</h3><div class='table-wrap'><table><tr><th>Année</th><th>Promotion</th><th>Faculté / Filière</th><th>Cours</th><th>Crédits</th><th>Note</th></tr>{% for h in s.historique %}<tr><td>{{ h.annee_academique }}</td><td>{{ h.promotion }}</td><td>{{ h.faculte }} / {{ h.filiere }}</td><td>{{ h.cours }}</td><td>{{ h.credits }}</td><td>{{ h.note if h.note is not none else h.decision }}</td></tr>{% else %}<tr><td colspan='6'>Aucun historique annuel archivé pour ce dossier.</td></tr>{% endfor %}</table></div>{% elif q %}<p>Aucun dossier correspondant.</p>{% endif %}</section>"""
    q=request.form.get("q","").strip() if request.method=="POST" else ""
    student=None
    if q:
        if current_user.role in ("admin","enseignant"):
            student=Student.query.filter(db.or_(Student.matricule==q,Student.nom.ilike("%"+q+"%"))).first()
        elif current_user.student_id:
            own=db.session.get(Student,current_user.student_id)
            if own and (q==own.matricule or q.lower() in own.nom.lower()): student=own
    return page("Assistant scolaire",template,s=student,q=q)

@app.route("/comptes", methods=["GET","POST"])
@admin_only
def comptes():
    if request.method=="POST":
        email=request.form["email"].strip().lower()
        if User.query.filter_by(email=email).first():
            flash("Cette adresse e-mail existe déjà.","error")
        else:
            u=User(nom=request.form["nom"].strip(),email=email,role=request.form["role"])
            u.set_password(request.form["password"])
            sid=request.form.get("student_id")
            u.student_id=int(sid) if sid else None
            db.session.add(u); db.session.commit(); flash("Compte créé.","success")
        return redirect(url_for("comptes"))
    return page("Comptes utilisateurs",ACCOUNTS,users=User.query.order_by(User.nom).all(),
                students=Student.query.order_by(Student.nom).all())



@app.route("/affectations", methods=["GET", "POST"])
@admin_only
def affectations():
    if request.method == "POST":
        try:
            teacher_id = int(request.form.get("teacher_id", ""))
            volume = int(request.form.get("volume_horaire") or 0)
        except (ValueError, TypeError):
            flash("Sélectionnez un enseignant et un volume horaire valide.", "error")
            return redirect(url_for("affectations"))
        teacher = db.session.get(User, teacher_id)
        cours = request.form.get("cours", "").strip()
        classe = request.form.get("classe", "").strip()
        annee = request.form.get("annee_academique", "").strip()
        if not teacher or teacher.role != "enseignant" or not all([cours, classe, annee]) or volume < 0:
            flash("Vérifiez l'enseignant, le cours, la classe, l'année et le volume horaire.", "error")
        elif TeacherAssignment.query.filter_by(teacher_id=teacher.id, cours=cours, classe=classe, annee_academique=annee).first():
            flash("Cette affectation existe déjà pour cet enseignant.", "error")
        else:
            db.session.add(TeacherAssignment(teacher_id=teacher.id, cours=cours, classe=classe,
                annee_academique=annee, volume_horaire=volume))
            db.session.commit()
            flash("Cours affecté à l'enseignant avec succès.", "success")
        return redirect(url_for("affectations"))
    template = """
    <section class='panel'><h2>Affecter un cours</h2>
    <form method='post' class='form-grid'>
      <label>Enseignant *<select name='teacher_id' required>{% for t in teachers %}<option value='{{ t.id }}'>{{ t.nom }} · {{ t.email }}</option>{% endfor %}</select></label>
      <label>Nom du cours *<input name='cours' required placeholder='Mathématiques'></label>
      <label>Classe *<input name='classe' required placeholder='G1 Informatique'></label>
      <label>Année académique *<input name='annee_academique' required value='2026-2027'></label>
      <label>Volume horaire (heures)<input type='number' min='0' name='volume_horaire' value='0'></label>
      <button class='btn primary' {% if not teachers %}disabled{% endif %}>Enregistrer l'affectation</button>
    </form>{% if not teachers %}<p>Créez d'abord un compte avec le rôle « Enseignant » dans Comptes utilisateurs.</p>{% endif %}</section>
    <section class='panel'><h2>Affectations enregistrées</h2><div class='table-wrap'><table>
    <tr><th>Enseignant</th><th>Cours</th><th>Classe</th><th>Année</th><th>Volume (h)</th></tr>
    {% for a in assignments %}<tr><td>{{ a.enseignant.nom }}</td><td>{{ a.cours }}</td><td>{{ a.classe }}</td><td>{{ a.annee_academique }}</td><td>{{ a.volume_horaire }}</td></tr>
    {% else %}<tr><td colspan='5'>Aucune affectation enregistrée.</td></tr>{% endfor %}</table></div></section>
    """
    return page("Affectations enseignants", template,
        teachers=User.query.filter_by(role="enseignant").order_by(User.nom).all(),
        assignments=TeacherAssignment.query.order_by(TeacherAssignment.annee_academique.desc(), TeacherAssignment.classe).all())


@app.route("/facultes", methods=["GET", "POST"])
@admin_only
def facultes():
    if request.method == "POST":
        action = request.form.get("action")
        code = request.form.get("code", "").strip()
        nom = request.form.get("nom", "").strip()
        if not re.fullmatch(r"\\d{2}", code) or not nom:
            flash("Le code doit contenir exactement deux chiffres et le nom est obligatoire.", "error")
        elif action == "faculty":
            if FacultyCatalog.query.filter(db.or_(FacultyCatalog.code == code, FacultyCatalog.nom.ilike(nom))).first():
                flash("Cette faculté ou ce code existe déjà.", "error")
            else:
                db.session.add(FacultyCatalog(code=code, nom=nom))
                db.session.commit()
                flash("Faculté ajoutée au catalogue.", "success")
        elif action == "program":
            try:
                faculty_id = int(request.form.get("faculty_id", ""))
            except ValueError:
                faculty_id = 0
            faculty = db.session.get(FacultyCatalog, faculty_id)
            if not faculty:
                flash("Sélectionnez une faculté valide.", "error")
            elif ProgramCatalog.query.filter_by(faculty_id=faculty.id).filter(db.or_(
                    ProgramCatalog.code == code, ProgramCatalog.nom.ilike(nom))).first():
                flash("Cette filière ou ce code existe déjà dans cette faculté.", "error")
            else:
                db.session.add(ProgramCatalog(code=code, nom=nom, faculty_id=faculty.id))
                db.session.commit()
                flash("Filière ajoutée au catalogue.", "success")
        else:
            flash("Type d'enregistrement inconnu.", "error")
        return redirect(url_for("facultes"))
    template = """
    <section class='panel'><h2>Ajouter une faculté</h2>
    <form method='post' class='inline-form'><input type='hidden' name='action' value='faculty'>
      <label>Code (2 chiffres)<input name='code' pattern='[0-9]{2}' maxlength='2' required placeholder='01'></label>
      <label>Nom de la faculté<input name='nom' required placeholder='Sciences informatiques'></label>
      <button class='btn primary'>Ajouter la faculté</button>
    </form></section>
    <section class='panel'><h2>Ajouter une filière</h2>
    <form method='post' class='inline-form'><input type='hidden' name='action' value='program'>
      <label>Faculté<select name='faculty_id' required>{% for f in faculties %}<option value='{{ f.id }}'>{{ f.code }} · {{ f.nom }}</option>{% endfor %}</select></label>
      <label>Code filière (2 chiffres)<input name='code' pattern='[0-9]{2}' maxlength='2' required placeholder='01'></label>
      <label>Nom de la filière<input name='nom' required placeholder='Réseaux informatiques'></label>
      <button class='btn primary' {% if not faculties %}disabled{% endif %}>Ajouter la filière</button>
    </form>{% if not faculties %}<p>Créez d'abord une faculté pour pouvoir y rattacher une filière.</p>{% endif %}</section>
    <section class='panel'><h2>Catalogue des facultés et filières</h2>
    {% for f in faculties %}<div class='panel-head'><div><h3>{{ f.code }} · {{ f.nom }}</h3><p>{{ f.filieres|length }} filière(s)</p></div></div>
      <div class='table-wrap'><table><tr><th>Code</th><th>Filière</th></tr>
      {% for p in f.filieres|sort(attribute='code') %}<tr><td>{{ p.code }}</td><td>{{ p.nom }}</td></tr>
      {% else %}<tr><td colspan='2'>Aucune filière enregistrée.</td></tr>{% endfor %}</table></div>
    {% else %}<p>Aucune faculté enregistrée.</p>{% endfor %}
    </section>
    """
    return page("Facultés & filières", template,
        faculties=FacultyCatalog.query.order_by(FacultyCatalog.code).all())

@app.route("/historique", methods=["GET","POST"])
@admin_only
def historique():
    if request.method == "POST":
        try:
            student_id = int(request.form["student_id"])
            credits = int(request.form.get("credits") or 0)
            note_raw = request.form.get("note", "").strip()
            note = float(note_raw) if note_raw else None
        except (ValueError, TypeError):
            flash("Vérifiez l'élève, les crédits et la note.", "error")
            return redirect(url_for("historique"))
        student = db.session.get(Student, student_id)
        annee = request.form.get("annee_academique", "").strip()
        promotion = request.form.get("promotion", "").strip()
        faculte = request.form.get("faculte", "").strip()
        filiere = request.form.get("filiere", "").strip()
        cours = request.form.get("cours", "").strip()
        decision = request.form.get("decision", "").strip()
        if not student or not all([annee, promotion, faculte, filiere, cours]) or credits < 0 or (note is not None and not 0 <= note <= 20):
            flash("Données invalides. La note doit être comprise entre 0 et 20.", "error")
            return redirect(url_for("historique"))
        record = StudentHistory(student_id=student.id, annee_academique=annee,
            promotion=promotion, faculte=faculte, filiere=filiere, cours=cours,
            credits=credits, note=note, decision=decision)
        db.session.add(record)
        db.session.commit()
        flash("Ligne d'historique académique enregistrée.", "success")
        return redirect(url_for("historique"))
    template = """
    <section class='panel'><h2>Ajouter une archive académique</h2>
    <p>Enregistrez le parcours annuel d'un élève : année, promotion, cours, crédits, note et décision.</p>
    <form method='post' class='form-grid'>
      <label>Élève *<select name='student_id' required>{% for s in students %}<option value='{{ s.id }}'>{{ s.nom }} · {{ s.matricule }}</option>{% endfor %}</select></label>
      <label>Année académique *<input name='annee_academique' required placeholder='2026-2027'></label>
      <label>Promotion *<input name='promotion' required placeholder='G1 / L1 / Promotion'></label>
      <label>Faculté *<input name='faculte' required></label>
      <label>Filière *<input name='filiere' required></label>
      <label>Cours *<input name='cours' required></label>
      <label>Crédits<input type='number' name='credits' min='0' value='0'></label>
      <label>Note / 20<input type='number' name='note' min='0' max='20' step='.01'></label>
      <label>Décision<input name='decision' placeholder='Admis, Ajourné…'></label>
      <div class='actions'><button class='btn primary'>Enregistrer l'archive</button></div>
    </form></section>
    <section class='panel'><h2>Archives enregistrées</h2>
    <div class='table-wrap'><table><tr><th>Élève</th><th>Année</th><th>Promotion</th><th>Faculté / Filière</th><th>Cours</th><th>Crédits</th><th>Note</th><th>Décision</th></tr>
    {% for h in records %}<tr><td>{{ h.student.nom }}</td><td>{{ h.annee_academique }}</td><td>{{ h.promotion }}</td><td>{{ h.faculte }} / {{ h.filiere }}</td><td>{{ h.cours }}</td><td>{{ h.credits }}</td><td>{{ h.note if h.note is not none else '—' }}</td><td>{{ h.decision or '—' }}</td></tr>
    {% else %}<tr><td colspan='8'>Aucune archive enregistrée.</td></tr>{% endfor %}</table></div></section>
    """
    return page("Historique académique", template,
        students=Student.query.order_by(Student.nom).all(),
        records=StudentHistory.query.join(Student).order_by(StudentHistory.annee_academique.desc(), Student.nom).all())

@app.route("/manifest.json")
def manifest(): return send_from_directory(ROOT/"static","manifest.json")

@app.errorhandler(403)
def forbidden(_): return page("Accès refusé","<section class='panel'><h2>Accès réservé à l'administration.</h2><a href='/'>Retour</a></section>"),403

@app.errorhandler(404)
def not_found(_): return page("Introuvable","<section class='panel'><h2>Cette page n'existe pas.</h2><a href='/'>Retour</a></section>"),404

with app.app_context():
    db.create_all()
    from sqlalchemy import inspect
    insp=inspect(db.engine)
    for table, columns in {
        "student": {"annee_inscription":"INTEGER","code_faculte":"VARCHAR(2)","code_filiere":"VARCHAR(2)"},
        "grade": {"annee_academique":"VARCHAR(20) DEFAULT '2026-2027'","promotion":"VARCHAR(80) DEFAULT ''"},
        "payment": {"devise":"VARCHAR(3) NOT NULL DEFAULT 'CDF'"}
    }.items():
        existing={col["name"] for col in insp.get_columns(table)}
        for col, definition in columns.items():
            if col not in existing:
                with db.engine.begin() as conn:
                    conn.exec_driver_sql("ALTER TABLE " + table + " ADD COLUMN " + col + " " + definition)
    if not User.query.filter_by(email="admin@shemec.cd").first():
        admin=User(nom="Administrateur Shemec",email="admin@shemec.cd",role="admin")
        admin.set_password(os.getenv("ADMIN_PASSWORD","Shemec2026!"))
        db.session.add(admin); db.session.commit()

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)),debug=os.getenv("FLASK_DEBUG")=="1")
