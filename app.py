import os
from datetime import datetime, date
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
    db_url = db_url.replace("postgres://", "postgresql://", 1)
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
    nombre_cours = db.Column(db.Integer, default=0)
    credits = db.Column(db.Integer, default=0)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.relationship("Grade", cascade="all,delete-orphan", backref="eleve")
    paiements = db.relationship("Payment", cascade="all,delete-orphan", backref="eleve")
    @property
    def moyenne(self):
        return round(sum(n.note for n in self.notes) / len(self.notes), 2) if self.notes else 0

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    cours = db.Column(db.String(140), nullable=False)
    note = db.Column(db.Float, nullable=False)
    periode = db.Column(db.String(80), default="Trimestre 1")

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    libelle = db.Column(db.String(140), nullable=False)
    montant = db.Column(db.Integer, nullable=False)
    statut = db.Column(db.String(20), default="En attente")
    date_paiement = db.Column(db.Date, nullable=True)

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

@login.user_loader
def load_user(uid): return db.session.get(User, int(uid))

def admin_only(fn):
    @wraps(fn)
    @login_required
    def wrapped(*a, **kw):
        if current_user.role != "admin": abort(403)
        return fn(*a, **kw)
    return wrapped

def matricule_suivant():
    annee = datetime.now().year
    dernier = Student.query.filter(Student.matricule.like(f"{annee}-%")).order_by(Student.id.desc()).first()
    numero = 1
    if dernier:
        try: numero = int(dernier.matricule.rsplit("-", 1)[1]) + 1
        except ValueError: numero = Student.query.count() + 1
    return f"{annee}-{numero:03d}"

BASE = """
<!doctype html><html lang='fr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<meta name='theme-color' content='#075b49'><link rel='manifest' href='/manifest.json'><link rel='stylesheet' href='/static/style.css'>
<title>{{ title }} · École Shemec</title></head><body>
{% if current_user.is_authenticated %}<div class='layout'><aside class='side'><a class='brand' href='/'> <b>✦</b><span>ÉCOLE SHEMEC<small>ESPACE SCOLAIRE</small></span></a>
<nav><a href='/'>▦ Tableau de bord</a>{% if current_user.role=='admin' %}<a href='/eleves'>♙ Élèves</a><a href='/comptes'>♧ Comptes utilisateurs</a>{% endif %}
<a href='/notes'>▤ Notes & résultats</a><a href='/messages'>✉ Messages</a><a href='/finances'>◈ Finances</a><a href='/horaire'>▦ Emploi du temps</a></nav>
<div class='side-bottom'><b>{{ current_user.nom }}</b><small>{{ current_user.role|capitalize }}</small><a href='/deconnexion'>↪ Déconnexion</a></div></aside>
<main class='main'><header><div><small class='kicker'>ÉCOLE SHEMEC · LUBUMBASHI</small><h1>{{ title }}</h1></div><span class='avatar'>{{ current_user.nom[:1] }}</span></header>
{% with alerts=get_flashed_messages(with_categories=true) %}{% for cat,msg in alerts %}<div class='alert {{ cat }}'>{{ msg }}</div>{% endfor %}{% endwith %}
{{ content|safe }}</main><nav class='bottom-nav'><a href='/'>Accueil</a>{% if current_user.role=='admin' %}<a href='/eleves'>Élèves</a>{% endif %}<a href='/notes'>Notes</a><a href='/messages'>Messages</a><a href='/finances'>Finances</a></nav></div>
{% else %}{% with alerts=get_flashed_messages(with_categories=true) %}{% for cat,msg in alerts %}<div class='alert {{ cat }}'>{{ msg }}</div>{% endfor %}{% endwith %}{{ content|safe }}{% endif %}
<script src='/static/app.js'></script></body></html>
"""

def page(title, template, **context):
    content = render_template_string(template, **context)
    return render_template_string(BASE, title=title, content=content)

