"""Tableau de bord familial sécurisé pour les parents."""
from flask import abort, request
from flask_login import current_user, login_required


def register_parent_portal(app, db, Student, Grade, Attendance, SchoolFee,
                           FeePayment, AcademicYear, parent_children, page):
    @app.route("/espace-parent")
    @login_required
    def espace_parent():
        if current_user.role != "parent":
            abort(403)

        children = parent_children(current_user)
        raw_id = request.args.get("student_id", "").strip()
        selected = None
        if raw_id:
            if not raw_id.isdigit():
                abort(400)
            selected = next((child for child in children if child.id == int(raw_id)), None)
            if selected is None:
                abort(403)
        elif len(children) == 1:
            selected = children[0]

        active_year = AcademicYear.query.filter_by(active=True).first()
        school_year = active_year.label if active_year else None
        cards = []
        for child in children:
            grades = Grade.query.filter_by(student_id=child.id).order_by(
                Grade.annee_academique.desc(), Grade.periode.desc()
            ).all()
            average = round(sum(float(g.note) for g in grades) / len(grades), 2) if grades else None
            recent_absences = Attendance.query.filter_by(
                student_id=child.id, statut="Absent"
            ).order_by(Attendance.jour.desc()).limit(5).all()
            unpaid = []
            fee_query = SchoolFee.query.filter_by(classe=child.classe)
            if school_year:
                fee_query = fee_query.filter_by(annee_academique=school_year)
            fees = fee_query.all()
            for fee in fees:
                paid = db.session.query(db.func.coalesce(db.func.sum(FeePayment.montant), 0)).filter_by(
                    fee_id=fee.id, student_id=child.id
                ).scalar()
                remaining = max(0, fee.montant - int(paid or 0))
                if remaining:
                    unpaid.append({"label": fee.libelle, "remaining": remaining, "currency": fee.devise})
            cards.append({"student": child, "average": average,
                          "absences": recent_absences, "unpaid": unpaid})

        selected_card = next((item for item in cards if selected and item["student"].id == selected.id), None)
        template = """
        <section class='hero'><div><small>ÉCOLE SHEMEC · ESPACE FAMILLE</small>
        <h2>Bienvenue dans votre espace parent</h2>
        <p>Suivez les résultats, les absences et les frais scolaires de vos enfants.</p></div><span>🇨🇩</span></section>
        {% if not children %}<section class='panel'><h2>Aucun enfant lié à ce compte</h2>
        <p>Contactez l'administration pour associer les dossiers de vos enfants à votre compte parent.</p></section>{% endif %}
        {% if children|length > 1 %}<section class='panel'><h2>Choisir un enfant</h2>
        <form method='get' class='inline-form'><label>Dossier de l'enfant
        <select name='student_id' required><option value=''>Sélectionner</option>
        {% for child in children %}<option value='{{ child.id }}' {% if selected and selected.id == child.id %}selected{% endif %}>{{ child.nom }} · {{ child.classe }}</option>{% endfor %}
        </select></label><button class='btn primary'>Afficher le dossier</button></form></section>{% endif %}
        {% if selected_card %}<section class='panel'><h2>{{ selected_card.student.nom }}</h2>
        <p>Matricule : {{ selected_card.student.matricule }} · Classe : {{ selected_card.student.classe }}</p>
        <div class='stats-grid'><div><small>Moyenne des notes enregistrées</small><b>{{ selected_card.average if selected_card.average is not none else 'Pas encore de notes' }}</b></div>
        <div><small>Absences récentes</small><b>{{ selected_card.absences|length }}</b></div>
        <div><small>Frais encore dus</small><b>{{ selected_card.unpaid|length }} poste(s)</b></div></div>
        <p><a class='btn primary' href='/bulletins?student_id={{ selected_card.student.id }}'>Consulter les bulletins</a>
        <a class='btn' href='/frais'>Voir les frais scolaires</a>
        <a class='btn' href='/finances'>Historique des paiements</a></p>
        <h3>Absences récentes</h3><div class='table-wrap'><table><tr><th>Date</th><th>Statut</th><th>Motif</th></tr>
        {% for a in selected_card.absences %}<tr><td>{{ a.jour.strftime('%d/%m/%Y') }}</td><td>{{ a.statut }}</td><td>{{ a.motif or '—' }}</td></tr>
        {% else %}<tr><td colspan='3'>Aucune absence enregistrée récemment.</td></tr>{% endfor %}</table></div>
        <h3>Soldes des frais scolaires</h3><div class='table-wrap'><table><tr><th>Frais</th><th>Solde</th></tr>
        {% for fee in selected_card.unpaid %}<tr><td>{{ fee.label }}</td><td>{{ '{:,.0f}'.format(fee.remaining).replace(',', ' ') }} {{ fee.currency }}</td></tr>
        {% else %}<tr><td colspan='2'>Aucun solde impayé trouvé pour les frais configurés.</td></tr>{% endfor %}</table></div>
        </section>{% elif children|length == 1 %}<p>Ouvrez le dossier de votre enfant ci-dessous.</p>{% endif %}
        {% if children|length > 1 and not selected %}<section class='panel'><h2>Mes enfants</h2><div class='table-wrap'><table>
        <tr><th>Élève</th><th>Classe</th><th>Matricule</th><th>Dossier</th></tr>
        {% for child in children %}<tr><td>{{ child.nom }}</td><td>{{ child.classe }}</td><td>{{ child.matricule }}</td><td><a href='/espace-parent?student_id={{ child.id }}'>Ouvrir</a></td></tr>{% endfor %}
        </table></div></section>{% endif %}
        """
        if len(children) == 1 and selected_card is None:
            selected_card = cards[0]
        return page("Espace Parent", template, children=children,
                    selected=selected, selected_card=selected_card, school_year=school_year)
