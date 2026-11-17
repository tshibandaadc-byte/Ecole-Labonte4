"""Passage de classe et archivage annuel — École Shemec."""
import re
from flask import request, abort, redirect, url_for, flash
from flask_login import login_required, current_user
from assessment import resultats_annuels
from school_structure import NIVEAUX_SCOLAIRES


def register_progression_routes(app, db, Student, Grade, Enrollment, StudentHistory,
                                AcademicYear, page, journaliser):
    @app.route("/passages", methods=["GET", "POST"])
    @login_required
    def passages_scolaires():
        if current_user.role != "admin":
            abort(403)

        active_year = AcademicYear.query.filter_by(active=True).first()
        default_year = active_year.label if active_year else "2026-2027"

        if request.method == "POST":
            try:
                student_id = int(request.form.get("student_id", ""))
            except (TypeError, ValueError):
                abort(400)
            student = db.session.get(Student, student_id)
            year = request.form.get("annee_academique", "").strip()
            decision = request.form.get("decision", "").strip()
            allowed = ("Promu", "Redoublant", "Diplômé")
            if (not student or not re.fullmatch(r"\d{4}-\d{4}", year)
                    or int(year[5:]) != int(year[:4]) + 1 or decision not in allowed):
                abort(400, description="Élève, année académique ou décision invalide.")

            grades = Grade.query.filter_by(student_id=student.id, annee_academique=year).all()
            summary = resultats_annuels(grades)
            if summary["moyenne_generale"] is None:
                abort(400, description="Impossible de valider le passage : aucune note annuelle n'est enregistrée.")

            current_enrollment = Enrollment.query.filter_by(
                student_id=student.id, annee_academique=year
            ).first()
            if current_enrollment and current_enrollment.statut in allowed:
                flash("Une décision annuelle a déjà été validée pour cet élève.", "warning")
                return redirect(url_for("passages_scolaires", annee=year))

            next_start = int(year[:4]) + 1
            next_year = f"{next_start}-{next_start + 1}"
            next_enrollment = Enrollment.query.filter_by(
                student_id=student.id, annee_academique=next_year
            ).first()
            if decision != "Diplômé" and next_enrollment:
                flash("Une inscription existe déjà pour l'année suivante. Aucune modification effectuée.", "warning")
                return redirect(url_for("passages_scolaires", annee=year))

            level = student.niveau_scolaire
            classes = NIVEAUX_SCOLAIRES.get(level, ())
            current_class = student.classe
            target_class = current_class
            if decision == "Promu":
                if level and current_class in classes:
                    index = classes.index(current_class)
                    if index == len(classes) - 1:
                        abort(400, description="Dernière classe du cycle : utilisez la décision Diplômé.")
                    target_class = classes[index + 1]
                elif level:
                    abort(400, description="La classe actuelle n'appartient pas au cycle scolaire de l'élève.")
                else:
                    abort(400, description="Cycle scolaire absent : vérifiez le dossier avant le passage.")
            elif decision == "Diplômé":
                if not level or current_class not in classes or current_class != classes[-1]:
                    abort(400, description="Le diplôme ne peut être validé que pour la dernière classe du cycle.")
            
            existing_history = StudentHistory.query.filter_by(
                student_id=student.id, annee_academique=year
            ).first()
            if existing_history:
                flash("Une archive existe déjà pour cette année. Vérifiez l'historique avant toute nouvelle décision.", "warning")
                return redirect(url_for("passages_scolaires", annee=year))

            try:
                # Une ligne d'historique par matière : les anciennes notes restent intactes.
                for row in summary["matieres"]:
                    db.session.add(StudentHistory(
                        student_id=student.id,
                        annee_academique=year,
                        promotion=student.promotion,
                        faculte=student.niveau_scolaire or student.faculte,
                        filiere=student.option_scolaire or student.filiere,
                        cours=row["matiere"],
                        credits=0,
                        note=row["moyenne"],
                        decision=decision
                    ))
                if not summary["matieres"]:
                    db.session.add(StudentHistory(
                        student_id=student.id, annee_academique=year,
                        promotion=student.promotion,
                        faculte=student.niveau_scolaire or student.faculte,
                        filiere=student.option_scolaire or student.filiere,
                        cours="Synthèse annuelle", credits=0, note=summary["moyenne_generale"],
                        decision=decision
                    ))

                if current_enrollment:
                    current_enrollment.statut = decision
                else:
                    current_enrollment = Enrollment(
                        student_id=student.id, annee_academique=year,
                        promotion=student.promotion, classe=current_class, statut=decision
                    )
                    db.session.add(current_enrollment)

                if decision != "Diplômé":
                    student.classe = target_class
                    db.session.add(Enrollment(
                        student_id=student.id, annee_academique=next_year,
                        promotion=student.promotion, classe=target_class, statut=decision
                    ))
                db.session.flush()
                journaliser("Décision de passage scolaire", "Enrollment",
                    f"élève={student.id}; nom={student.nom}; matricule={student.matricule}; année={year}; décision={decision}; classe={current_class} -> {target_class}; moyenne={summary['moyenne_generale']}")
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise

            flash(
                f"Décision « {decision} » validée pour {student.nom}. "
                + (f"Nouvelle classe : {target_class} ({next_year})." if decision != "Diplômé" else "Fin de cycle enregistrée."),
                "success"
            )
            return redirect(url_for("passages_scolaires", annee=year))

        year = request.args.get("annee", default_year).strip()
        if not re.fullmatch(r"\d{4}-\d{4}", year):
            abort(400)
        students = Student.query.order_by(Student.classe, Student.nom).all()
        rows = []
        for student in students:
            grades = Grade.query.filter_by(student_id=student.id, annee_academique=year).all()
            summary = resultats_annuels(grades)
            current = Enrollment.query.filter_by(student_id=student.id, annee_academique=year).first()
            rows.append({
                "student": student,
                "average": summary["moyenne_generale"],
                "subjects": len(summary["matieres"]),
                "decision": current.statut if current and current.statut in ("Promu", "Redoublant", "Diplômé") else None,
            })

        template = """
        <section class='panel'>
          <h2>Validation annuelle des passages</h2>
          <p>Les notes de l'année sont archivées par matière avant la décision. La classe de l'élève ne change qu'après validation par la Direction.</p>
          <form method='get' class='inline-form'>
            <label>Année académique<input name='annee' value='{{ year }}' pattern='[0-9]{4}-[0-9]{4}' required></label>
            <button class='btn primary'>Afficher</button>
          </form>
        </section>
        <section class='panel'><h2>Dossiers à examiner · {{ year }}</h2>
          <div class='table-wrap'><table>
            <tr><th>Élève</th><th>Cycle / classe actuelle</th><th>Matières notées</th><th>Moyenne annuelle</th><th>Décision</th></tr>
            {% for row in rows %}
            <tr>
              <td><b>{{ row.student.nom }}</b><small class='sub'>{{ row.student.matricule }}</small></td>
              <td>{{ row.student.niveau_scolaire or row.student.faculte }}<small class='sub'>{{ row.student.classe }}</small></td>
              <td>{{ row.subjects }}</td>
              <td>{% if row.average is not none %}<b>{{ '%.2f'|format(row.average) }}/20</b>{% else %}Aucune note{% endif %}</td>
              <td>
                {% if row.decision %}<span class='pill'>{{ row.decision }} · déjà validé</span>
                {% elif row.average is not none %}
                <form method='post' class='inline-form'>
                  <input type='hidden' name='student_id' value='{{ row.student.id }}'>
                  <input type='hidden' name='annee_academique' value='{{ year }}'>
                  <select name='decision' required>
                    <option value=''>Choisir</option><option value='Promu'>Promu</option>
                    <option value='Redoublant'>Redoublant</option><option value='Diplômé'>Diplômé</option>
                  </select>
                  <button class='btn primary'>Valider</button>
                </form>
                {% else %}<span class='muted'>En attente des notes</span>{% endif %}
              </td>
            </tr>
            {% else %}<tr><td colspan='5'>Aucun élève inscrit.</td></tr>{% endfor %}
          </table></div>
        </section>
        <section class='panel'>
          <h3>Règles de sécurité</h3>
          <ul>
            <li>Réservé au compte Administration.</li>
            <li>Une décision par élève et par année académique.</li>
            <li>Une seconde inscription pour l'année suivante bloque la promotion automatique.</li>
            <li>Les notes originales ne sont ni supprimées ni modifiées.</li>
            <li>La dernière classe du cycle ne peut être validée que comme diplômée.</li>
          </ul>
          <p class='muted'>La moyenne affichée est arithmétique. Le seuil et les coefficients officiels doivent être approuvés par la Direction avant utilisation administrative.</p>
          <a class='btn outline' href='/historique'>Consulter l'historique académique</a>
        </section>
        """
        return page("Passages de classe", template, year=year, rows=rows)
