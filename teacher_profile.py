"""Espace professionnel des enseignants : affectations, contrat et paie."""
from flask import abort, request
from flask_login import current_user, login_required


def register_teacher_profile(app, db, User, Personnel, StaffContract,
                             PayrollRecord, TeacherAssignment, page):
    @app.route("/espace-professionnel")
    @login_required
    def espace_professionnel():
        admin = current_user.role == "admin"
        if not admin and current_user.role != "enseignant":
            abort(403)
        selected = current_user
        if admin:
            raw = request.args.get("teacher_id", "")
            selected = db.session.get(User, int(raw)) if raw.isdigit() else None
            teachers = User.query.filter_by(role="enseignant").order_by(User.nom).all()
            if selected and selected.role != "enseignant":
                abort(400)
            if not selected:
                template = """
                <section class='panel'><h2>Dossiers professionnels</h2>
                <form method='get' class='inline-form'><label>Choisir un enseignant
                <select name='teacher_id' required>{% for t in teachers %}<option value='{{ t.id }}'>{{ t.nom }} · {{ t.email }}</option>{% endfor %}</select></label>
                <button class='btn primary'>Ouvrir le dossier</button></form>
                {% if not teachers %}<p>Aucun compte enseignant n'a encore été créé.</p>{% endif %}</section>"""
                return page("Dossiers professionnels", template, teachers=teachers)

        profile = Personnel.query.filter_by(user_id=selected.id).first()
        assignments = TeacherAssignment.query.filter_by(teacher_id=selected.id).order_by(
            TeacherAssignment.annee_academique.desc(), TeacherAssignment.classe, TeacherAssignment.cours
        ).all()
        contracts = StaffContract.query.filter_by(personnel_id=profile.id).order_by(
            StaffContract.date_debut.desc()
        ).all() if profile else []
        payrolls = PayrollRecord.query.filter_by(personnel_id=profile.id).order_by(
            PayrollRecord.periode.desc()
        ).limit(24).all() if profile else []
        totals = {}
        for item in assignments:
            totals[item.annee_academique] = totals.get(item.annee_academique, 0) + item.volume_horaire

        template = """
        {% if admin %}<section class='panel'><a href='/espace-professionnel'>← Tous les dossiers</a></section>{% endif %}
        <section class='hero'><div><small>ÉCOLE SHEMEC · DOSSIER PROFESSIONNEL</small>
        <h2>{{ selected.nom }}</h2><p>{{ profile.fonction if profile else 'Enseignant' }} · {{ selected.email }}</p></div><span>🇨🇩</span></section>
        <section class='panel'><h2>Fiche professionnelle</h2>
        {% if profile %}<div class='stats-grid'><div><small>Fonction</small><b>{{ profile.fonction }}</b></div><div><small>Statut</small><b>{{ profile.statut }}</b></div><div><small>Téléphone</small><b>{{ profile.telephone or 'Non renseigné' }}</b></div><div><small>E-mail</small><b>{{ profile.email or selected.email }}</b></div></div>
        {% else %}<p>Aucune fiche Personnel n'est encore liée à ce compte. L'administration doit créer la fiche et la relier au compte enseignant.</p>{% endif %}</section>
        <section class='panel'><h2>Affectations et charges horaires</h2><div class='table-wrap'><table>
        <tr><th>Année</th><th>Classe</th><th>Matière</th><th>Volume hebdomadaire</th></tr>
        {% for a in assignments %}<tr><td>{{ a.annee_academique }}</td><td>{{ a.classe }}</td><td>{{ a.cours }}</td><td>{{ a.volume_horaire }} h</td></tr>
        {% else %}<tr><td colspan='4'>Aucune affectation pédagogique.</td></tr>{% endfor %}</table></div>
        {% for year, hours in totals.items() %}<p><b>Total {{ year }} : {{ hours }} heures hebdomadaires affectées</b></p>{% endfor %}</section>
        <section class='panel'><h2>Contrats</h2><div class='table-wrap'><table><tr><th>Type</th><th>Début</th><th>Fin</th><th>Salaire de base</th><th>Statut</th></tr>
        {% for c in contracts %}<tr><td>{{ c.type_contrat }}</td><td>{{ c.date_debut }}</td><td>{{ c.date_fin or 'Indéterminée' }}</td><td>{{ c.salaire_base }} {{ c.devise }}</td><td>{{ c.statut }}</td></tr>
        {% else %}<tr><td colspan='5'>Aucun contrat enregistré.</td></tr>{% endfor %}</table></div></section>
        <section class='panel'><h2>Historique des bulletins de paie</h2><div class='table-wrap'><table>
        <tr><th>Période</th><th>Salaire de base</th><th>Avances</th><th>Déductions</th><th>Net à payer</th><th>Devise</th><th>Bulletin</th></tr>
        {% for p in payrolls %}<tr><td>{{ p.periode }}</td><td>{{ p.salaire_base }}</td><td>{{ p.avances }}</td><td>{{ p.deductions }}</td><td><b>{{ p.net_a_payer }}</b></td><td>{{ p.devise }}</td><td><a href='/paie/{{ p.id }}/bulletin.pdf'>PDF</a></td></tr>
        {% else %}<tr><td colspan='7'>Aucun bulletin de paie disponible.</td></tr>{% endfor %}</table></div></section>
        """
        return page("Mon dossier professionnel", template, admin=admin,
                    selected=selected, profile=profile, assignments=assignments,
                    contracts=contracts, payrolls=payrolls, totals=totals)
