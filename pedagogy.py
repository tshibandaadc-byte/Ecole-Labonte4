"""Organisation pédagogique et emploi du temps — École Shemec."""
import re
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


def valid_academic_year(value):
    """Accepte une année scolaire écrite sous la forme 2026-2027."""
    return bool(value and re.fullmatch(r"\d{4}-\d{4}", value))


def register_timetable_routes(app, db, User, TeacherAssignment, CourseSlot, page, AcademicYear=None):
    def default_year():
        if AcademicYear is not None:
            active = AcademicYear.query.filter_by(active=True).first()
            if active:
                return active.label
        latest = TeacherAssignment.query.order_by(TeacherAssignment.annee_academique.desc()).first()
        return latest.annee_academique if latest else "2026-2027"

    @app.route("/planning-cours", methods=["GET", "POST"])
    @login_required
    def planning_cours():
        admin = current_user.role == "admin"
        teacher = current_user.role == "enseignant"
        if not (admin or teacher):
            abort(403)

        selected_year = (request.values.get("annee_academique") or request.args.get("annee") or default_year()).strip()
        if not valid_academic_year(selected_year):
            abort(400, description="Année académique invalide. Format attendu : AAAA-AAAA.")

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
                if slot.annee_academique != selected_year:
                    abort(404)
                db.session.delete(slot)
                db.session.commit()
                flash("Séance retirée de l'emploi du temps.", "success")
                return redirect(url_for("planning_cours", annee=selected_year))

            raw_assignment = request.form.get("assignment_id", "")
            assignment = db.session.get(TeacherAssignment, int(raw_assignment)) if raw_assignment.isdigit() else None
            day = request.form.get("jour", "")
            start_raw = request.form.get("debut", "")
            end_raw = request.form.get("fin", "")
            start, end = parse_time(start_raw), parse_time(end_raw)
            if (not assignment or assignment.annee_academique != selected_year or
                    day not in DAYS or not start or not end or start >= end):
                flash("Vérifiez l'affectation, l'année, le jour et les heures du cours.", "error")
                return redirect(url_for("planning_cours", annee=selected_year))

            teacher_user = db.session.get(User, assignment.teacher_id)
            if not teacher_user or teacher_user.role != "enseignant":
                abort(400, description="Le compte enseignant de cette affectation n'est plus valide.")

            existing_slots = CourseSlot.query.filter_by(
                jour=day, annee_academique=selected_year
            ).all()
            for existing in existing_slots:
                old_start, old_end = parse_time(existing.debut), parse_time(existing.fin)
                if not old_start or not old_end or not intervals_overlap(start, end, old_start, old_end):
                    continue
                same_class = existing.classe.strip().casefold() == assignment.classe.strip().casefold()
                same_teacher = existing.enseignant.strip().casefold() == teacher_user.nom.strip().casefold()
                if same_class:
                    flash("Conflit : cette classe a déjà un cours pendant ce créneau.", "error")
                    return redirect(url_for("planning_cours", annee=selected_year))
                if same_teacher:
                    flash("Conflit : cet enseignant est déjà occupé pendant ce créneau.", "error")
                    return redirect(url_for("planning_cours", annee=selected_year))

            db.session.add(CourseSlot(
                annee_academique=selected_year,
                classe=assignment.classe, jour=day, debut=start_raw, fin=end_raw,
                cours=assignment.cours, enseignant=teacher_user.nom
            ))
            db.session.commit()
            flash("Cours ajouté à l'emploi du temps.", "success")
            return redirect(url_for("planning_cours", annee=selected_year))

        query = CourseSlot.query.filter_by(annee_academique=selected_year)
        assignments_query = TeacherAssignment.query.filter_by(annee_academique=selected_year)
        if teacher:
            allowed = assignments_query.filter_by(teacher_id=current_user.id).all()
            allowed_classes = sorted({row.classe for row in allowed})
            query = query.filter(CourseSlot.classe.in_(allowed_classes)) if allowed_classes else query.filter(db.false())
            assignments_query = assignments_query.filter_by(teacher_id=current_user.id)
        slots = query.order_by(CourseSlot.jour, CourseSlot.debut, CourseSlot.classe).all()
        assignments = assignments_query.order_by(TeacherAssignment.classe, TeacherAssignment.cours).all()
        years = sorted({
            row[0] for row in db.session.query(TeacherAssignment.annee_academique).distinct().all()
            if row[0]
        }, reverse=True)
        if selected_year not in years:
            years.append(selected_year)
            years.sort(reverse=True)

        template = """
        <section class='hero'><div><small>ÉCOLE SHEMEC · LUBUMBASHI</small>
          <h2>Emploi du temps des cours · {{ annee }}</h2>
          <p>Planification par année scolaire et contrôle des conflits de classe et d'enseignant.</p></div><span>🇨🇩</span></section>
        <section class='panel'><form method='get' class='inline-form'>
          <label>Année académique<select name='annee' required>
            {% for y in years %}<option value='{{ y }}' {% if y == annee %}selected{% endif %}>{{ y }}</option>{% endfor %}
          </select></label><button class='btn primary'>Afficher</button>
        </form></section>
        {% if admin %}
        <section class='panel'><h2>Ajouter une séance</h2>
          {% if assignments %}
          <form method='post' class='form-grid'>
            <input type='hidden' name='annee_academique' value='{{ annee }}'>
            <input type='hidden' name='action' value='create'>
            <label>Affectation pédagogique *<select name='assignment_id' required>
              {% for a in assignments %}<option value='{{ a.id }}'>{{ a.classe }} · {{ a.cours }} · {{ a.enseignant.nom }} · {{ a.annee_academique }}</option>{% endfor %}
            </select></label>
            <label>Jour *<select name='jour' required>{% for day in days %}<option>{{ day }}</option>{% endfor %}</select></label>
            <label>Début *<input type='time' name='debut' required></label>
            <label>Fin *<input type='time' name='fin' required></label>
            <button class='btn primary'>Ajouter au planning</button>
          </form>
          {% else %}<p>Aucune affectation pour {{ annee }}. Créez d'abord les affectations des enseignants.</p>{% endif %}
        </section>
        {% endif %}
        <section class='panel'><div class='panel-head'><div><h2>Planning hebdomadaire</h2>
          <p>{{ slots|length }} séance(s) · Année {{ annee }}</p></div></div>
          <div class='table-wrap'><table><tr><th>Jour</th><th>Heure</th><th>Classe</th><th>Matière</th><th>Enseignant</th>{% if admin %}<th>Action</th>{% endif %}</tr>
          {% for s in slots %}<tr><td>{{ s.jour }}</td><td>{{ s.debut }} – {{ s.fin }}</td><td>{{ s.classe }}</td><td>{{ s.cours }}</td><td>{{ s.enseignant or '—' }}</td>
          {% if admin %}<td><form method='post'><input type='hidden' name='action' value='delete'><input type='hidden' name='slot_id' value='{{ s.id }}'><input type='hidden' name='annee_academique' value='{{ annee }}'><button class='btn outline' onclick="return confirm('Retirer cette séance ?')">Retirer</button></form></td>{% endif %}</tr>
          {% else %}<tr><td colspan='6'>Aucun cours planifié pour cette année.</td></tr>{% endfor %}</table></div>
        </section>
        """
        return page("Emploi du temps", template, admin=admin, slots=slots,
                    assignments=assignments, days=DAYS, annee=selected_year, years=years)
