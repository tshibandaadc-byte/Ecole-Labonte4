"""Annonces et notifications internes de l'École Shemec."""
from datetime import datetime
from flask import abort, redirect, request, url_for, flash
from flask_login import current_user, login_required


def register_notice_routes(app, db, page):
    class SchoolNotice(db.Model):
        __tablename__ = "school_notice"
        id = db.Column(db.Integer, primary_key=True)
        titre = db.Column(db.String(160), nullable=False)
        contenu = db.Column(db.Text, nullable=False)
        audience = db.Column(db.String(20), nullable=False, default="Tous")
        actif = db.Column(db.Boolean, nullable=False, default=True)
        auteur_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        cree_le = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
        auteur = db.relationship("User")

    class NoticeRead(db.Model):
        __tablename__ = "school_notice_read"
        id = db.Column(db.Integer, primary_key=True)
        notice_id = db.Column(db.Integer, db.ForeignKey("school_notice.id"), nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        lu_le = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
        __table_args__ = (db.UniqueConstraint("notice_id", "user_id", name="uq_notice_user_read"),)

    with app.app_context():
        db.create_all()

    def visible_to_user(notice):
        role = current_user.role
        return role == "admin" or notice.audience == "Tous" or (
            (role == "parent" and notice.audience == "Parents") or
            (role == "eleve" and notice.audience == "Élèves") or
            (role == "enseignant" and notice.audience == "Enseignants")
        )

    @app.route("/notifications")
    @login_required
    def notifications():
        notices = SchoolNotice.query.filter_by(actif=True).order_by(SchoolNotice.cree_le.desc()).all()
        notices = [n for n in notices if visible_to_user(n)]
        read_ids = {r.notice_id for r in NoticeRead.query.filter_by(user_id=current_user.id).all()}
        template = """
        <section class='hero'><div><small>ÉCOLE SHEMEC · COMMUNICATION</small><h2>Mes notifications</h2>
        <p>Annonces officielles et informations de votre établissement.</p></div><span>🇨🇩</span></section>
        <section class='panel'><div class='table-wrap'><table><tr><th>Annonce</th><th>Public</th><th>Date</th><th>État</th><th>Action</th></tr>
        {% for n in notices %}<tr><td><b>{{ n.titre }}</b><br>{{ n.contenu }}</td><td>{{ n.audience }}</td>
        <td>{{ n.cree_le.strftime('%d/%m/%Y %H:%M') }}</td><td>{{ 'Lue' if n.id in read_ids else 'Non lue' }}</td>
        <td>{% if n.id not in read_ids %}<form method='post' action='/notifications/{{ n.id }}/lire'><button class='btn primary'>Marquer comme lue</button></form>{% endif %}</td></tr>
        {% else %}<tr><td colspan='5'>Aucune annonce pour le moment.</td></tr>{% endfor %}</table></div></section>"""
        return page("Mes notifications", template, notices=notices, read_ids=read_ids)

    @app.post("/notifications/<int:notice_id>/lire")
    @login_required
    def mark_notice_read(notice_id):
        notice = db.session.get(SchoolNotice, notice_id)
        if not notice or not notice.actif or not visible_to_user(notice):
            abort(404)
        existing = NoticeRead.query.filter_by(notice_id=notice.id, user_id=current_user.id).first()
        if not existing:
            db.session.add(NoticeRead(notice_id=notice.id, user_id=current_user.id))
            db.session.commit()
        return redirect(url_for("notifications"))

    @app.route("/admin/annonces", methods=["GET", "POST"])
    @login_required
    def manage_notices():
        if current_user.role != "admin":
            abort(403)
        audiences = ["Tous", "Parents", "Élèves", "Enseignants"]
        if request.method == "POST":
            titre = request.form.get("titre", "").strip()
            contenu = request.form.get("contenu", "").strip()
            audience = request.form.get("audience", "Tous")
            if not titre or not contenu or len(titre) > 160 or audience not in audiences:
                flash("Vérifiez le titre, le contenu et le public de l'annonce.", "error")
            else:
                db.session.add(SchoolNotice(titre=titre, contenu=contenu,
                    audience=audience, auteur_id=current_user.id))
                db.session.commit()
                flash("Annonce publiée dans les notifications de son public.", "success")
                return redirect(url_for("manage_notices"))
        notices = SchoolNotice.query.order_by(SchoolNotice.cree_le.desc()).limit(100).all()
        template = """
        <section class='hero'><div><small>ÉCOLE SHEMEC · ADMINISTRATION</small><h2>Gestion des annonces</h2>
        <p>Publiez une information destinée aux familles, élèves ou enseignants.</p></div><span>🇨🇩</span></section>
        <section class='panel'><h2>Nouvelle annonce</h2><form method='post'>
        <label>Titre<input name='titre' maxlength='160' required></label>
        <label>Message<textarea name='contenu' rows='5' required></textarea></label>
        <label>Destinataires<select name='audience'>{% for a in audiences %}<option>{{ a }}</option>{% endfor %}</select></label>
        <button class='btn primary'>Publier l'annonce</button></form></section>
        <section class='panel'><h2>Historique des annonces</h2><div class='table-wrap'><table>
        <tr><th>Titre</th><th>Public</th><th>Date</th><th>Statut</th><th></th></tr>
        {% for n in notices %}<tr><td>{{ n.titre }}</td><td>{{ n.audience }}</td><td>{{ n.cree_le.strftime('%d/%m/%Y') }}</td>
        <td>{{ 'Active' if n.actif else 'Archivée' }}</td><td>{% if n.actif %}<form method='post' action='/admin/annonces/{{ n.id }}/archiver'><button class='btn'>Archiver</button></form>{% endif %}</td></tr>
        {% else %}<tr><td colspan='5'>Aucune annonce publiée.</td></tr>{% endfor %}</table></div></section>"""
        return page("Gestion des annonces", template, notices=notices, audiences=audiences)

    @app.post("/admin/annonces/<int:notice_id>/archiver")
    @login_required
    def archive_notice(notice_id):
        if current_user.role != "admin":
            abort(403)
        notice = db.session.get(SchoolNotice, notice_id)
        if not notice:
            abort(404)
        notice.actif = False
        db.session.commit()
        flash("Annonce archivée.", "success")
        return redirect(url_for("manage_notices"))