LOGIN = """
<div class='login-page'><form class='login-card' method='post'><div class='mark'>✦</div><small class='kicker'>BIENVENUE À</small><h1>École Shemec</h1><p>Votre espace scolaire numérique.</p>
<label>Adresse e-mail<input type='email' name='email' required autocomplete='username'></label>
<label>Mot de passe<input type='password' name='password' required autocomplete='current-password'></label>
<button class='btn primary wide'>Se connecter</button><small class='muted'>Élèves · Parents · Enseignants · Administration</small></form></div>
"""
DASH_ADMIN = """
<section class='hero'><div><small>VUE GÉNÉRALE</small><h2>Bonjour, {{ current_user.nom }} 👋</h2><p>Bienvenue dans votre espace de gestion.</p></div><span>✦</span></section>
<div class='stats'><article><small>Élèves inscrits</small><strong>{{ total }}</strong><em>Effectif total</em></article><article><small>Enseignants</small><strong>{{ enseignants }}</strong><em>Personnel enseignant</em></article><article><small>Recettes encaissées</small><strong>{{ recettes }} FC</strong><em>Paiements confirmés</em></article><article><small>Paiements payés</small><strong>{{ payes }}/{{ nb_paiements }}</strong><em>Suivi des frais</em></article></div>
<section class='panel'><div class='panel-head'><div><h2>Dernières inscriptions</h2><p>Les dossiers récemment ajoutés</p></div><a class='btn outline' href='/eleves'>Tous les élèves</a></div>
<div class='table-wrap'><table><tr><th>Élève</th><th>Matricule</th><th>Classe</th><th>Promotion</th><th></th></tr>{% for s in recents %}<tr><td><img class='mini' src='/static/uploads/{{ s.photo }}'> {{ s.nom }}</td><td>{{ s.matricule }}</td><td>{{ s.classe }}</td><td>{{ s.promotion }}</td><td><a href='/eleves/{{ s.id }}'>Détails →</a></td></tr>{% else %}<tr><td colspan='5'>Aucune inscription pour le moment.</td></tr>{% endfor %}</table></div></section>
"""
DASH_USER = """
<section class='hero'><div><small>MON ESPACE SCOLAIRE</small><h2>Bienvenue, {{ current_user.nom }}</h2><p>Retrouvez vos informations et vos résultats.</p></div><span>✦</span></section>
{% if student %}<section class='panel profile'><img src='/static/uploads/{{ student.photo }}'><div><small>MATRICULE {{ student.matricule }}</small><h2>{{ student.nom }}</h2><p>{{ student.filiere }} · {{ student.classe }} · {{ student.promotion }}</p><b>Moyenne : {{ student.moyenne }}/20</b></div></section>{% else %}<section class='panel'>Votre compte n'est pas encore lié à un dossier élève. Contactez l'administration.</section>{% endif %}
<div class='quick'><a href='/notes'>▤ <b>Mes notes</b><small>Voir mes résultats</small></a><a href='/messages'>✉ <b>Messages</b><small>Contacter l'école</small></a><a href='/finances'>◈ <b>Paiements</b><small>Suivre mes frais</small></a></div>
"""
STUDENTS = """
<section class='panel'><div class='panel-head'><div><h2>Liste des élèves</h2><p>{{ students|length }} dossier(s)</p></div><a class='btn primary' href='/eleves/nouveau'>＋ Ajouter un élève</a></div>
<form class='search'><input name='q' value='{{ q }}' placeholder='Rechercher par nom ou matricule'><button class='btn dark'>Rechercher</button></form>
<div class='table-wrap'><table><tr><th>Élève</th><th>Matricule</th><th>Faculté / Filière</th><th>Classe</th><th>Moyenne</th><th></th></tr>{% for s in students %}<tr><td><img class='mini' src='/static/uploads/{{ s.photo }}'> {{ s.nom }}</td><td><span class='pill'>{{ s.matricule }}</span></td><td>{{ s.faculte }}<small class='sub'>{{ s.filiere }}</small></td><td>{{ s.classe }}</td><td>{{ s.moyenne }}/20</td><td><a href='/eleves/{{ s.id }}'>Ouvrir →</a></td></tr>{% else %}<tr><td colspan='6'>Aucun élève trouvé.</td></tr>{% endfor %}</table></div></section>
"""
STUDENT_FORM = """
<section class='panel'><h2>{{ 'Modifier le dossier' if s else 'Nouvelle inscription' }}</h2><p>La photo est obligatoire à la création. Le matricule est attribué automatiquement.</p>
<form method='post' enctype='multipart/form-data' class='form-grid'>
<label class='photo'>Photo de profil {% if not s %}*{% endif %}<input type='file' name='photo' accept='.jpg,.jpeg,.png,.webp' {% if not s %}required{% endif %}><img id='preview' src='{{ ("/static/uploads/"+s.photo) if s else "" }}' {% if not s %}hidden{% endif %}></label>
<label>Nom complet *<input name='nom' required value='{{ s.nom if s else "" }}'></label>
<label>Matricule automatique<input value='{{ s.matricule if s else matricule }}' readonly></label>
<label>Faculté *<input name='faculte' required value='{{ s.faculte if s else "" }}'></label>
<label>Filière *<input name='filiere' required value='{{ s.filiere if s else "" }}'></label>
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
{% if admin %}<section class='panel'><h2>Enregistrer un paiement</h2><form method='post' class='inline-form'><label>Élève<select name='student_id' required>{% for s in students %}<option value='{{ s.id }}'>{{ s.nom }} · {{ s.matricule }}</option>{% endfor %}</select></label><label>Libellé<input name='libelle' required placeholder='Frais scolaires'></label><label>Montant (FC)<input type='number' name='montant' min='0' required></label><label>Statut<select name='statut'><option>Payé</option><option>En attente</option></select></label><button class='btn primary'>Ajouter</button></form></section>{% endif %}
<section class='panel'><h2>Suivi des paiements</h2><div class='table-wrap'><table><tr><th>Élève</th><th>Libellé</th><th>Montant</th><th>Statut</th></tr>{% for p in paiements %}<tr><td>{{ p.eleve.nom }}</td><td>{{ p.libelle }}</td><td>{{ "{:,.0f}".format(p.montant).replace(",", " ") }} FC</td><td><span class='status {{ "paid" if p.statut=="Payé" else "pending" }}'>{{ p.statut }}</span></td></tr>{% else %}<tr><td colspan='4'>Aucun paiement.</td></tr>{% endfor %}</table></div></section>
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
    if current_user.role == "admin":
        return page("Tableau de bord", DASH_ADMIN, total=Student.query.count(),
            enseignants=User.query.filter_by(role="enseignant").count(),
            recettes=db.session.query(db.func.coalesce(db.func.sum(Payment.montant),0)).filter_by(statut="Payé").scalar(),
            payes=Payment.query.filter_by(statut="Payé").count(), nb_paiements=Payment.query.count(),
            recents=Student.query.order_by(Student.cree_le.desc()).limit(6).all())
    student = db.session.get(Student, current_user.student_id) if current_user.student_id else None
    return page("Mon espace", DASH_USER, student=student)

@app.route("/connexion", methods=["GET","POST"])
def connexion():
    if current_user.is_authenticated: return redirect(url_for("dashboard"))
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email","").strip().lower()).first()
        if user and user.verify(request.form.get("password","")):
            login_user(user); return redirect(url_for("dashboard"))
        flash("Adresse e-mail ou mot de passe incorrect.", "error")
    return page("Connexion", LOGIN)

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
            return page("Nouvelle inscription", STUDENT_FORM, s=None, matricule=matricule_suivant())
        ext = photo.filename.rsplit(".",1)[-1].lower()
        if ext not in ALLOWED:
            flash("Format accepté : JPG, PNG ou WEBP.", "error")
            return page("Nouvelle inscription", STUDENT_FORM, s=None, matricule=matricule_suivant())
        filename = datetime.utcnow().strftime("%Y%m%d%H%M%S%f") + "_" + secure_filename(photo.filename)
        photo.save(UPLOADS / filename)
        s = Student(matricule=matricule_suivant(), nom=request.form["nom"].strip(), photo=filename,
            faculte=request.form["faculte"].strip(), filiere=request.form["filiere"].strip(),
            promotion=request.form["promotion"].strip(), classe=request.form["classe"].strip(),
            nombre_cours=int(request.form.get("nombre_cours") or 0), credits=int(request.form.get("credits") or 0))
        db.session.add(s); db.session.commit()
        flash("Inscription enregistrée : " + s.matricule, "success")
        return redirect(url_for("eleve_detail", sid=s.id))
    return page("Nouvelle inscription", STUDENT_FORM, s=None, matricule=matricule_suivant())

@app.route("/eleves/<int:sid>")
@admin_only
def eleve_detail(sid):
    return page("Dossier de l'élève", DETAIL, s=db.get_or_404(Student,sid))

@app.route("/eleves/<int:sid>/modifier", methods=["GET","POST"])
@admin_only
def eleve_modifier(sid):
    s = db.get_or_404(Student,sid)
    if request.method == "POST":
        for field in ("nom","faculte","filiere","promotion","classe"):
            setattr(s, field, request.form[field].strip())
        s.nombre_cours=int(request.form.get("nombre_cours") or 0); s.credits=int(request.form.get("credits") or 0)
        photo=request.files.get("photo")
        if photo and photo.filename:
            ext=photo.filename.rsplit(".",1)[-1].lower()
            if ext not in ALLOWED: flash("Format photo invalide.","error"); return page("Modifier l'élève",STUDENT_FORM,s=s,matricule=s.matricule)
            filename=datetime.utcnow().strftime("%Y%m%d%H%M%S%f")+"_"+secure_filename(photo.filename)
            photo.save(UPLOADS/filename); s.photo=filename
        db.session.commit(); flash("Dossier modifié.","success"); return redirect(url_for("eleve_detail",sid=s.id))
    return page("Modifier l'élève",STUDENT_FORM,s=s,matricule=s.matricule)

@app.route("/eleves/<int:sid>/supprimer", methods=["POST"])
@admin_only
def eleve_supprimer(sid):
    s=db.get_or_404(Student,sid); db.session.delete(s); db.session.commit()
    flash("Dossier supprimé.","success"); return redirect(url_for("eleves"))

@app.route("/notes", methods=["GET","POST"])
@login_required
def notes():
    admin=current_user.role=="admin"
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
        p=Payment(student_id=int(request.form["student_id"]),libelle=request.form["libelle"].strip(),
                  montant=int(request.form["montant"]),statut=request.form["statut"])
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
    return page("Messages",MESSAGES,messages=Message.query.order_by(Message.cree_le.desc()).all())

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

@app.route("/manifest.json")
def manifest(): return send_from_directory(ROOT/"static","manifest.json")

@app.errorhandler(403)
def forbidden(_): return page("Accès refusé","<section class='panel'><h2>Accès réservé à l'administration.</h2><a href='/'>Retour</a></section>"),403

@app.errorhandler(404)
def not_found(_): return page("Introuvable","<section class='panel'><h2>Cette page n'existe pas.</h2><a href='/'>Retour</a></section>"),404

with app.app_context():
    db.create_all()
    if not User.query.filter_by(email="admin@shemec.cd").first():
        admin=User(nom="Administrateur Shemec",email="admin@shemec.cd",role="admin")
        admin.set_password(os.getenv("ADMIN_PASSWORD","Shemec2026!"))
        db.session.add(admin); db.session.commit()

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)),debug=os.getenv("FLASK_DEBUG")=="1")
