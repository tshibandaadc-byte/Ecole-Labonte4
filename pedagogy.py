"""Organisation pédagogique et emploi du temps — École Shemec."""
from datetime import datetime

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user, login_required


DAYS = ("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi")


def parse_time(value):
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        return None


def intervals_overlap(start_a, end_a, start_b, end_b):
    """Deux cours se chevauchent si leurs intervalles semi-ouverts se croisent."""
    return start_a < end_b and start_b < end_a


def register_timetable_routes(app, db, User, TeacherAssignment, CourseSlot, page):
    @app.route("/planning-cours", methods=["GET", "POST"])
    @login_required
    def planning_cours():
        admin = current_user.role == "admin"
        teacher = current_user.role == "enseignant"
        if not (admin or teacher):
            abort(403)

        if request.method == "POST":
            if not admin:
                abort(403)
            action = request.form.get("action", "create")
            if action == "delete":
                raw_id = request.form.get("slot_id", "")
                if not raw_id.isdigit():
                    abort(400)
                slot = db.session.get(CourseSlot, int(raw_id))
                if not slot:
                    abort(404)
                db.session.delete(slot)
                db.session.commit()
                flash("Séance retirée de l'emploi du temps.", "success")
                return redirect(url_for("planning_cours"))

            raw_assignment = request.form.get("assignment_id", "")
            assignment = db.session.get(TeacherAssignment, int(raw_assignment)) if raw_assignment.isdigit() else None
            day = request.form.get("jour", "")
            start_raw = request.form.get("debut", "")
            end_raw = request.form.get("fin", "")
            start, end = parse_time(start_raw), parse_time(end_raw)
            if not assignment or day not in DAYS or not start or not end or start >= end:
                flash("Vérifiez l'affectation, le jour et les heures du cours.", "error")
                return redirect(url_for("planning_cours"))

            teacher_user = db.session.get(User, assignment.teacher_id)
            if not teacher_user or teacher_user.role != "enseignant":
                abort(400, description="Le compte enseignant de cette affectation n'est plus valide.")

            existing_slots = CourseSlot.query.filter_by(jour=day, annee_academique=assignment.annee_academique).all()
            for existing in existing_slots:
                old_start, old_end = parse_time(existing.debut), parse_time(existing.fin)
                if not old_start or not old_end:
                    continue
                if not intervals_overlap(start, end, old_start, old_end):
                    continue
                same_class = existing.classe.strip().casefold() == assignment.classe.strip().casefold()
                same_teacher = existing.enseignant.strip().casefold() == teacher_user.nom.strip().casefold()
                if same_class:
                    flash("Conflit : cette classe a déjà un cours pendant ce créneau.", "error")
                    return redirect(url_for("planning_cours"))
                if same_teacher:
                    flash("Conflit : cet enseignant est déjà occupé pendant ce créneau.", "error")
                    return redirect(url_for("planning_cours"))

            db.session.add(CourseSlot(
                classe=assignment.classe, jour=day, debut=start_raw, fin=end_raw,
                cours=assignment.cours, enseignant=teacher_user.nom
            ))
            db.session.commit()
            flash("Cours ajouté à l'emploi du temps.", "success")
            return redirect(url_for("planning_cours"))

        query = CourseSlot.query
        assignments_query = TeacherAssignment.query
        if teacher:
            allowed = TeacherAssignment.query.filter_by(teacher_id=current_user.id, annee_academique=selected_year).all()
            allowed_classes = sorted({row.classe for row in allowed})
            query = query.filter(CourseSlot.classe.in_(allowed_classes)) if allowed_classes else query.filter(db.false())
            assignments_query = assignments_query.filter_by(teacher_id=current_user.id)
        slots = query.order_by(CourseSlot.jour, CourseSlot.debut, CourseSlot.classe).all()
        assignments = assignments_query.order_by(
            TeacherAssignment.annee_academique.desc(), TeacherAssignment.classe, TeacherAssignment.cours
        ).all()
        template = """
        <section class='hero'><div><small>ÉCOLE SHEMEC · LUBUMBASHI</small>
          <h2>Emploi du temps des cours · {{ annee }}</h2>
          <p>Planification des séances et contrôle des conflits de classe et d'enseignant.</p></div><span>🇨🇩</span></section>
        {% if admin %}
        <section class='panel'><h2>Ajouter une séance</h2>
          {% if assignments %}
          <form method='post' class='form-grid'>
            <input type='hidden' name='action' value='create'>
            <label>Affectation pédagogique *
              <select name='assignment_id' required>
                {% for a in assignments %}<option value='{{ a.id }}'>{{ a.classe }} · {{ a.cours }} · {{ a.enseignant.nom }} · {{ a.annee_academique }}</option>{% endfor %}
              </select>
            </label>
            <label>Jour *<select name='jour' required>{% for day in days %}<option>{{ day }}</option>{% endfor %}</select></label>
            <label>Début *<input type='time' name='debut' required></label>
            <label>Fin *<input type='time' name='fin' required></label>
            <button class='btn primary'>Ajouter au planning</button>
          </form>
          {% else %}<p>Aucune affectation disponible. Créez d'abord les affectations des enseignants.</p>{% endif %}
        </section>
        {% endif %}
        <section class='panel'><div class='panel-head'><div><h2>Planning hebdomadaire</h2>
          <p>{{ slots|length }} séance(s) enregistrée(s)</p></div></div>
          <div class='table-wrap'><table><tr><th>Jour</th><th>Heure</th><th>Classe</th><th>Matière</th><th>Enseignant</th>{% if admin %}<th>Action</th>{% endif %}</tr>
          {% for s in slots %}<tr><td>{{ s.jour }}</td><td>{{ s.debut }} – {{ s.fin }}</td><td>{{ s.classe }}</td><td>{{ s.cours }}</td><td>{{ s.enseignant or '—' }}</td>
          {% if admin %}<td><form method='post'><input type='hidden' name='action' value='delete'><input type='hidden' name='slot_id' value='{{ s.id }}'><button class='btn outline' onclick="return confirm('Retirer cette séance ?')">Retirer</button></form></td>{% endif %}</tr>
          {% else %}<tr><td colspan='6'>Aucun cours planifié pour le moment.</td></tr>{% endfor %}</table></div>
        </section>
        <section class='panel'><p class='muted'>Les conflits sont contrôlés pour une même classe et un même enseignant. Le modèle historique des créneaux ne stocke pas encore l'année académique : le planning affiché est donc commun aux années tant qu'une migration dédiée n'est pas réalisée.</p></section>
        """
        return page("Emploi du temps", template, admin=admin, slots=slots,
                    assignments=assignments, days=DAYS)
