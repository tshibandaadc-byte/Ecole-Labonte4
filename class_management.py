"""Gestion des classes, listes d'élèves et titulaires — École Shemec."""
import re
from datetime import date
from flask import request, abort, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import UniqueConstraint


def register_class_routes(app, db, Student, User, TeacherAssignment, AcademicYear, page):
    class ClassRoom(db.Model):
        __tablename__ = "school_class"
        id = db.Column(db.Integer, primary_key=True)
        nom = db.Column(db.String(80), nullable=False)
        niveau_scolaire = db.Column(db.String(30), nullable=True)
        option_scolaire = db.Column(db.String(80), nullable=True)
        annee_academique = db.Column(db.String(20), nullable=False)
        titulaire_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
        cree_le = db.Column(db.Date, nullable=False, default=date.today)
        titulaire = db.relationship("User")
        __table_args__ = (UniqueConstraint("nom", "annee_academique", name="uq_school_class_year"),)

    with app.app_context():
        db.create_all()

    @app.route("/classes", methods=["GET", "POST"])
    @login_required
    def gestion_classes():
        if current_user.role != "admin":
            abort(403)

        active = AcademicYear.query.filter_by(active=True).first()
        default_year = active.label if active else "2026-2027"

        if request.method == "POST":
            name = request.form.get("classe", "").strip()
            year = request.form.get("annee_academique", "").strip()
            teacher_raw = request.form.get("titulaire_id", "").strip()
            if not name or len(name) > 80 or not re.fullmatch(r"\d{4}-\d{4}", year):
                abort(400, description="Classe ou année académique invalide.")
            teacher = None
            if teacher_raw:
                if not teacher_raw.isdigit():
                    abort(400)
                teacher = db.session.get(User, int(teacher_raw))
                if not teacher or teacher.role != "enseignant":
                    abort(400, description="Le titulaire doit être un compte enseignant actif.")
            room = ClassRoom.query.filter_by(nom=name, annee_academique=year).first()
            if room is None:
                sample = Student.query.filter_by(classe=name).first()
                room = ClassRoom(
                    nom=name,
                    niveau_scolaire=sample.niveau_scolaire if sample else None,
                    option_scolaire=sample.option_scolaire if sample else None,
                    annee_academique=year
                )
                db.session.add(room)
            room.titulaire = teacher
            db.session.commit()
            flash("Titulaire de classe enregistré." if teacher else "Classe enregistrée sans titulaire.", "success")
            return redirect(url_for("gestion_classes", annee=year, classe=name))

        year = request.args.get("annee", default_year).strip()
        if not re.fullmatch(r"\d{4}-\d{4}", year):
            abort(400)
        selected = request.args.get("classe", "").strip()
        class_names = sorted({
            value for (value,) in db.session.query(Student.classe).distinct().all()
            if value and value.strip()
        })
        # Inclure aussi les classes déjà créées même si aucun élève n'y est encore inscrit.
        rooms = ClassRoom.query.filter_by(annee_academique=year).order_by(ClassRoom.nom).all()
        room_by_name = {room.nom: room for room in rooms}
        names = sorted(set(class_names) | set(room_by_name))
        if selected and selected not in names:
            abort(404)
        students = Student.query.filter_by(classe=selected).order_by(Student.nom).all() if selected else []
        room = room_by_name.get(selected) if selected else None
        teachers = User.query.filter_by(role="enseignant").order_by(User.nom).all()
        stats = []
        for name in names:
            group = Student.query.filter_by(classe=name).all()
            current_room = room_by_name.get(name)
            stats.append({
                "name": name,
                "count": len(group),
                "level": (current_room.niveau_scolaire if current_room else None)
                         or (group[0].niveau_scolaire if group else ""),
                "option": (current_room.option_scolaire if current_room else None)
                          or (group[0].option_scolaire if group else ""),
                "titulaire": current_room.titulaire.nom if current_room and current_room.titulaire else "À désigner",
            })

        template = """
        <section class='hero'><div><small>ORGANISATION PÉDAGOGIQUE</small>
          <h2>Classes et titulaires</h2><p>Effectifs, listes nominatives et responsable de chaque classe.</p></div><span>🇨🇩</span></section>
        <section class='panel'>
          <form method='get' class='inline-form'>
            <label>Année académique<input name='annee' value='{{ year }}' pattern='[0-9]{4}-[0-9]{4}' required></label>
            <button class='btn primary'>Afficher</button>
          </form>
        </section>
        <section class='panel'><div class='panel-head'><div><h2>Répertoire des classes</h2>
          <p>{{ names|length }} classe(s) · {{ total }} élève(s)</p></div></div>
          <div class='table-wrap'><table><tr><th>Classe</th><th>Cycle</th><th>Option</th><th>Effectif</th><th>Titulaire</th><th></th></tr>
          {% for item in stats %}<tr><td><b>{{ item.name }}</b></td><td>{{ item.level or '—' }}</td>
          <td>{{ item.option or '—' }}</td><td>{{ item.count }}</td><td>{{ item.titulaire }}</td>
          <td><a href='{{ url_for("gestion_classes", annee=year, classe=item.name) }}'>Ouvrir →</a></td></tr>
          {% else %}<tr><td colspan='6'>Aucune classe trouvée. Inscrivez d'abord des élèves.</td></tr>{% endfor %}
          </table></div>
        </section>
        {% if selected %}
        <section class='panel'><div class='panel-head'><div><h2>Classe : {{ selected }}</h2>
          <p>{{ students|length }} élève(s) · Année {{ year }}</p></div></div>
          <form method='post' class='inline-form'>
            <input type='hidden' name='classe' value='{{ selected }}'>
            <input type='hidden' name='annee_academique' value='{{ year }}'>
            <label>Titulaire de classe<select name='titulaire_id'>
              <option value=''>Non désigné</option>
              {% for teacher in teachers %}<option value='{{ teacher.id }}' {% if room and room.titulaire_id == teacher.id %}selected{% endif %}>{{ teacher.nom }}</option>{% endfor %}
            </select></label>
            <button class='btn primary'>Enregistrer le titulaire</button>
          </form>
          <div class='table-wrap'><table><tr><th>N°</th><th>Élève</th><th>Matricule</th><th>Cycle</th><th>Option</th></tr>
          {% for student in students %}<tr><td>{{ loop.index }}</td><td>{{ student.nom }}</td><td>{{ student.matricule }}</td>
          <td>{{ student.niveau_scolaire or student.faculte }}</td><td>{{ student.option_scolaire or student.filiere }}</td></tr>
          {% else %}<tr><td colspan='5'>Aucun élève dans cette classe pour le moment.</td></tr>{% endfor %}
          </table></div>
        </section>
        {% endif %}
        <section class='panel'><p class='muted'>Le répertoire rassemble les classes existantes dans les dossiers élèves. Le titulaire est enregistré par année académique ; l'historique des anciennes années est conservé.</p></section>
        """
        total = Student.query.count()
        return page("Classes et titulaires", template, year=year, names=names,
                    stats=stats, selected=selected, students=students, teachers=teachers,
                    room=room, total=total)
