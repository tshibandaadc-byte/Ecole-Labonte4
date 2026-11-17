import os
from datetime import datetime, date
import re
from functools import wraps
from pathlib import Path

from flask import Flask, request, redirect, url_for, flash, send_from_directory, send_file, render_template_string, abort
from io import BytesIO
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

parent_student = db.Table(
    "parent_student",
    db.Column("parent_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("student_id", db.Integer, db.ForeignKey("student.id"), primary_key=True)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(140), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="eleve")
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=True)
    enfants = db.relationship("Student", secondary=parent_student,
        backref=db.backref("parents", lazy="select"), lazy="select")
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


class SchoolFee(db.Model):
    __tablename__ = "school_fee"
    id = db.Column(db.Integer, primary_key=True)
    classe = db.Column(db.String(80), nullable=False)
    annee_academique = db.Column(db.String(20), nullable=False)
    libelle = db.Column(db.String(140), nullable=False)
    montant = db.Column(db.Integer, nullable=False)
    devise = db.Column(db.String(3), nullable=False, default="CDF")
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    versements = db.relationship("FeePayment", cascade="all,delete-orphan", backref="frais")
    __table_args__ = (db.UniqueConstraint("classe", "annee_academique", "libelle", "devise",
                                           name="uq_school_fee_class_year_label_currency"),)


class FeePayment(db.Model):
    __tablename__ = "fee_payment"
    id = db.Column(db.Integer, primary_key=True)
    fee_id = db.Column(db.Integer, db.ForeignKey("school_fee.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    montant = db.Column(db.Integer, nullable=False)
    date_paiement = db.Column(db.Date, nullable=False, default=date.today)
    reference = db.Column(db.String(80), nullable=True)
    eleve = db.relationship("Student", backref=db.backref("versements_frais", lazy=True))


class AdmissionApplication(db.Model):
    __tablename__ = "admission_application"
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(160), nullable=False)
    photo = db.Column(db.String(255), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty_catalog.id"), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey("program_catalog.id"), nullable=False)
    classe = db.Column(db.String(80), nullable=False)
    promotion = db.Column(db.String(80), nullable=False)
    annee_academique = db.Column(db.String(20), nullable=False)
    telephone_parent = db.Column(db.String(40), nullable=True)
    statut = db.Column(db.String(20), nullable=False, default="En attente")
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=True)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    faculty = db.relationship("FacultyCatalog")
    program = db.relationship("ProgramCatalog")
    student = db.relationship("Student")


class Enrollment(db.Model):
    __tablename__ = "enrollment"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    annee_academique = db.Column(db.String(20), nullable=False)
    promotion = db.Column(db.String(80), nullable=False)
    classe = db.Column(db.String(80), nullable=False)
    statut = db.Column(db.String(20), nullable=False, default="Réinscrit")
    date_inscription = db.Column(db.Date, nullable=False, default=date.today)
    student = db.relationship("Student", backref=db.backref("inscriptions_annuelles", lazy=True))
    __table_args__ = (db.UniqueConstraint("student_id", "annee_academique",
                                           name="uq_enrollment_student_year"),)

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

class Personnel(db.Model):
    __tablename__ = "personnel"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=True)
    nom = db.Column(db.String(160), nullable=False)
    fonction = db.Column(db.String(120), nullable=False)
    telephone = db.Column(db.String(40), nullable=True)
    email = db.Column(db.String(180), nullable=True)
    statut = db.Column(db.String(20), nullable=False, default="Actif")
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    compte = db.relationship("User", backref=db.backref("fiche_personnel", uselist=False))
    contrats = db.relationship("StaffContract", cascade="all,delete-orphan", backref="personnel")
    avances = db.relationship("StaffAdvance", cascade="all,delete-orphan", backref="personnel")
    paies = db.relationship("PayrollRecord", cascade="all,delete-orphan", backref="personnel")


class StaffContract(db.Model):
    __tablename__ = "staff_contract"
    id = db.Column(db.Integer, primary_key=True)
    personnel_id = db.Column(db.Integer, db.ForeignKey("personnel.id"), nullable=False, index=True)
    type_contrat = db.Column(db.String(60), nullable=False)
    date_debut = db.Column(db.Date, nullable=False)
    date_fin = db.Column(db.Date, nullable=True)
    salaire_base = db.Column(db.Integer, nullable=False)
    devise = db.Column(db.String(3), nullable=False, default="CDF")
    statut = db.Column(db.String(20), nullable=False, default="Actif")


class StaffAdvance(db.Model):
    __tablename__ = "staff_advance"
    id = db.Column(db.Integer, primary_key=True)
    personnel_id = db.Column(db.Integer, db.ForeignKey("personnel.id"), nullable=False, index=True)
    montant = db.Column(db.Integer, nullable=False)
    devise = db.Column(db.String(3), nullable=False, default="CDF")
    date_avance = db.Column(db.Date, nullable=False, default=date.today)
    motif = db.Column(db.String(180), nullable=False)
    statut = db.Column(db.String(20), nullable=False, default="À retenir")


class PayrollRecord(db.Model):
    __tablename__ = "payroll_record"
    id = db.Column(db.Integer, primary_key=True)
    personnel_id = db.Column(db.Integer, db.ForeignKey("personnel.id"), nullable=False, index=True)
    periode = db.Column(db.String(20), nullable=False)
    salaire_base = db.Column(db.Integer, nullable=False)
    avances = db.Column(db.Integer, nullable=False, default=0)
    deductions = db.Column(db.Integer, nullable=False, default=0)
    net_a_payer = db.Column(db.Integer, nullable=False)
    devise = db.Column(db.String(3), nullable=False, default="CDF")
    date_paiement = db.Column(db.Date, nullable=False, default=date.today)
    reference = db.Column(db.String(80), nullable=True)
    __table_args__ = (db.UniqueConstraint("personnel_id", "periode", "devise", name="uq_payroll_person_period_currency"),)


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

def parent_children(user):
    """Retourne uniquement les élèves explicitement liés au compte parent."""
    if user.role != "parent":
        return []
    children = list(user.enfants)
    if user.student_id:
        legacy = db.session.get(Student, user.student_id)
        if legacy and legacy not in children:
            children.append(legacy)
    return children

def admin_only(fn):
    @wraps(fn)
    @login_required
    def wrapped(*a, **kw):
        if current_user.role != "admin": abort(403)
        return fn(*a, **kw)
    return wrapped

import re
MATRICULE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{6}$")

def generer_matricule(annee, code_faculte, code_filiere):
    prefix = "{}-{}-{}-".format(int(annee), code_faculte, code_filiere)
    dernier = Student.query.filter(Student.matricule.like(prefix + "%")).order_by(Student.matricule.desc()).first()
    sequence = int(dernier.matricule.rsplit("-", 1)[1]) + 1 if dernier else 1
    while Student.query.filter_by(matricule=prefix + "{:06d}".format(sequence)).first():
        sequence += 1
    return prefix + "{:06d}".format(sequence)

def matricule_valide(value):
    return bool(MATRICULE_RE.fullmatch((value or "").strip()))

BASE = """
<!doctype html><html lang='fr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<meta name='theme-color' content='#075b49'><link rel='manifest' href='/manifest.json'><link rel='stylesheet' href='/static/style.css'>
<title>{{ title }} · École La Bonté</title></head><body>
{% if current_user.is_authenticated %}<div class='layout'><aside class='side'><a class='brand' href='/'> <b>✦</b><span>ÉCOLE LA BONTÉ<small>ESPACE SCOLAIRE</small></span></a>
<nav><a href='/'>▦ Tableau de bord</a>{% if current_user.role=='admin' %}<a href='/eleves'>♙ Élèves</a><a href='/admissions'>▣ Admissions</a><a href='/reinscriptions'>↻ Réinscriptions</a><a href='/facultes'>▦ Facultés & filières</a><a href='/historique'>▤ Historique académique</a><a href='/affectations'>♧ Affectations enseignants</a><a href='/comptes'>♧ Comptes utilisateurs</a><a href='/personnel'>♙ Personnel & paie</a>{% endif %}{% if current_user.role in ['enseignant','admin'] %}<a href='/mon-salaire'>◈ Mon salaire</a>{% endif %}<a href='/assistant'>✧ Assistant scolaire</a>
<a href='/notes'>▤ Notes & résultats</a><a href='/bulletins'>▧ Bulletins</a>{% if current_user.role in ['admin','enseignant'] %}<a href='/presences'>◷ Présences</a>{% endif %}<a href='/messages'>✉ Messages</a><a href='/finances'>◈ Finances</a><a href='/frais'>▣ Frais par classe</a><a href='/horaire'>▦ Emploi du temps</a></nav>
<div class='side-bottom'><b>{{ current_user.nom }}</b><small>{{ current_user.role|capitalize }}</small><a href='/deconnexion'>↪ Déconnexion</a></div></aside>
<main class='main'><header><div><small class='kicker'>ÉCOLE LA BONTÉ · LUBUMBASHI</small><h1>{{ title }}</h1></div><span class='avatar'>{{ current_user.nom[:1] }}</span></header>
{% with alerts=get_flashed_messages(with_categories=true) %}{% for cat,msg in alerts %}<div class='alert {{ cat }}'>{{ msg }}</div>{% endfor %}{% endwith %}
{{ content|safe }}</main><nav class='bottom-nav'><a href='/'>Accueil</a>{% if current_user.role=='admin' %}<a href='/eleves'>Élèves</a>{% endif %}{% if current_user.role in ['admin','enseignant'] %}<a href='/presences'>Présences</a>{% endif %}<a href='/notes'>Notes</a><a href='/bulletins'>Bulletins</a><a href='/messages'>Messages</a><a href='/finances'>Finances</a><a href='/frais'>Frais</a></nav></div>
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
<button class='btn primary wide'>Se connecter</button><a href='/creer-compte-eleve'>Créer un compte Élève – École La Bonté, Chemègue, Lubumbashi</a><a href='/admission'>Déposer une demande d'admission</a><small class='muted'>Élèves · Parents · Enseignants · Administration</small></form></div>
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
<div class='quick'><a href='/notes'>▤ <b>Mes notes</b><small>Voir mes résultats</small></a><a href='/messages'>✉ <b>Messages</b><small>Contacter l'école</small></a><a href='/finances'>◈ <b>Paiements</b><small>Suivre mes frais</small></a><a href='/frais'>▣ <b>Frais</b><small>Voir les soldes</small></a></div>
"""
DASH_PARENT = """
<section class='hero'><div><small>ESPACE PARENT</small><h2>Bienvenue, {{ current_user.nom }}</h2><p>Consultez les informations scolaires de vos enfants.</p></div><span>✦</span></section>
{% for item in children %}<section class='panel profile'><img src='/static/uploads/{{ item.student.photo }}'><div><small>MATRICULE {{ item.student.matricule }}</small><h2>{{ item.student.nom }}</h2><p>{{ item.student.filiere }} · {{ item.student.classe }} · {{ item.student.promotion }}</p><b>Moyenne : {{ item.student.moyenne }}/20</b><p>Absences : <strong>{{ item.absences }}</strong> · Paiements : <strong>{{ item.payments }}</strong></p></div></section>{% else %}<section class='panel'>Aucun enfant n'est encore lié à ce compte. Contactez l'administration.</section>{% endfor %}
<div class='quick'><a href='/notes'>▤ <b>Résultats</b><small>Notes des enfants</small></a><a href='/messages'>✉ <b>Messages</b><small>Contacter l'école</small></a><a href='/finances'>◈ <b>Paiements</b><small>Suivre les frais</small></a><a href='/frais'>▣ <b>Frais</b><small>Voir les soldes</small></a></div>
"""
STUDENTS = """
<section class='panel'><div class='panel-head'><div><h2>Liste des élèves</h2><p>{{ students|length }} dossier(s)</p></div><a class='btn primary' href='/eleves/nouveau'>＋ Ajouter un élève</a></div>
<form class='search'><input name='q' value='{{ q }}' placeholder='Rechercher par nom ou matricule'><button class='btn dark'>Rechercher</button></form>
<div class='table-wrap'><table><tr><th>Élève</th><th>Matricule</th><th>Faculté / Filière</th><th>Classe</th><th>Moyenne</th><th></th></tr>{% for s in students %}<tr><td><img class='mini' src='/static/uploads/{{ s.photo }}'> {{ s.nom }}</td><td><span class='pill'>{{ s.matricule }}</span></td><td>{{ s.faculte }}<small class='sub'>{{ s.filiere }}</small></td><td>{{ s.classe }}</td><td>{{ s.moyenne }}/20</td><td><a href='/eleves/{{ s.id }}'>Ouvrir →</a></td></tr>{% else %}<tr><td colspan='6'>Aucun élève trouvé.</td></tr>{% endfor %}</table></div></section>
"""
STUDENT_FORM = """
<section class='panel'><h2>{{ 'Modifier le dossier' if s else 'Nouvelle inscription' }}</h2><p>La photo est obligatoire à la création. Le matricule est attribué automatiquement à partir de l'année, du code faculté et du code filière.</p>
<form method='post' enctype='multipart/form-data' class='form-grid'>
<label class='photo'>Photo de profil {% if not s %}*{% endif %}<input type='file' name='photo' accept='.jpg,.jpeg,.png,.webp' {% if not s %}required{% endif %}><img id='preview' src='{{ ("/static/uploads/"+s.photo) if s else "" }}' {% if not s %}hidden{% endif %}></label>
<label>Nom complet *<input name='nom' required value='{{ s.nom if s else "" }}'></label>
{% if s %}<label>Matricule officiel<input value='{{ s.matricule }}' readonly></label>{% else %}<label>Matricule officiel<input value='Attribué automatiquement après validation' readonly></label>{% endif %}
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
<div class='actions'><a class='btn primary' href='/eleves/{{ s.id }}/carte'>Carte élève / QR code</a><a class='btn outline' href='/eleves/{{ s.id }}/inscription.pdf'>Document d'inscription PDF</a><a class='btn primary' href='/eleves/{{ s.id }}/modifier'>Modifier</a><form method='post' action='/eleves/{{ s.id }}/supprimer' onsubmit="return confirm('Supprimer ce dossier ?')"><button class='btn danger'>Supprimer</button></form></div></section>
"""
GRADES = """
{% if admin %}<section class='panel'><h2>Ajouter une note</h2><form method='post' class='inline-form'><label>Élève<select name='student_id' required>{% for s in students %}<option value='{{ s.id }}'>{{ s.nom }} · {{ s.matricule }}</option>{% endfor %}</select></label><label>Cours<input name='cours' required></label><label>Note / 20<input type='number' name='note' min='0' max='20' step='.01' required></label><label>Période<input name='periode' value='Trimestre 1'></label><button class='btn primary'>Enregistrer</button></form></section>
{% elif teacher %}<section class='panel'><h2>Saisir une note pour un cours affecté</h2><p>Vous ne pouvez évaluer que les élèves de vos classes et les cours qui vous sont attribués.</p><form method='post' class='inline-form'><label>Élève<select name='student_id' required>{% for s in students %}<option value='{{ s.id }}'>{{ s.nom }} · {{ s.classe }}</option>{% endfor %}</select></label><label>Cours affecté<select name='assignment_id' required>{% for a in assignments %}<option value='{{ a.id }}'>{{ a.cours }} · {{ a.classe }} · {{ a.annee_academique }}</option>{% endfor %}</select></label><label>Note / 20<input type='number' name='note' min='0' max='20' step='.01' required></label><label>Période<input name='periode' value='Trimestre 1' required></label><button class='btn primary' {% if not assignments or not students %}disabled{% endif %}>Enregistrer la note</button></form>{% if not assignments %}<p>Aucun cours ne vous est affecté. Contactez l'administration.</p>{% endif %}</section>{% endif %}
<section class='panel'><h2>Résultats et notes</h2><div class='table-wrap'><table><tr><th>Élève</th><th>Cours</th><th>Période</th><th>Note</th></tr>{% for n in notes %}<tr><td>{{ n.eleve.nom }}</td><td>{{ n.cours }}</td><td>{{ n.periode }}</td><td><b>{{ n.note }}/20</b></td></tr>{% else %}<tr><td colspan='4'>Aucune note disponible.</td></tr>{% endfor %}</table></div></section>
"""

BULLETIN = """
<style>
@media print {
  @page { size: A4; margin: 14mm; }
  body { background: white !important; }
  .side, .bottom-nav, header, .no-print, .alert { display: none !important; }
  .layout, .main { display: block !important; margin: 0 !important; padding: 0 !important; width: 100% !important; }
  .panel { box-shadow: none !important; border: 1px solid #bbb !important; break-inside: avoid; margin: 0 0 14px !important; }
  .bulletin-head { border-bottom: 2px solid #075b49; padding-bottom: 12px; margin-bottom: 14px; }
  table { width: 100%; border-collapse: collapse; }
  th, td { border: 1px solid #aaa !important; padding: 7px !important; }
}
.bulletin-head { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; }
.bulletin-mark { color:#b58b26; font-size:30px; font-weight:800; }
.bulletin-meta { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; margin:16px 0; }
.bulletin-meta div { background:#f5f7f5; padding:10px; border-radius:8px; }
.bulletin-meta small { display:block; color:#667; margin-bottom:3px; }
.bulletin-summary { display:flex; flex-wrap:wrap; gap:12px; margin-top:14px; }
.bulletin-summary div { background:#f5f7f5; border-radius:8px; padding:12px 16px; }
.bulletin-summary strong { display:block; font-size:20px; color:#075b49; }
.signature-row { display:flex; justify-content:space-between; gap:30px; margin-top:35px; }
.signature-row div { width:42%; border-top:1px solid #888; padding-top:8px; text-align:center; }
</style>
{% if admin and not student %}<section class='panel no-print'><h2>Choisir un élève</h2><form method='get' class='inline-form'><label>Élève<select name='student_id' required><option value=''>Sélectionner</option>{% for s in students %}<option value='{{ s.id }}'>{{ s.nom }} · {{ s.matricule }}</option>{% endfor %}</select></label><button class='btn primary'>Afficher le bulletin</button></form></section>
{% elif parent and not student %}{% if students %}<section class='panel no-print'><h2>Choisir un enfant</h2><form method='get' class='inline-form'><label>Enfant<select name='student_id' required><option value=''>Sélectionner</option>{% for s in students %}<option value='{{ s.id }}'>{{ s.nom }} · {{ s.matricule }}</option>{% endfor %}</select></label><button class='btn primary'>Afficher le bulletin</button></form></section>{% else %}<section class='panel'>Aucun enfant n'est lié à votre compte. Contactez l'administration.</section>{% endif %}
{% elif not student %}<section class='panel'>Votre compte n'est pas encore lié à un dossier élève. Contactez l'administration.</section>
{% else %}
<div class='panel no-print' style='display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap'><div><b>Bulletins scolaires</b><p>Consultez les résultats par année académique et période.</p></div><a class='btn primary' href='/bulletins/pdf?student_id={{ student.id }}'>Télécharger le bulletin PDF</a><button type='button' class='btn outline' onclick='window.print()'>Imprimer la page</button></div>
{% for group in groups %}
<section class='panel'>
  <div class='bulletin-head'><div><small class='kicker'>ÉCOLE LA BONTÉ · LUBUMBASHI</small><h2>Bulletin scolaire</h2><p>Année académique {{ group.annee }} · {{ group.periode }}</p></div><div class='bulletin-mark'>✦</div></div>
  <div class='bulletin-meta'><div><small>ÉLÈVE</small><b>{{ student.nom }}</b></div><div><small>MATRICULE</small><b>{{ student.matricule }}</b></div><div><small>FACULTÉ / FILIÈRE</small><b>{{ student.faculte }} · {{ student.filiere }}</b></div><div><small>PROMOTION / CLASSE</small><b>{{ student.promotion }} · {{ student.classe }}</b></div></div>
  <div class='table-wrap'><table><tr><th>Matière / Cours</th><th>Note obtenue</th><th>Maximum</th></tr>{% for n in group.notes %}<tr><td>{{ n.cours }}</td><td><b>{{ '%.2f'|format(n.note) }}</b></td><td>20</td></tr>{% endfor %}</table></div>
  <div class='bulletin-summary'><div><small>Moyenne générale</small><strong>{{ '%.2f'|format(group.moyenne) }}/20</strong></div><div><small>Appréciation</small><strong>{{ group.appreciation }}</strong></div><div><small>Résultat</small><strong>{{ 'Admis' if group.moyenne >= 10 else 'À renforcer' }}</strong></div></div>
  <div class='signature-row'><div>Le titulaire</div><div>La Direction</div></div>
</section>
{% else %}<section class='panel'>Aucune note n'est encore disponible pour cet élève.</section>{% endfor %}
{% endif %}
"""

FINANCES = """
{% if admin %}<section class='panel'><h2>Enregistrer un paiement</h2><form method='post' class='inline-form'><label>Élève<select name='student_id' required>{% for s in students %}<option value='{{ s.id }}'>{{ s.nom }} · {{ s.matricule }}</option>{% endfor %}</select></label><label>Libellé<input name='libelle' required placeholder='Frais scolaires'></label><label>Montant<input type='number' name='montant' min='1' step='1' required></label><label>Devise<select name='devise' required><option value='CDF'>CDF — Franc congolais</option><option value='USD'>USD — Dollar américain</option></select></label><label>Statut<select name='statut'><option>Payé</option><option>En attente</option></select></label><button class='btn primary'>Ajouter</button></form></section>{% endif %}
<section class='panel'><h2>Soldes et suivi des paiements</h2>
<div class='stats-grid'>
<article class='stat'><small>Payé en CDF</small><strong>{{ "{:,.0f}".format(totaux.CDF.paye).replace(",", " ") }} CDF</strong></article>
<article class='stat'><small>En attente en CDF</small><strong>{{ "{:,.0f}".format(totaux.CDF.attente).replace(",", " ") }} CDF</strong></article>
<article class='stat'><small>Payé en USD</small><strong>{{ "{:,.0f}".format(totaux.USD.paye).replace(",", " ") }} USD</strong></article>
<article class='stat'><small>En attente en USD</small><strong>{{ "{:,.0f}".format(totaux.USD.attente).replace(",", " ") }} USD</strong></article>
</div><div class='table-wrap'><table><tr><th>Élève</th><th>Libellé</th><th>Montant</th><th>Devise</th><th>Statut</th><th>Reçu</th></tr>
{% for p in paiements %}<tr><td>{{ p.eleve.nom }}</td><td>{{ p.libelle }}</td><td>{{ "{:,.0f}".format(p.montant).replace(",", " ") }}</td><td>{{ p.devise }}</td><td>{{ p.statut }}</td><td><a class='btn outline' href='/finances/{{ p.id }}/recu.pdf'>PDF</a></td></tr>
{% else %}<tr><td colspan='6'>Aucun paiement.</td></tr>{% endfor %}</table></div></section>
"""

FEES = """
<section class='panel'><form method='get' class='inline-form'>
<label>Année académique à consulter<input name='annee' value='{{ annee }}' required placeholder='2026-2027'></label>
<button class='btn outline'>Afficher</button></form></section>
{% if admin %}
<section class='panel'><h2>Définir les frais d'une classe</h2>
<form method='post' class='inline-form'>
<input type='hidden' name='action' value='create_fee'>
<label>Classe exacte<input name='classe' required placeholder='Ex. 3e A'></label>
<label>Année académique<input name='annee_academique' required value='2026-2027'></label>
<label>Intitulé<input name='libelle' required placeholder='Frais scolaires'></label>
<label>Montant total<input type='number' name='montant' min='1' step='1' required></label>
<label>Devise<select name='devise'><option value='CDF'>CDF</option><option value='USD'>USD</option></select></label>
<button class='btn primary'>Créer les frais</button></form></section>
<section class='panel'><h2>Enregistrer un versement</h2>
<form method='post' class='inline-form'>
<input type='hidden' name='action' value='record_payment'>
<label>Élève<select name='student_id' required>{% for s in students %}<option value='{{ s.id }}'>{{ s.nom }} · {{ s.classe }}</option>{% endfor %}</select></label>
<label>Frais à payer<select name='fee_id' required>{% for f in frais %}<option value='{{ f.id }}'>{{ f.classe }} · {{ f.libelle }} · {{ f.montant }} {{ f.devise }} · {{ f.annee_academique }}</option>{% endfor %}</select></label>
<label>Montant du versement<input type='number' name='montant' min='1' step='1' required></label>
<label>Référence (facultatif)<input name='reference'></label>
<button class='btn primary'>Enregistrer le versement</button></form></section>
{% endif %}
<section class='panel'><h2>État des frais et soldes</h2>
<div class='table-wrap'><table><tr><th>Élève</th><th>Classe</th><th>Année</th><th>Frais</th><th>Total dû</th><th>Payé</th><th>Reste</th><th>Devise</th></tr>
{% for row in soldes %}<tr><td>{{ row.eleve.nom }}</td><td>{{ row.eleve.classe }}</td><td>{{ row.frais.annee_academique }}</td><td>{{ row.frais.libelle }}</td><td>{{ "{:,.0f}".format(row.total).replace(",", " ") }}</td><td>{{ "{:,.0f}".format(row.paye).replace(",", " ") }}</td><td><b>{{ "{:,.0f}".format(row.reste).replace(",", " ") }}</b></td><td>{{ row.frais.devise }}</td></tr>
{% else %}<tr><td colspan='8'>Aucun frais applicable pour cette année académique.</td></tr>{% endfor %}</table></div></section>
<section class='panel'><h2>Historique des versements</h2>
<div class='table-wrap'><table><tr><th>Date</th><th>Élève</th><th>Frais</th><th>Montant</th><th>Référence</th><th>Reçu</th></tr>
{% for v in versements %}<tr><td>{{ v.date_paiement.strftime('%d/%m/%Y') }}</td><td>{{ v.eleve.nom }}</td><td>{{ v.frais.libelle }}</td><td>{{ "{:,.0f}".format(v.montant).replace(",", " ") }} {{ v.frais.devise }}</td><td>{{ v.reference or '-' }}</td><td><a class='btn outline' href='/frais/versement/{{ v.id }}/recu.pdf'>PDF</a></td></tr>
{% else %}<tr><td colspan='6'>Aucun versement enregistré.</td></tr>{% endfor %}</table></div></section>
"""


ADMISSION_FORM = """
<section class='hero'><div><small>ÉCOLE LA BONTÉ · LUBUMBASHI</small><h2>Demande d'admission</h2><p>Remplissez les informations pour soumettre un dossier à l'administration.</p></div><span>✦</span></section>
<section class='panel'><form method='post' enctype='multipart/form-data' class='form-grid'>
<label>Nom complet de l'élève *<input name='nom' required maxlength='160'></label>
<label>Photo de l'élève *<input type='file' name='photo' accept='.jpg,.jpeg,.png,.webp' required></label>
<label>Faculté *<select name='faculty_id' required><option value=''>Choisir</option>{% for f in faculties %}<option value='{{ f.id }}'>{{ f.code }} · {{ f.nom }}</option>{% endfor %}</select></label>
<label>Filière *<select name='program_id' required><option value=''>Choisir</option>{% for f in faculties %}{% for p in f.filieres %}<option value='{{ p.id }}'>{{ f.nom }} — {{ p.code }} · {{ p.nom }}</option>{% endfor %}{% endfor %}</select></label>
<label>Classe demandée *<input name='classe' required></label>
<label>Promotion *<input name='promotion' required placeholder='Ex. 1re année'></label>
<label>Année académique *<input name='annee_academique' required value='2026-2027'></label>
<label>Téléphone du parent/tuteur<input name='telephone_parent' maxlength='40'></label>
<div class='actions'><button class='btn primary'>Soumettre la demande</button></div>
</form></section>
"""
ADMISSIONS = """
<section class='panel'><h2>Dossiers d'admission</h2><div class='table-wrap'><table><tr><th>Date</th><th>Candidat</th><th>Faculté / Filière</th><th>Classe</th><th>Année</th><th>Statut</th><th>Action</th></tr>
{% for a in demandes %}<tr><td>{{ a.cree_le.strftime('%d/%m/%Y') }}</td><td>{{ a.nom }}</td><td>{{ a.faculty.nom }} / {{ a.program.nom }}</td><td>{{ a.classe }}</td><td>{{ a.annee_academique }}</td><td>{{ a.statut }}</td><td>{% if a.statut == 'En attente' %}<form method='post' class='inline-form'><input type='hidden' name='application_id' value='{{ a.id }}'><button class='btn primary' name='action' value='accepter'>Accepter</button><button class='btn danger' name='action' value='refuser'>Refuser</button></form>{% elif a.student_id %}<a href='/eleves/{{ a.student_id }}/inscription.pdf'>Document PDF</a>{% endif %}</td></tr>
{% else %}<tr><td colspan='7'>Aucune demande.</td></tr>{% endfor %}</table></div></section>
"""
REENROLLMENTS = """
<section class='panel'><h2>Enregistrer une réinscription</h2><form method='post' class='inline-form'>
<label>Élève<select name='student_id' required>{% for s in students %}<option value='{{ s.id }}'>{{ s.nom }} · {{ s.matricule }} · {{ s.classe }}</option>{% endfor %}</select></label>
<label>Année académique<input name='annee_academique' required value='2026-2027'></label>
<label>Promotion<input name='promotion' required></label><label>Nouvelle classe<input name='classe' required></label>
<button class='btn primary'>Confirmer la réinscription</button></form></section>
<section class='panel'><h2>Historique des inscriptions</h2><div class='table-wrap'><table><tr><th>Élève</th><th>Matricule</th><th>Année</th><th>Promotion</th><th>Classe</th><th>Date</th><th>Document</th></tr>
{% for e in records %}<tr><td>{{ e.student.nom }}</td><td>{{ e.student.matricule }}</td><td>{{ e.annee_academique }}</td><td>{{ e.promotion }}</td><td>{{ e.classe }}</td><td>{{ e.date_inscription.strftime('%d/%m/%Y') }}</td><td><a href='/eleves/{{ e.student_id }}/inscription.pdf'>PDF</a></td></tr>{% else %}<tr><td colspan='7'>Aucune réinscription.</td></tr>{% endfor %}</table></div></section>
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
<section class='panel'><h2>Créer un compte utilisateur</h2><p>Pour un parent, sélectionnez tous ses enfants. Les liens sont réservés à l'administration.</p>
<form method='post' class='inline-form'><label>Nom complet<input name='nom' required></label><label>E-mail<input name='email' type='email' required></label><label>Mot de passe provisoire<input name='password' type='password' minlength='10' required></label><label>Rôle<select name='role'><option value='eleve'>Élève</option><option value='parent'>Parent</option><option value='enseignant'>Enseignant</option><option value='admin'>Administrateur</option></select></label>
<label>Enfant(s) du parent — sélection multiple<select name='student_ids' multiple size='5'>{% for s in students %}<option value='{{ s.id }}'>{{ s.nom }} · {{ s.matricule }}</option>{% endfor %}</select></label>
<label>Dossier lié (compte élève) <select name='student_id'><option value=''>Non lié</option>{% for s in students %}<option value='{{ s.id }}'>{{ s.nom }} · {{ s.matricule }}</option>{% endfor %}</select></label><button class='btn primary'>Créer le compte</button></form></section>
<section class='panel'><h2>Comptes existants</h2><div class='table-wrap'><table><tr><th>Nom</th><th>E-mail</th><th>Rôle</th><th>Enfants liés</th></tr>{% for u in users %}<tr><td>{{ u.nom }}</td><td>{{ u.email }}</td><td>{{ u.role }}</td><td>{% if u.role=='parent' %}{{ u.enfants|map(attribute='nom')|join(', ') }}{% elif u.student_id %}{{ u.student_id }}{% else %}—{% endif %}</td></tr>{% endfor %}</table></div></section>
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
    if current_user.role == "parent":
        children = []
        for child in parent_children(current_user):
            children.append({
                "student": child,
                "absences": Attendance.query.filter_by(student_id=child.id, statut="Absent").count(),
                "payments": Payment.query.filter_by(student_id=child.id).count()
            })
        return page("Espace parent", DASH_PARENT, children=children)
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
        matricule=generer_matricule(annee,cf,cfi)
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
        db.session.add(s); db.session.flush()
        db.session.add(Enrollment(student_id=s.id, annee_academique=str(annee) + "-" + str(annee + 1),
            promotion=s.promotion, classe=s.classe, statut="Inscrit"))
        db.session.commit()
        flash("Inscription enregistrée. Matricule attribué : " + s.matricule, "success")
        return redirect(url_for("eleve_detail", sid=s.id))
    return page("Nouvelle inscription", STUDENT_FORM, s=None, matricule="", faculties=FacultyCatalog.query.order_by(FacultyCatalog.code).all())

@app.route("/eleves/<int:sid>")
@admin_only
def eleve_detail(sid):
    return page("Dossier de l'élève", DETAIL, s=db.get_or_404(Student,sid))



@app.route("/eleves/<int:sid>/carte")
@admin_only
def eleve_carte(sid):
    s = db.get_or_404(Student, sid)
    template = """
    <style>
    .student-card{max-width:760px;margin:22px auto;padding:26px;border:3px solid #b58b26;border-radius:18px;background:linear-gradient(135deg,#fff,#f2f7f3);display:grid;grid-template-columns:1fr 150px;gap:20px;align-items:center}
    .student-card .school{color:#075b49;font-weight:800;letter-spacing:1.5px;font-size:20px}
    .student-card .subtitle{color:#65736b;font-size:11px;margin:5px 0 18px}
    .student-card .student-photo{width:118px;height:140px;object-fit:cover;border:3px solid #b58b26;border-radius:10px}
    .student-card .qr{width:132px;height:132px;object-fit:contain;background:white;padding:5px;border:1px solid #ddd;border-radius:8px}
    .student-card .matricule{font-size:18px;font-weight:800;color:#075b49;letter-spacing:1px}
    .student-card .field{margin:9px 0}.student-card small{display:block;color:#64736b;font-size:10px;text-transform:uppercase}
    @media print{.side,header,.bottom-nav,.no-print,.alert{display:none!important}.layout,.main{display:block!important;margin:0!important;padding:0!important}.student-card{box-shadow:none;margin:20mm auto;break-inside:avoid}}
    @media(max-width:560px){.student-card{grid-template-columns:1fr 110px;padding:15px;gap:10px}.student-card .student-photo{width:88px;height:108px}.student-card .qr{width:100px;height:100px}}
    </style>
    <section class="panel">
      <div class="panel-head no-print"><div><h2>Carte d'élève</h2><p>Carte officielle à imprimer et plastifier</p></div><button class="btn primary" type="button" onclick="window.print()">Imprimer la carte</button></div>
      <div class="student-card">
        <div><div class="school">✦ ÉCOLE LA BONTÉ</div><div class="subtitle">LUBUMBASHI · CARTE D'IDENTIFICATION SCOLAIRE</div>
          <img class="student-photo" src="/static/uploads/{{ s.photo }}" alt="Photo de l'élève">
          <div class="field"><small>Nom complet</small><strong>{{ s.nom }}</strong></div>
          <div class="field"><small>Matricule</small><div class="matricule">{{ s.matricule }}</div></div>
          <div class="field"><small>Promotion · Classe</small><strong>{{ s.promotion }} · {{ s.classe }}</strong></div>
          <div class="field"><small>Faculté · Filière</small><strong>{{ s.faculte }} · {{ s.filiere }}</strong></div>
        </div>
        <div style="text-align:center"><img class="qr" src="/eleves/{{ s.id }}/qr.png" alt="QR code du matricule"><small>Scanner pour lire le matricule</small></div>
      </div>
      <div class="actions no-print"><a class="btn outline" href="/eleves/{{ s.id }}">Retour au dossier</a></div>
    </section>
    """
    return page("Carte d'élève", template, s=s)


@app.route("/eleves/<int:sid>/qr.png")
@admin_only
def eleve_qr(sid):
    s = db.get_or_404(Student, sid)
    try:
        import qrcode
    except ImportError:
        abort(503, description="Le module qrcode est absent. Installez requirements.txt.")
    payload = "ECOLE LA BONTE | LUBUMBASHI | MATRICULE:" + s.matricule
    image = qrcode.make(payload)
    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return send_file(output, mimetype="image/png", download_name="qr-" + s.matricule + ".png")

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
    is_admin=current_user.role=="admin"
    is_teacher=current_user.role=="enseignant"
    if request.method=="POST":
        if not (is_admin or is_teacher): abort(403)
        try:
            student_id=int(request.form["student_id"])
            note=float(request.form["note"])
        except (ValueError, KeyError, TypeError):
            abort(400)
        if not 0 <= note <= 20: abort(400)
        student=db.session.get(Student, student_id)
        cours=request.form.get("cours","").strip() if is_admin else ""
        if is_teacher:
            try: assignment_id=int(request.form.get("assignment_id",""))
            except (ValueError, TypeError): abort(400)
            assignment=TeacherAssignment.query.filter_by(id=assignment_id,teacher_id=current_user.id).first()
            if not assignment or not student or student.classe != assignment.classe:
                abort(403)
            cours=assignment.cours
        elif not student or not cours:
            abort(400)
        n=Grade(student_id=student.id,cours=cours,note=note,
            periode=request.form.get("periode","Trimestre 1").strip() or "Trimestre 1",
            annee_academique=(assignment.annee_academique if is_teacher else "2026-2027"))
        db.session.add(n); db.session.commit()
        flash("Note enregistrée.", "success")
        return redirect(url_for("notes"))
    query=Grade.query.join(Student)
    students=[]
    assignments=[]
    if is_admin:
        students=Student.query.order_by(Student.nom).all()
        notes_list=query.order_by(Grade.id.desc()).all()
    elif is_teacher:
        assignments=TeacherAssignment.query.filter_by(teacher_id=current_user.id).order_by(
            TeacherAssignment.annee_academique.desc(),TeacherAssignment.classe,TeacherAssignment.cours).all()
        pairs=[db.and_(Student.classe==a.classe,Grade.cours==a.cours,Grade.annee_academique==a.annee_academique) for a in assignments]
        students=Student.query.filter(Student.classe.in_([a.classe for a in assignments])).order_by(Student.nom).all() if assignments else []
        notes_list=query.filter(db.or_(*pairs)).order_by(Grade.id.desc()).all() if pairs else []
    elif current_user.role == "parent":
        child_ids=[child.id for child in parent_children(current_user)]
        notes_list=query.filter(Grade.student_id.in_(child_ids)).order_by(Grade.id.desc()).all() if child_ids else []
    else:
        if not current_user.student_id:
            return page("Notes",GRADES,admin=False,teacher=False,notes=[],students=[],assignments=[])
        notes_list=query.filter(Grade.student_id==current_user.student_id).order_by(Grade.id.desc()).all()
    return page("Notes & résultats",GRADES,admin=is_admin,teacher=is_teacher,notes=notes_list,
        students=students,assignments=assignments)


@app.route("/bulletins")
@login_required
def bulletins():
    is_admin = current_user.role == "admin"
    is_parent = current_user.role == "parent"
    if current_user.role == "enseignant":
        abort(403)

    students = []
    student = None
    if is_admin:
        students = Student.query.order_by(Student.nom).all()
        raw_id = request.args.get("student_id", "").strip()
        if raw_id:
            try:
                student = db.session.get(Student, int(raw_id))
            except ValueError:
                abort(400)
            if not student:
                abort(404)
    elif is_parent:
        students = parent_children(current_user)
        raw_id = request.args.get("student_id", "").strip()
        if raw_id:
            try:
                requested_id = int(raw_id)
            except ValueError:
                abort(400)
            student = next((child for child in students if child.id == requested_id), None)
            if not student:
                abort(403)
        elif len(students) == 1:
            student = students[0]
    else:
        student = db.session.get(Student, current_user.student_id) if current_user.student_id else None

    groups = []
    if student:
        grades = Grade.query.filter_by(student_id=student.id).order_by(
            Grade.annee_academique.desc(), Grade.periode, Grade.cours, Grade.id
        ).all()
        grouped = {}
        for grade in grades:
            key = (grade.annee_academique or "Non précisée", grade.periode or "Période non précisée")
            grouped.setdefault(key, []).append(grade)
        for (annee, periode), rows in grouped.items():
            moyenne = sum(row.note for row in rows) / len(rows)
            if moyenne >= 16:
                appreciation = "Très bien"
            elif moyenne >= 14:
                appreciation = "Bien"
            elif moyenne >= 12:
                appreciation = "Assez bien"
            elif moyenne >= 10:
                appreciation = "Passable"
            else:
                appreciation = "Insuffisant"
            groups.append({
                "annee": annee,
                "periode": periode,
                "notes": rows,
                "moyenne": moyenne,
                "appreciation": appreciation
            })
    return page("Bulletins scolaires", BULLETIN, admin=is_admin,
                parent=is_parent, students=students, student=student, groups=groups)




@app.route("/bulletins/pdf")
@login_required
def bulletin_pdf():
    is_admin = current_user.role == "admin"
    is_parent = current_user.role == "parent"
    if current_user.role == "enseignant":
        abort(403)
    raw_id = request.args.get("student_id", "").strip()
    if is_admin:
        if not raw_id: abort(400)
        try: student = db.session.get(Student, int(raw_id))
        except ValueError: abort(400)
        if not student: abort(404)
    elif is_parent:
        children = parent_children(current_user)
        if not raw_id and len(children) == 1:
            student = children[0]
        else:
            try: sid = int(raw_id)
            except (ValueError, TypeError): abort(400)
            student = next((child for child in children if child.id == sid), None)
            if not student: abort(403)
    else:
        student = db.session.get(Student, current_user.student_id) if current_user.student_id else None
        if not student or (raw_id and raw_id != str(student.id)): abort(403)

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    except ImportError:
        return "Le module PDF manque. Installez requirements.txt puis redémarrez.", 503

    notes = Grade.query.filter_by(student_id=student.id).order_by(
        Grade.annee_academique.desc(), Grade.periode, Grade.cours, Grade.id).all()
    groups = {}
    for n in notes:
        groups.setdefault((n.annee_academique or "Non précisée",
                           n.periode or "Période non précisée"), []).append(n)

    buffer = BytesIO()
    green, gold = colors.HexColor("#075b49"), colors.HexColor("#b58b26")
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
        topMargin=16*mm, bottomMargin=18*mm, title="Bulletin scolaire - "+student.nom,
        author="École La Bonté · Lubumbashi")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="School", parent=styles["Title"], fontSize=19,
        leading=23, textColor=green, alignment=1, spaceAfter=2))
    styles.add(ParagraphStyle(name="SubSchool", parent=styles["Normal"], fontSize=8,
        textColor=colors.HexColor("#58645e"), alignment=1, spaceAfter=10))
    styles.add(ParagraphStyle(name="BulletinTitle", parent=styles["Heading2"],
        fontSize=14, textColor=green, alignment=1, spaceAfter=8))
    story = []

    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(gold); canvas.line(18*mm, 14*mm, A4[0]-18*mm, 14*mm)
        canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.HexColor("#58645e"))
        canvas.drawString(18*mm, 8*mm, "École La Bonté · Lubumbashi")
        canvas.drawRightString(A4[0]-18*mm, 8*mm, "Page %s" % document.page)
        canvas.restoreState()

    if not groups:
        groups = {("Non précisée", "Aucune note"): []}
    for index, ((year, period), rows) in enumerate(groups.items()):
        if index: story.append(PageBreak())
        story += [Paragraph("✦", ParagraphStyle(name="Emblem"+str(index),
            parent=styles["Title"], fontSize=23, textColor=gold, alignment=1)),
            Paragraph("ÉCOLE LA BONTÉ", styles["School"]),
            Paragraph("LUBUMBASHI · RÉPUBLIQUE DÉMOCRATIQUE DU CONGO", styles["SubSchool"]),
            Paragraph("BULLETIN SCOLAIRE", styles["BulletinTitle"]),
            Paragraph("<b>Année académique :</b> "+escape(year)+" &nbsp;&nbsp; <b>Période :</b> "+escape(period), styles["Normal"]),
            Spacer(1, 7)]
        info = [
            [Paragraph("<b>ÉLÈVE</b><br/>"+escape(student.nom), styles["Normal"]),
             Paragraph("<b>MATRICULE</b><br/>"+escape(student.matricule), styles["Normal"])],
            [Paragraph("<b>FACULTÉ / FILIÈRE</b><br/>"+escape(student.faculte)+" / "+escape(student.filiere), styles["Normal"]),
             Paragraph("<b>PROMOTION / CLASSE</b><br/>"+escape(student.promotion)+" / "+escape(student.classe), styles["Normal"])]
        ]
        t=Table(info,colWidths=[87*mm,87*mm],rowHeights=[17*mm,17*mm])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#f1f6f2")),
            ("BOX",(0,0),(-1,-1),.6,colors.HexColor("#cbd8d0")),
            ("INNERGRID",(0,0),(-1,-1),.4,colors.HexColor("#d5dfd9")),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),9)]))
        story += [t, Spacer(1,9)]
        data=[["MATIÈRE / COURS","NOTE OBTENUE","MAXIMUM"]]
        data += [[Paragraph(escape(n.cours),styles["Normal"]),"{:.2f}".format(n.note),"20"] for n in rows]
        table=Table(data,colWidths=[112*mm,31*mm,31*mm],repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),green),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("GRID",(0,0),(-1,-1),.5,colors.HexColor("#b9c8bf")),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f6f8f6")]),
            ("ALIGN",(1,1),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("FONTSIZE",(0,0),(-1,-1),9),("TOPPADDING",(0,0),(-1,-1),7),
            ("BOTTOMPADDING",(0,0),(-1,-1),7)]))
        story += [table, Spacer(1,10)]
        if rows:
            avg=sum(n.note for n in rows)/len(rows)
            appr=("Très bien" if avg>=16 else "Bien" if avg>=14 else
                  "Assez bien" if avg>=12 else "Passable" if avg>=10 else "Insuffisant")
            summary=[["MOYENNE GÉNÉRALE","APPRÉCIATION","RÉSULTAT"],
                     ["{:.2f}/20".format(avg),appr,"Admis" if avg>=10 else "À renforcer"]]
        else:
            summary=[["MOYENNE GÉNÉRALE","APPRÉCIATION","RÉSULTAT"],["—","—","En attente de notes"]]
        st=Table(summary,colWidths=[58*mm,58*mm,58*mm])
        st.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#eaf1ec")),
            ("TEXTCOLOR",(0,0),(-1,0),green),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTNAME",(0,1),(-1,1),"Helvetica-Bold"),("ALIGN",(0,0),(-1,-1),"CENTER"),
            ("BOX",(0,0),(-1,-1),.6,gold),("INNERGRID",(0,0),(-1,-1),.4,colors.HexColor("#d5dfd9")),
            ("FONTSIZE",(0,0),(-1,-1),9),("TOPPADDING",(0,0),(-1,-1),8),
            ("BOTTOMPADDING",(0,0),(-1,-1),8)]))
        story += [st, Spacer(1,28)]
        sig=Table([["Le titulaire","La Direction"],["\n\n________________________","\n\n________________________"]],
                  colWidths=[87*mm,87*mm])
        sig.setStyle(TableStyle([("ALIGN",(0,0),(-1,-1),"CENTER"),
            ("TEXTCOLOR",(0,0),(-1,0),green),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold")]))
        story.append(sig)
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    buffer.seek(0)
    filename="bulletin-"+re.sub(r"[^A-Za-z0-9_-]+","-",student.matricule)+".pdf"
    return send_file(buffer,mimetype="application/pdf",as_attachment=True,download_name=filename)


@app.route("/finances", methods=["GET","POST"])
@login_required
def finances():
    admin = current_user.role == "admin"
    if request.method == "POST":
        if not admin: abort(403)
        try:
            student_id = int(request.form.get("student_id", ""))
            montant = int(request.form.get("montant", ""))
        except (TypeError, ValueError):
            abort(400)
        student = db.session.get(Student, student_id)
        libelle = request.form.get("libelle", "").strip()
        devise = request.form.get("devise", "CDF").upper()
        statut = request.form.get("statut", "En attente")
        if not student or not libelle or montant <= 0 or devise not in ("CDF", "USD") or statut not in ("Payé", "En attente"):
            abort(400)
        payment = Payment(student_id=student.id, libelle=libelle, montant=montant,
                          devise=devise, statut=statut,
                          date_paiement=date.today() if statut == "Payé" else None)
        db.session.add(payment)
        db.session.commit()
        flash("Paiement enregistré.", "success")
        return redirect(url_for("finances"))
    query = Payment.query.join(Student)
    if not admin:
        if current_user.role == "parent":
            ids = [child.id for child in parent_children(current_user)]
            query = query.filter(Payment.student_id.in_(ids)) if ids else query.filter(db.false())
        elif current_user.role == "eleve" and current_user.student_id:
            query = query.filter(Payment.student_id == current_user.student_id)
        else:
            abort(403)
    paiements = query.order_by(Payment.id.desc()).all()
    totaux = {currency: {"paye": 0, "attente": 0} for currency in ("CDF", "USD")}
    for payment in paiements:
        if payment.devise in totaux:
            key = "paye" if payment.statut == "Payé" else "attente"
            totaux[payment.devise][key] += payment.montant
    return page("Finances scolaires", FINANCES, admin=admin, paiements=paiements,
                totaux=totaux, students=Student.query.order_by(Student.nom).all() if admin else [])


@app.route("/finances/<int:payment_id>/recu.pdf")
@login_required
def payment_receipt_pdf(payment_id):
    payment = db.get_or_404(Payment, payment_id)
    if current_user.role == "admin":
        pass
    elif current_user.role == "parent":
        if payment.student_id not in [child.id for child in parent_children(current_user)]: abort(403)
    elif current_user.role == "eleve":
        if current_user.student_id != payment.student_id: abort(403)
    else:
        abort(403)
    if payment.statut != "Payé":
        abort(400, description="Un reçu définitif est disponible uniquement pour un paiement marqué Payé.")
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        abort(503, description="ReportLab est absent. Installez requirements.txt.")
    buffer = BytesIO()
    green = colors.HexColor("#075b49")
    gold = colors.HexColor("#b58b26")
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=22*mm, leftMargin=22*mm,
                            topMargin=25*mm, bottomMargin=25*mm, title="Reçu de paiement scolaire")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReceiptSchool", parent=styles["Title"],
                              fontSize=20, textColor=green, alignment=1, spaceAfter=5))
    story = [Paragraph("ECOLE LA BONTE", styles["ReceiptSchool"]),
             Paragraph("LUBUMBASHI - RECU DE PAIEMENT SCOLAIRE", styles["Heading2"]), Spacer(1, 18)]
    rows = [
        ["NUMERO DU RECU", "REC-{:06d}".format(payment.id)],
        ["DATE", (payment.date_paiement or date.today()).strftime("%d/%m/%Y")],
        ["ELEVE", payment.eleve.nom],
        ["MATRICULE", payment.eleve.matricule],
        ["MOTIF", payment.libelle],
        ["MONTANT RECU", "{:,.0f} {}".format(payment.montant, payment.devise).replace(",", " ")],
        ["STATUT", payment.statut]
    ]
    table = Table(rows, colWidths=[55*mm, 105*mm], rowHeights=[15*mm]*len(rows))
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#edf3ef")),
        ("TEXTCOLOR",(0,0),(0,-1),green),("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
        ("GRID",(0,0),(-1,-1),.6,colors.HexColor("#c8d5cc")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),10),
        ("RIGHTPADDING",(0,0),(-1,-1),10),("FONTSIZE",(0,0),(-1,-1),10),
        ("BOX",(0,0),(-1,-1),1,gold)
    ]))
    story.extend([table, Spacer(1, 35),
                  Paragraph("Signature et cachet de la caisse : ______________________________", styles["Normal"])])
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True,
                     download_name="recu-REC-{:06d}.pdf".format(payment.id))


@app.route("/frais", methods=["GET", "POST"])
@login_required
def school_fees():
    admin = current_user.role == "admin"
    if request.method == "POST":
        if not admin: abort(403)
        action = request.form.get("action", "")
        if action == "create_fee":
            classe = request.form.get("classe", "").strip()
            year = request.form.get("annee_academique", "").strip()
            label = request.form.get("libelle", "").strip()
            currency = request.form.get("devise", "CDF").upper()
            try:
                amount = int(request.form.get("montant", ""))
            except (TypeError, ValueError):
                abort(400)
            if not classe or not year or len(year) > 20 or not label or amount <= 0 or currency not in ("CDF", "USD"):
                abort(400)
            existing = SchoolFee.query.filter_by(classe=classe, annee_academique=year,
                                                  libelle=label, devise=currency).first()
            if existing:
                flash("Ces frais existent déjà pour cette classe et cette année.", "warning")
            else:
                db.session.add(SchoolFee(classe=classe, annee_academique=year,
                                         libelle=label, montant=amount, devise=currency))
                db.session.commit()
                flash("Frais de classe créés.", "success")
            return redirect(url_for("school_fees"))
        if action == "record_payment":
            try:
                student_id = int(request.form.get("student_id", ""))
                fee_id = int(request.form.get("fee_id", ""))
                amount = int(request.form.get("montant", ""))
            except (TypeError, ValueError):
                abort(400)
            student = db.session.get(Student, student_id)
            fee = db.session.get(SchoolFee, fee_id)
            if not student or not fee or student.classe.strip().casefold() != fee.classe.strip().casefold() or amount <= 0:
                abort(400, description="Élève, frais ou montant invalide.")
            already_paid = db.session.query(db.func.coalesce(db.func.sum(FeePayment.montant), 0)).filter_by(fee_id=fee.id, student_id=student.id).scalar()
            remaining = fee.montant - int(already_paid or 0)
            if amount > remaining:
                abort(400, description="Le versement dépasse le solde restant.")
            versement = FeePayment(fee_id=fee.id, student_id=student.id, montant=amount,
                                   reference=request.form.get("reference", "").strip()[:80] or None)
            db.session.add(versement)
            db.session.commit()
            flash("Versement enregistré. Vous pouvez imprimer le reçu PDF.", "success")
            return redirect(url_for("school_fees"))
        abort(400)
    year = request.args.get("annee", "2026-2027").strip()[:20]
    if admin:
        students = Student.query.order_by(Student.nom).all()
        fees = SchoolFee.query.filter_by(annee_academique=year).order_by(SchoolFee.classe, SchoolFee.libelle).all()
        payments_query = FeePayment.query.join(Student).join(SchoolFee).filter(SchoolFee.annee_academique == year)
    elif current_user.role == "parent":
        students = parent_children(current_user)
        student_ids = [s.id for s in students]
        fees = SchoolFee.query.filter_by(annee_academique=year).all()
        payments_query = FeePayment.query.join(SchoolFee).filter(SchoolFee.annee_academique == year, FeePayment.student_id.in_(student_ids)) if student_ids else FeePayment.query.filter(db.false())
    elif current_user.role == "eleve" and current_user.student_id:
        student = db.session.get(Student, current_user.student_id)
        students = [student] if student else []
        fees = SchoolFee.query.filter_by(annee_academique=year).all()
        payments_query = FeePayment.query.join(SchoolFee).filter(SchoolFee.annee_academique == year, FeePayment.student_id == current_user.student_id)
    else:
        abort(403)
    soldes = []
    for student in students:
        for fee in fees:
            if student.classe.strip().casefold() != fee.classe.strip().casefold():
                continue
            paid = db.session.query(db.func.coalesce(db.func.sum(FeePayment.montant), 0)).filter_by(
                fee_id=fee.id, student_id=student.id).scalar()
            paid = int(paid or 0)
            soldes.append({"eleve": student, "frais": fee, "total": fee.montant,
                           "paye": paid, "reste": max(0, fee.montant - paid)})
    versements = payments_query.order_by(FeePayment.date_paiement.desc(), FeePayment.id.desc()).all()
    return page("Frais par classe", FEES, admin=admin, students=students,
                frais=fees, soldes=soldes, versements=versements, annee=year)


@app.route("/frais/versement/<int:payment_id>/recu.pdf")
@login_required
def fee_payment_receipt(payment_id):
    versement = db.session.get(FeePayment, payment_id)
    if not versement: abort(404)
    if current_user.role == "admin":
        pass
    elif current_user.role == "parent":
        if versement.student_id not in [child.id for child in parent_children(current_user)]: abort(403)
    elif current_user.role == "eleve":
        if current_user.student_id != versement.student_id: abort(403)
    else:
        abort(403)
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        abort(503, description="ReportLab est absent. Installez requirements.txt.")
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=22*mm, leftMargin=22*mm,
                            topMargin=25*mm, bottomMargin=25*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="FeeReceiptTitle", parent=styles["Title"],
                              textColor=colors.HexColor("#075b49"), alignment=1, fontSize=20))
    rows = [
        ["REÇU N°", "FRAIS-{:06d}".format(versement.id)],
        ["DATE", versement.date_paiement.strftime("%d/%m/%Y")],
        ["ÉLÈVE", versement.eleve.nom],
        ["MATRICULE", versement.eleve.matricule],
        ["CLASSE", versement.eleve.classe],
        ["ANNÉE ACADÉMIQUE", versement.frais.annee_academique],
        ["MOTIF", versement.frais.libelle],
        ["VERSEMENT REÇU", "{:,.0f} {}".format(versement.montant, versement.frais.devise).replace(",", " ")],
        ["RÉFÉRENCE", versement.reference or "-"]
    ]
    table = Table(rows, colWidths=[55*mm, 105*mm], rowHeights=[13*mm]*len(rows))
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#edf3ef")),
        ("TEXTCOLOR",(0,0),(0,-1),colors.HexColor("#075b49")),
        ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
        ("GRID",(0,0),(-1,-1),.6,colors.HexColor("#c8d5cc")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),9),
        ("FONTSIZE",(0,0),(-1,-1),10)
    ]))
    story = [Paragraph("ÉCOLE LA BONTÉ", styles["FeeReceiptTitle"]),
             Paragraph("LUBUMBASHI · REÇU DE VERSEMENT", styles["Heading2"]),
             Spacer(1, 16), table, Spacer(1, 35),
             Paragraph("Signature et cachet de la caisse : ______________________________", styles["Normal"])]
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True,
                     download_name="recu-frais-{:06d}.pdf".format(versement.id))


@app.route("/admission", methods=["GET", "POST"])
def admission_public():
    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        classe = request.form.get("classe", "").strip()
        promotion = request.form.get("promotion", "").strip()
        year = request.form.get("annee_academique", "").strip()
        phone = request.form.get("telephone_parent", "").strip()
        photo = request.files.get("photo")
        try:
            faculty_id = int(request.form.get("faculty_id", ""))
            program_id = int(request.form.get("program_id", ""))
        except (TypeError, ValueError):
            abort(400)
        faculty = db.session.get(FacultyCatalog, faculty_id)
        program = db.session.get(ProgramCatalog, program_id)
        if not all([nom, classe, promotion, year, photo, photo.filename, faculty, program]) or program.faculty_id != faculty.id or len(year) > 20:
            flash("Vérifiez les champs obligatoires et la faculté/filière choisies.", "error")
            return page("Demande d'admission", ADMISSION_FORM, faculties=FacultyCatalog.query.order_by(FacultyCatalog.code).all())
        ext = photo.filename.rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED:
            flash("Format photo accepté : JPG, PNG ou WEBP.", "error")
            return page("Demande d'admission", ADMISSION_FORM, faculties=FacultyCatalog.query.order_by(FacultyCatalog.code).all())
        filename = datetime.utcnow().strftime("%Y%m%d%H%M%S%f") + "_" + secure_filename(photo.filename)
        photo.save(UPLOADS / filename)
        application = AdmissionApplication(nom=nom, photo=filename, faculty_id=faculty.id,
            program_id=program.id, classe=classe, promotion=promotion, annee_academique=year,
            telephone_parent=phone or None)
        db.session.add(application)
        db.session.commit()
        flash("Demande reçue. L'administration étudiera votre dossier.", "success")
        return redirect(url_for("admission_public"))
    return page("Demande d'admission", ADMISSION_FORM,
                faculties=FacultyCatalog.query.order_by(FacultyCatalog.code).all())


@app.route("/admissions", methods=["GET", "POST"])
@admin_only
def admissions():
    if request.method == "POST":
        try:
            application_id = int(request.form.get("application_id", ""))
        except (TypeError, ValueError):
            abort(400)
        application = db.get_or_404(AdmissionApplication, application_id)
        action = request.form.get("action")
        if application.statut != "En attente" or action not in ("accepter", "refuser"):
            abort(400)
        if action == "refuser":
            application.statut = "Refusée"
            db.session.commit()
            flash("Demande refusée.", "success")
        else:
            faculty, program = application.faculty, application.program
            if not faculty or not program or program.faculty_id != faculty.id:
                abort(400, description="Le catalogue faculté/filière de cette demande est invalide.")
            try:
                academic_year = int(application.annee_academique[:4])
            except ValueError:
                abort(400, description="L'année académique doit commencer par une année à quatre chiffres.")
            matricule = generer_matricule(academic_year, faculty.code, program.code)
            student = Student(matricule=matricule, annee_inscription=academic_year,
                code_faculte=faculty.code, code_filiere=program.code, nom=application.nom,
                photo=application.photo, faculte=faculty.nom, filiere=program.nom,
                promotion=application.promotion, classe=application.classe)
            db.session.add(student)
            db.session.flush()
            db.session.add(Enrollment(student_id=student.id, annee_academique=application.annee_academique,
                promotion=application.promotion, classe=application.classe, statut="Admis"))
            application.statut = "Acceptée"
            application.student_id = student.id
            db.session.commit()
            flash("Admission acceptée. Matricule attribué : " + matricule, "success")
        return redirect(url_for("admissions"))
    return page("Admissions", ADMISSIONS,
                demandes=AdmissionApplication.query.order_by(AdmissionApplication.cree_le.desc()).all())


@app.route("/reinscriptions", methods=["GET", "POST"])
@admin_only
def reinscriptions():
    if request.method == "POST":
        try:
            student_id = int(request.form.get("student_id", ""))
        except (TypeError, ValueError):
            abort(400)
        student = db.session.get(Student, student_id)
        year = request.form.get("annee_academique", "").strip()
        promotion = request.form.get("promotion", "").strip()
        classe = request.form.get("classe", "").strip()
        if not student or not year or len(year) > 20 or not promotion or not classe:
            abort(400)
        if Enrollment.query.filter_by(student_id=student.id, annee_academique=year).first():
            flash("Cet élève est déjà inscrit pour cette année académique.", "warning")
        else:
            enrollment = Enrollment(student_id=student.id, annee_academique=year,
                                    promotion=promotion, classe=classe, statut="Réinscrit")
            student.annee_inscription = int(year[:4]) if year[:4].isdigit() else student.annee_inscription
            student.promotion, student.classe = promotion, classe
            db.session.add(enrollment)
            db.session.commit()
            flash("Réinscription enregistrée.", "success")
        return redirect(url_for("reinscriptions"))
    return page("Réinscriptions", REENROLLMENTS,
        students=Student.query.order_by(Student.nom).all(),
        records=Enrollment.query.join(Student).order_by(Enrollment.date_inscription.desc(), Enrollment.id.desc()).all())


@app.route("/eleves/<int:sid>/inscription.pdf")
@admin_only
def student_enrollment_pdf(sid):
    student = db.get_or_404(Student, sid)
    enrollment = Enrollment.query.filter_by(student_id=sid).order_by(Enrollment.date_inscription.desc(), Enrollment.id.desc()).first()
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        abort(503, description="ReportLab est absent. Installez requirements.txt.")
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=22*mm, leftMargin=22*mm,
                            topMargin=25*mm, bottomMargin=25*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="EnrollmentTitle", parent=styles["Title"],
                              textColor=colors.HexColor("#075b49"), alignment=1, fontSize=20))
    year = enrollment.annee_academique if enrollment else str(student.annee_inscription or "")
    rows = [
        ["NOM COMPLET", student.nom], ["MATRICULE", student.matricule],
        ["FACULTÉ", student.faculte], ["FILIÈRE", student.filiere],
        ["PROMOTION", enrollment.promotion if enrollment else student.promotion],
        ["CLASSE", enrollment.classe if enrollment else student.classe],
        ["ANNÉE ACADÉMIQUE", year],
        ["DATE DU DOCUMENT", date.today().strftime("%d/%m/%Y")]
    ]
    table = Table(rows, colWidths=[55*mm, 105*mm], rowHeights=[14*mm]*len(rows))
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#edf3ef")),
        ("TEXTCOLOR",(0,0),(0,-1),colors.HexColor("#075b49")),
        ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
        ("GRID",(0,0),(-1,-1),.6,colors.HexColor("#c8d5cc")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),9),
        ("FONTSIZE",(0,0),(-1,-1),10)
    ]))
    story = [Paragraph("ÉCOLE LA BONTÉ", styles["EnrollmentTitle"]),
             Paragraph("LUBUMBASHI · ATTESTATION D'INSCRIPTION", styles["Heading2"]),
             Spacer(1, 18), table, Spacer(1, 35),
             Paragraph("La Direction", styles["Normal"]),
             Spacer(1, 25),
             Paragraph("Signature et cachet : ______________________________________", styles["Normal"])]
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True,
                     download_name="inscription-" + re.sub(r"[^A-Za-z0-9_-]+", "-", student.matricule) + ".pdf")

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
    role = current_user.role
    if role not in ("admin", "enseignant"):
        abort(403)

    admin = role == "admin"
    classes_autorisees = []
    if not admin:
        classes_autorisees = [row[0] for row in
            db.session.query(TeacherAssignment.classe).filter_by(
                teacher_id=current_user.id
            ).distinct().all()]
        if not classes_autorisees:
            flash("Aucune classe ne vous est affectée. Contactez l'administration.", "warning")

    if request.method == "POST":
        try:
            student_id = int(request.form.get("student_id", ""))
            jour = datetime.strptime(request.form.get("jour", ""), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            flash("Sélectionnez un élève et une date valides.", "error")
            return redirect(url_for("presences"))

        student = db.session.get(Student, student_id)
        statut = request.form.get("statut", "")
        motif = request.form.get("motif", "").strip()
        if not student:
            flash("L'élève sélectionné n'existe pas.", "error")
        elif not admin and student.classe not in classes_autorisees:
            abort(403)
        elif statut not in ("Présent", "Absent", "Retard"):
            flash("Statut de présence invalide.", "error")
        else:
            record = Attendance(student_id=student.id, jour=jour,
                                statut=statut, motif=motif)
            db.session.add(record)
            db.session.commit()
            flash("Présence enregistrée.", "success")
        return redirect(url_for("presences"))

    student_query = Student.query
    record_query = Attendance.query.join(Student)
    if not admin:
        if classes_autorisees:
            student_query = student_query.filter(Student.classe.in_(classes_autorisees))
            record_query = record_query.filter(Student.classe.in_(classes_autorisees))
        else:
            student_query = student_query.filter(db.false())
            record_query = record_query.filter(db.false())

    students = student_query.order_by(Student.classe, Student.nom).all()
    records = record_query.order_by(
        Attendance.jour.desc(), Attendance.id.desc()
    ).limit(150).all()
    template = """
    <section class='panel'><h2>Enregistrer une présence ou une absence</h2>
    {% if not admin and not classes_autorisees %}<p>Aucune classe ne vous est affectée. Vous ne pouvez pas enregistrer de présence.</p>{% endif %}
    <form method='post' class='inline-form'>
    <label>Élève<select name='student_id' required {% if not students %}disabled{% endif %}>{% for s in students %}<option value='{{ s.id }}'>{{ s.classe }} · {{ s.nom }} · {{ s.matricule }}</option>{% endfor %}</select></label>
    <label>Date<input type='date' name='jour' value='{{ today }}' required></label>
    <label>Statut<select name='statut'><option>Présent</option><option>Absent</option><option>Retard</option></select></label>
    <label>Motif<input name='motif'></label>
    <button class='btn primary' {% if not students %}disabled{% endif %}>Enregistrer</button></form></section>
    <section class='panel'><h2>Registre des présences</h2>
    <div class='table-wrap'><table><tr><th>Date</th><th>Classe</th><th>Élève</th><th>Matricule</th><th>Statut</th><th>Motif</th></tr>
    {% for r in records %}<tr><td>{{ r.jour.strftime('%d/%m/%Y') }}</td><td>{{ r.eleve.classe }}</td><td>{{ r.eleve.nom }}</td><td>{{ r.eleve.matricule }}</td><td>{{ r.statut }}</td><td>{{ r.motif }}</td></tr>
    {% else %}<tr><td colspan='6'>Aucun relevé pour les classes accessibles.</td></tr>{% endfor %}</table></div></section>
    """
    return page("Présences & absences", template, admin=admin,
        classes_autorisees=classes_autorisees, students=students,
        records=records, today=date.today().isoformat())

@app.route("/assistant", methods=["GET","POST"])
@login_required
def assistant():
    template="""<section class='panel'><h2>Assistant scolaire — recherche dans les dossiers</h2><p>Recherchez un matricule ou un nom. L'assistant interroge la base de données selon vos autorisations.</p><form method='post' class='search'><input name='q' placeholder='Matricule officiel ou nom' required><button class='btn primary'>Rechercher</button></form>{% if s %}<div class='profile'><img src='/static/uploads/{{ s.photo }}'><div><b>{{ s.nom }}</b><p>Matricule : {{ s.matricule }}</p><p>{{ s.faculte }} · {{ s.filiere }} · {{ s.promotion }}</p><b>Moyenne : {{ s.moyenne }}/20</b></div></div><h3>Parcours annuel</h3><div class='table-wrap'><table><tr><th>Année</th><th>Promotion</th><th>Faculté / Filière</th><th>Cours</th><th>Crédits</th><th>Note</th></tr>{% for h in s.historique %}<tr><td>{{ h.annee_academique }}</td><td>{{ h.promotion }}</td><td>{{ h.faculte }} / {{ h.filiere }}</td><td>{{ h.cours }}</td><td>{{ h.credits }}</td><td>{{ h.note if h.note is not none else h.decision }}</td></tr>{% else %}<tr><td colspan='6'>Aucun historique annuel archivé pour ce dossier.</td></tr>{% endfor %}</table></div>{% elif q %}<p>Aucun dossier correspondant.</p>{% endif %}</section>"""
    q=request.form.get("q","").strip() if request.method=="POST" else ""
    student=None
    if q:
        if current_user.role in ("admin","enseignant"):
            student=Student.query.filter(db.or_(Student.matricule==q,Student.nom.ilike("%"+q+"%"))).first()
        elif current_user.role == "parent":
            children=parent_children(current_user)
            student=next((child for child in children if q==child.matricule or q.lower() in child.nom.lower()),None)
        elif current_user.student_id:
            own=db.session.get(Student,current_user.student_id)
            if own and (q==own.matricule or q.lower() in own.nom.lower()): student=own
    return page("Assistant scolaire",template,s=student,q=q)

@app.route("/comptes", methods=["GET","POST"])
@admin_only
def comptes():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower()
        role=request.form.get("role","eleve")
        allowed_roles=("eleve","parent","enseignant","admin")
        try:
            linked_ids=[int(value) for value in request.form.getlist("student_ids") if value]
            sid_raw=request.form.get("student_id","").strip()
            sid=int(sid_raw) if sid_raw else None
        except ValueError:
            flash("Sélection invalide pour le dossier élève.","error")
            return redirect(url_for("comptes"))
        if not request.form.get("nom","").strip() or not email or not request.form.get("password","") or role not in allowed_roles:
            flash("Complétez les champs obligatoires et choisissez un rôle valide.","error")
        elif len(request.form["password"]) < 10:
            flash("Le mot de passe provisoire doit contenir au moins 10 caractères.","error")
        elif User.query.filter_by(email=email).first():
            flash("Cette adresse e-mail existe déjà.","error")
        elif any(not db.session.get(Student, student_id) for student_id in linked_ids) or (sid and not db.session.get(Student,sid)):
            flash("Un des dossiers élèves sélectionnés n'existe pas.","error")
        elif role != "parent" and linked_ids:
            flash("La sélection multiple d'enfants est réservée aux comptes parents.","error")
        else:
            u=User(nom=request.form["nom"].strip(),email=email,role=role)
            u.set_password(request.form["password"])
            u.student_id=sid if role=="eleve" else None
            if role=="parent":
                u.enfants=[db.session.get(Student, student_id) for student_id in sorted(set(linked_ids))]
                if sid:
                    legacy=db.session.get(Student,sid)
                    if legacy not in u.enfants: u.enfants.append(legacy)
            db.session.add(u); db.session.commit()
            flash("Compte créé et liens familiaux enregistrés.","success")
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


@app.route("/personnel", methods=["GET", "POST"])
@admin_only
def personnel():
    if request.method == "POST":
        action = request.form.get("action", "personnel")
        if action == "personnel":
            nom = request.form.get("nom", "").strip()
            fonction = request.form.get("fonction", "").strip()
            email = request.form.get("email", "").strip().lower() or None
            telephone = request.form.get("telephone", "").strip() or None
            statut = request.form.get("statut", "Actif")
            user_raw = request.form.get("user_id", "").strip()
            user = db.session.get(User, int(user_raw)) if user_raw.isdigit() else None
            if not nom or not fonction or statut not in ("Actif", "Suspendu", "Sorti"):
                flash("Nom, fonction ou statut invalide.", "error")
            elif user_raw and (not user or user.role not in ("enseignant", "admin") or Personnel.query.filter_by(user_id=user.id).first()):
                flash("Ce compte n'est pas valide ou est déjà lié à une fiche.", "error")
            else:
                db.session.add(Personnel(nom=nom, fonction=fonction, email=email,
                    telephone=telephone, statut=statut, user_id=user.id if user else None))
                db.session.commit()
                flash("Fiche du membre du personnel créée.", "success")
        elif action == "contract":
            try:
                personnel_id = int(request.form.get("personnel_id", ""))
                salaire = int(request.form.get("salaire_base", ""))
                debut = date.fromisoformat(request.form.get("date_debut", ""))
                fin_raw = request.form.get("date_fin", "").strip()
                fin = date.fromisoformat(fin_raw) if fin_raw else None
            except (ValueError, TypeError):
                flash("Vérifiez les dates et le salaire du contrat.", "error")
                return redirect(url_for("personnel"))
            p = db.session.get(Personnel, personnel_id)
            devise = request.form.get("devise", "CDF").upper()
            type_contrat = request.form.get("type_contrat", "").strip()
            if not p or not type_contrat or salaire <= 0 or devise not in ("CDF", "USD") or (fin and fin < debut):
                flash("Contrat invalide : salaire positif, devise et dates cohérentes obligatoires.", "error")
            else:
                StaffContract.query.filter_by(personnel_id=p.id, devise=devise, statut="Actif").update({"statut":"Terminé"})
                db.session.add(StaffContract(personnel_id=p.id, type_contrat=type_contrat,
                    date_debut=debut, date_fin=fin, salaire_base=salaire, devise=devise))
                db.session.commit()
                flash("Contrat enregistré.", "success")
        elif action == "advance":
            try:
                personnel_id = int(request.form.get("personnel_id", ""))
                montant = int(request.form.get("montant", ""))
                date_avance = date.fromisoformat(request.form.get("date_avance", ""))
            except (ValueError, TypeError):
                flash("Montant ou date d'avance invalide.", "error")
                return redirect(url_for("personnel"))
            p = db.session.get(Personnel, personnel_id)
            devise = request.form.get("devise", "CDF").upper()
            motif = request.form.get("motif", "").strip()
            if not p or montant <= 0 or devise not in ("CDF", "USD") or not motif:
                flash("L'avance doit avoir un montant positif, une devise et un motif.", "error")
            else:
                db.session.add(StaffAdvance(personnel_id=p.id, montant=montant, devise=devise,
                    date_avance=date_avance, motif=motif))
                db.session.commit()
                flash("Avance enregistrée. Elle sera déduite lors de la paie.", "success")
        elif action == "payroll":
            try:
                personnel_id = int(request.form.get("personnel_id", ""))
                salaire = int(request.form.get("salaire_base", ""))
                deductions = int(request.form.get("deductions") or 0)
                date_paiement = date.fromisoformat(request.form.get("date_paiement", ""))
            except (ValueError, TypeError):
                flash("Vérifiez le salaire, les retenues et la date de paiement.", "error")
                return redirect(url_for("personnel"))
            p = db.session.get(Personnel, personnel_id)
            periode = request.form.get("periode", "").strip()
            devise = request.form.get("devise", "CDF").upper()
            contrats = StaffContract.query.filter_by(personnel_id=personnel_id, devise=devise, statut="Actif").order_by(StaffContract.date_debut.desc()).all() if p else []
            if not salaire and contrats:
                salaire = contrats[0].salaire_base
            avances_rows = StaffAdvance.query.filter_by(personnel_id=personnel_id, devise=devise, statut="À retenir").all() if p else []
            avances = sum(x.montant for x in avances_rows)
            net = salaire - avances - deductions
            if not p or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", periode) or salaire <= 0 or deductions < 0 or devise not in ("CDF", "USD") or net < 0:
                flash("Paie invalide : période AAAA-MM, salaire positif et net non négatif requis.", "error")
            elif PayrollRecord.query.filter_by(personnel_id=p.id, periode=periode, devise=devise).first():
                flash("Une paie existe déjà pour cette période et cette devise.", "error")
            else:
                record = PayrollRecord(personnel_id=p.id, periode=periode, salaire_base=salaire,
                    avances=avances, deductions=deductions, net_a_payer=net, devise=devise,
                    date_paiement=date_paiement, reference=request.form.get("reference", "").strip() or None)
                db.session.add(record)
                for advance in avances_rows:
                    advance.statut = "Déduite"
                db.session.commit()
                flash("Paie enregistrée. Le bulletin de paie PDF est disponible.", "success")
        return redirect(url_for("personnel"))
    people = Personnel.query.order_by(Personnel.nom).all()
    contracts = StaffContract.query.order_by(StaffContract.date_debut.desc()).all()
    advances = StaffAdvance.query.filter_by(statut="À retenir").order_by(StaffAdvance.date_avance.desc()).all()
    payrolls = PayrollRecord.query.order_by(PayrollRecord.date_paiement.desc()).all()
    linked_users = User.query.filter(User.role.in_(("enseignant", "admin"))).order_by(User.nom).all()
    template = """
    <section class='panel'><h2>Ajouter un membre du personnel</h2>
    <form method='post' class='form-grid'><input type='hidden' name='action' value='personnel'>
      <label>Nom complet *<input name='nom' required></label><label>Fonction *<input name='fonction' required placeholder='Enseignant, comptable, secrétaire…'></label>
      <label>Téléphone<input name='telephone'></label><label>E-mail<input type='email' name='email'></label>
      <label>Compte lié (facultatif)<select name='user_id'><option value=''>Aucun compte</option>{% for u in linked_users %}<option value='{{ u.id }}'>{{ u.nom }} · {{ u.role }}</option>{% endfor %}</select></label>
      <label>Statut<select name='statut'><option>Actif</option><option>Suspendu</option><option>Sorti</option></select></label>
      <button class='btn primary'>Créer la fiche</button></form></section>
    <section class='panel'><h2>Enregistrer un contrat</h2><form method='post' class='form-grid'><input type='hidden' name='action' value='contract'>
      <label>Personnel<select name='personnel_id' required>{% for p in people %}<option value='{{ p.id }}'>{{ p.nom }} · {{ p.fonction }}</option>{% endfor %}</select></label>
      <label>Type de contrat<input name='type_contrat' required placeholder='CDI, CDD, prestation…'></label>
      <label>Date de début<input type='date' name='date_debut' required></label><label>Date de fin (facultative)<input type='date' name='date_fin'></label>
      <label>Salaire de base<input type='number' name='salaire_base' min='1' required></label><label>Devise<select name='devise'><option>CDF</option><option>USD</option></select></label>
      <button class='btn primary' {% if not people %}disabled{% endif %}>Enregistrer le contrat</button></form></section>
    <section class='panel'><h2>Enregistrer une avance</h2><form method='post' class='form-grid'><input type='hidden' name='action' value='advance'>
      <label>Personnel<select name='personnel_id' required>{% for p in people %}<option value='{{ p.id }}'>{{ p.nom }}</option>{% endfor %}</select></label>
      <label>Montant<input type='number' name='montant' min='1' required></label><label>Devise<select name='devise'><option>CDF</option><option>USD</option></select></label>
      <label>Date<input type='date' name='date_avance' required></label><label>Motif<input name='motif' required></label>
      <button class='btn primary' {% if not people %}disabled{% endif %}>Enregistrer l'avance</button></form></section>
    <section class='panel'><h2>Préparer une paie</h2><p>Les avances non encore retenues sont déduites automatiquement dans leur devise. Les devises CDF et USD ne sont jamais converties.</p>
    <form method='post' class='form-grid'><input type='hidden' name='action' value='payroll'>
      <label>Personnel<select name='personnel_id' required>{% for p in people %}<option value='{{ p.id }}'>{{ p.nom }}</option>{% endfor %}</select></label>
      <label>Période (AAAA-MM)<input name='periode' pattern='[0-9]{4}-(0[1-9]|1[0-2])' placeholder='2026-11' required></label>
      <label>Salaire de base (laisser 0 pour le contrat)<input type='number' name='salaire_base' min='0' value='0' required></label>
      <label>Devise<select name='devise'><option>CDF</option><option>USD</option></select></label>
      <label>Autres déductions<input type='number' name='deductions' min='0' value='0'></label>
      <label>Date de paiement<input type='date' name='date_paiement' required></label><label>Référence<input name='reference'></label>
      <button class='btn primary' {% if not people %}disabled{% endif %}>Valider la paie</button></form></section>
    <section class='panel'><h2>Personnel</h2><div class='table-wrap'><table><tr><th>Nom</th><th>Fonction</th><th>Contact</th><th>Statut</th><th>Contrats</th></tr>
    {% for p in people %}<tr><td>{{ p.nom }}</td><td>{{ p.fonction }}</td><td>{{ p.telephone or '—' }}<small class='sub'>{{ p.email or '' }}</small></td><td>{{ p.statut }}</td><td>{{ p.contrats|length }}</td></tr>{% else %}<tr><td colspan='5'>Aucun membre enregistré.</td></tr>{% endfor %}</table></div></section>
    <section class='panel'><h2>Contrats</h2><div class='table-wrap'><table><tr><th>Personnel</th><th>Type</th><th>Période</th><th>Salaire</th><th>Statut</th></tr>
    {% for c in contracts %}<tr><td>{{ c.personnel.nom }}</td><td>{{ c.type_contrat }}</td><td>{{ c.date_debut }} → {{ c.date_fin or 'Indéterminée' }}</td><td>{{ c.salaire_base }} {{ c.devise }}</td><td>{{ c.statut }}</td></tr>{% else %}<tr><td colspan='5'>Aucun contrat.</td></tr>{% endfor %}</table></div></section>
    <section class='panel'><h2>Avances à retenir</h2><div class='table-wrap'><table><tr><th>Personnel</th><th>Date</th><th>Motif</th><th>Montant</th></tr>
    {% for a in advances %}<tr><td>{{ a.personnel.nom }}</td><td>{{ a.date_avance }}</td><td>{{ a.motif }}</td><td>{{ a.montant }} {{ a.devise }}</td></tr>{% else %}<tr><td colspan='4'>Aucune avance en attente.</td></tr>{% endfor %}</table></div></section>
    <section class='panel'><h2>Historique des paies</h2><div class='table-wrap'><table><tr><th>Personnel</th><th>Période</th><th>Salaire</th><th>Avances</th><th>Déductions</th><th>Net</th><th>Devise</th><th>Bulletin</th></tr>
    {% for r in payrolls %}<tr><td>{{ r.personnel.nom }}</td><td>{{ r.periode }}</td><td>{{ r.salaire_base }}</td><td>{{ r.avances }}</td><td>{{ r.deductions }}</td><td><b>{{ r.net_a_payer }}</b></td><td>{{ r.devise }}</td><td><a href='/paie/{{ r.id }}/bulletin.pdf'>PDF</a></td></tr>{% else %}<tr><td colspan='8'>Aucune paie enregistrée.</td></tr>{% endfor %}</table></div></section>
    """
    return page("Personnel & paie", template, people=people, contracts=contracts,
                advances=advances, payrolls=payrolls, linked_users=linked_users)


@app.route("/mon-salaire")
@login_required
def mon_salaire():
    if current_user.role not in ("enseignant", "admin"):
        abort(403)
    fiche = Personnel.query.filter_by(user_id=current_user.id).first()
    if not fiche:
        return page("Mon salaire", "<section class='panel'>Aucune fiche de personnel n'est liée à votre compte. Contactez l'administration.</section>")
    return page("Mon salaire", """<section class='panel'><h2>Mes bulletins de paie</h2><div class='table-wrap'><table>
    <tr><th>Période</th><th>Salaire de base</th><th>Avances</th><th>Déductions</th><th>Net</th><th>Devise</th><th>PDF</th></tr>
    {% for r in payrolls %}<tr><td>{{ r.periode }}</td><td>{{ r.salaire_base }}</td><td>{{ r.avances }}</td><td>{{ r.deductions }}</td><td>{{ r.net_a_payer }}</td><td>{{ r.devise }}</td><td><a href='/paie/{{ r.id }}/bulletin.pdf'>Télécharger</a></td></tr>{% else %}<tr><td colspan='7'>Aucun bulletin disponible.</td></tr>{% endfor %}</table></div></section>""",
        payrolls=PayrollRecord.query.filter_by(personnel_id=fiche.id).order_by(PayrollRecord.periode.desc()).all())


@app.route("/paie/<int:payroll_id>/bulletin.pdf")
@login_required
def payroll_pdf(payroll_id):
    record = db.get_or_404(PayrollRecord, payroll_id)
    if current_user.role != "admin":
        fiche = Personnel.query.filter_by(user_id=current_user.id).first() if current_user.role == "enseignant" else None
        if not fiche or record.personnel_id != fiche.id:
            abort(403)
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        abort(503, description="ReportLab est absent. Installez requirements.txt.")
    buffer = BytesIO()
    green = colors.HexColor("#075b49")
    gold = colors.HexColor("#d6ae45")
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=22*mm, leftMargin=22*mm, topMargin=22*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    story = [Paragraph("ÉCOLE LA BONTÉ", ParagraphStyle("School", parent=styles["Title"], textColor=green, alignment=1)),
        Paragraph("LUBUMBASHI · BULLETIN DE PAIE", ParagraphStyle("Sub", parent=styles["Normal"], alignment=1, textColor=colors.HexColor("#777777"))),
        Spacer(1, 18)]
    data = [["Membre du personnel", record.personnel.nom], ["Fonction", record.personnel.fonction],
        ["Période", record.periode], ["Date de paiement", record.date_paiement.strftime("%d/%m/%Y")],
        ["Salaire de base", f"{record.salaire_base:,} {record.devise}"],
        ["Avances retenues", f"{record.avances:,} {record.devise}"],
        ["Autres déductions", f"{record.deductions:,} {record.devise}"],
        ["NET À PAYER", f"{record.net_a_payer:,} {record.devise}"]]
    table = Table(data, colWidths=[75*mm, 90*mm])
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(0,-1),colors.HexColor("#eaf1ec")),
        ("TEXTCOLOR",(0,0),(0,-1),green),("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
        ("GRID",(0,0),(-1,-1),.5,colors.HexColor("#cbd5ce")),("PADDING",(0,0),(-1,-1),9),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#f8f1d8")),("TEXTCOLOR",(0,-1),(-1,-1),green),
        ("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold")]))
    story += [table, Spacer(1, 28), Paragraph("Signature du bénéficiaire : __________________________", styles["Normal"]),
        Spacer(1, 18), Paragraph("Signature et cachet de la direction : __________________________", styles["Normal"])]
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True,
        download_name="bulletin-paie-{}-{}.pdf".format(re.sub(r"[^A-Za-z0-9_-]+","-",record.personnel.nom), record.periode))


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
