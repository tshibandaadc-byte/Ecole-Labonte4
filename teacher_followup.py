"""Suivi des présences et activités pédagogiques des enseignants."""
from datetime import date, datetime

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import UniqueConstraint


def register_teacher_followup(app, db, User, page):
    class TeacherAttendance(db.Model):
        __tablename__ = "teacher_attendance"
        id = db.Column(db.Integer, primary_key=True)
        teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
        jour = db.Column(db.Date, nullable=False, default=date.today)
        statut = db.Column(db.String(20), nullable=False, default="Présent")
        heure_arrivee = db.Column(db.String(5), nullable=True)
        heure_depart = db.Column(db.String(5), nullable=True)
        observation = db.Column(db.String(255), nullable=True)
        cree_le = db.Column(db.DateTime, default=datetime.utcnow)
        enseignant = db.relationship("User")
        __table_args__ = (UniqueConstraint("teacher_id", "jour", name="uq_teacher_attendance_day"),)

    class TeacherActivity(db.Model):
        __tablename__ = "teacher_activity"
        id = db.Column(db.Integer, primary_key=True)
        teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
        jour = db.Column(db.Date, nullable=False, default=date.today)
        classe = db.Column(db.String(80), nullable=False)
        cours = db.Column(db.String(140), nullable=False)
        type_activite = db.Column(db.String(40), nullable=False, default="Cours")
        description = db.Column(db.Text, nullable=False)
        statut = db.Column(db.String(20), nullable=False, default="Réalisée")
        cree_le = db.Column(db.DateTime, default=datetime.utcnow)
        enseignant = db.relationship("User")

    # Les tables sont créées sans modifier les tables historiques.
    with app.app_context():
        db.create_all()

    def is_teacher_or_admin():
        if current_user.role not in ("enseignant", "admin"):
            abort(403)
        return current_user.role == "admin"

    @app.route("/suivi-enseignant", methods=["GET", "POST"])
    @login_required
    def suivi_enseignant():
        admin = is_teacher_or_admin()
        teachers = User.query.filter_by(role="enseignant").order_by(User.nom).all()
        selected_raw = request.values.get("teacher_id", "")
        if admin:
            selected = db.session.get(User, int(selected_raw)) if selected_raw.isdigit() else None
            if selected and selected.role != "enseignant":
                abort(400)
            teacher_id = selected.id if selected else None
        else:
            selected = current_user
            teacher_id = current_user.id

        if request.method == "POST":
            action = request.form.get("action", "")
            if action == "attendance":
                raw_day = request.form.get("jour", "")
                try:
                    day = date.fromisoformat(raw_day)
                except ValueError:
                    flash("Date de présence invalide.", "error")
                    return redirect(url_for("suivi_enseignant"))
                status = request.form.get("statut", "")
                arrival = request.form.get("heure_arrivee", "").strip() or None
                departure = request.form.get("heure_depart", "").strip() or None
                observation = request.form.get("observation", "").strip()[:255]
                if status not in ("Présent", "Absent", "Retard", "Congé") or (arrival and not __import__("re").fullmatch(r"(?:[01]\\d|2[0-3]):[0-5]\\d", arrival)) or (departure and not __import__("re").fullmatch(r"(?:[01]\\d|2[0-3]):[0-5]\\d", departure)) or (arrival and departure and arrival >= departure):
                    flash("Vérifiez le statut et les heures déclarées.", "error")
                else:
                    row = TeacherAttendance.query.filter_by(teacher_id=current_user.id, jour=day).first()
                    if row is None:
                        row = TeacherAttendance(teacher_id=current_user.id, jour=day)
                        db.session.add(row)
                    row.statut, row.heure_arrivee, row.heure_depart, row.observation = status, arrival, departure, observation
                    db.session.commit()
                    flash("Présence enregistrée.", "success")
                return redirect(url_for("suivi_enseignant"))

            if action == "activity":
                try:
                    day = date.fromisoformat(request.form.get("jour", ""))
                except ValueError:
                    flash("Date d'activité invalide.", "error")
                    return redirect(url_for("suivi_enseignant"))
                classe = request.form.get("classe", "").strip()
                cours = request.form.get("cours", "").strip()
                kind = request.form.get("type_activite", "")
                description = request.form.get("description", "").strip()
                status = request.form.get("statut", "")
                if not classe or len(classe) > 80 or not cours or len(cours) > 140 or kind not in ("Cours", "Préparation", "Évaluation", "Réunion", "Remédiation", "Autre") or not description or len(description) > 3000 or status not in ("Réalisée", "En cours", "À suivre"):
                    flash("Complétez correctement les informations de l'activité.", "error")
                else:
                    db.session.add(TeacherActivity(teacher_id=current_user.id, jour=day,
                        classe=classe, cours=cours, type_activite=kind,
                        description=description, statut=status))
                    db.session.commit()
                    flash("Activité pédagogique enregistrée.", "success")
                return redirect(url_for("suivi_enseignant"))

            abort(400)

        attendance_query = TeacherAttendance.query
        activity_query = TeacherActivity.query
        if not admin:
            attendance_query = attendance_query.filter_by(teacher_id=current_user.id)
            activity_query = activity_query.filter_by(teacher_id=current_user.id)
        elif teacher_id:
            attendance_query = attendance_query.filter_by(teacher_id=teacher_id)
            activity_query = activity_query.filter_by(teacher_id=teacher_id)
        attendance = attendance_query.order_by(TeacherAttendance.jour.desc()).limit(150).all()
        activities = activity_query.order_by(TeacherActivity.jour.desc(), TeacherActivity.id.desc()).limit(150).all()

        template = """
        <section class='hero'><div><small>ÉCOLE SHEMEC · ESPACE PÉDAGOGIQUE</small>
          <h2>Suivi des enseignants</h2><p>Présences quotidiennes et journal des activités pédagogiques.</p></div><span>🇨🇩</span></section>
        {% if admin %}<section class='panel'><form method='get' class='inline-form'><label>Filtrer par enseignant
          <select name='teacher_id'><option value=''>Tous les enseignants</option>
          {% for t in teachers %}<option value='{{ t.id }}' {% if selected and selected.id == t.id %}selected{% endif %}>{{ t.nom }}</option>{% endfor %}</select></label>
          <button class='btn primary'>Filtrer</button></form></section>{% endif %}
        {% if not admin %}<section class='panel'><h2>Déclarer ma présence</h2><form method='post' class='form-grid'>
          <input type='hidden' name='action' value='attendance'><label>Date *<input type='date' name='jour' value='{{ today }}' required></label>
          <label>Statut *<select name='statut'><option>Présent</option><option>Absent</option><option>Retard</option><option>Congé</option></select></label>
          <label>Heure d'arrivée<input type='time' name='heure_arrivee'></label><label>Heure de départ<input type='time' name='heure_depart'></label>
          <label>Observation<input name='observation' maxlength='255'></label><button class='btn primary'>Enregistrer la présence</button></form></section>
        <section class='panel'><h2>Ajouter une activité pédagogique</h2><form method='post' class='form-grid'>
          <input type='hidden' name='action' value='activity'><label>Date *<input type='date' name='jour' value='{{ today }}' required></label>
          <label>Classe *<input name='classe' required maxlength='80'></label><label>Matière *<input name='cours' required maxlength='140'></label>
          <label>Type *<select name='type_activite'>{% for k in kinds %}<option>{{ k }}</option>{% endfor %}</select></label>
          <label>Statut *<select name='statut'><option>Réalisée</option><option>En cours</option><option>À suivre</option></select></label>
          <label class='wide'>Description / compte rendu *<textarea name='description' required maxlength='3000' rows='3'></textarea></label>
          <button class='btn primary'>Enregistrer l'activité</button></form></section>{% endif %}
        <section class='panel'><h2>Registre des présences</h2><div class='table-wrap'><table><tr><th>Enseignant</th><th>Date</th><th>Statut</th><th>Arrivée</th><th>Départ</th><th>Observation</th></tr>
        {% for a in attendance %}<tr><td>{{ a.enseignant.nom }}</td><td>{{ a.jour.strftime('%d/%m/%Y') }}</td><td>{{ a.statut }}</td><td>{{ a.heure_arrivee or '—' }}</td><td>{{ a.heure_depart or '—' }}</td><td>{{ a.observation or '—' }}</td></tr>
        {% else %}<tr><td colspan='6'>Aucune présence enregistrée.</td></tr>{% endfor %}</table></div></section>
        <section class='panel'><h2>Journal des activités pédagogiques</h2><div class='table-wrap'><table><tr><th>Enseignant</th><th>Date</th><th>Classe</th><th>Matière</th><th>Activité</th><th>Description</th><th>Statut</th></tr>
        {% for a in activities %}<tr><td>{{ a.enseignant.nom }}</td><td>{{ a.jour.strftime('%d/%m/%Y') }}</td><td>{{ a.classe }}</td><td>{{ a.cours }}</td><td>{{ a.type_activite }}</td><td>{{ a.description }}</td><td>{{ a.statut }}</td></tr>
        {% else %}<tr><td colspan='7'>Aucune activité enregistrée.</td></tr>{% endfor %}</table></div></section>
        """
        return page("Suivi des enseignants", template, admin=admin, teachers=teachers,
                    selected=selected, attendance=attendance, activities=activities,
                    today=date.today().isoformat(),
                    kinds=("Cours", "Préparation", "Évaluation", "Réunion", "Remédiation", "Autre"))
