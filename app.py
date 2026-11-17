"""Point d'entrée de l'application web École Shemec."""
import shemec_app as core
from shemec_app import *
from progression import register_progression_routes
from class_management import register_class_routes
from pedagogy import register_timetable_routes
from teacher_followup import register_teacher_followup
from teacher_profile import register_teacher_profile
from parent_portal import register_parent_portal

# Ajoute le nouvel écran dans la navigation commune sans toucher aux autres pages.
core.BASE = core.BASE.replace(
    "<a href='/eleves'>♙ Élèves</a>",
    "<a href='/eleves'>♙ Élèves</a><a href='/classes'>▦ Classes & titulaires</a>"
)

core.BASE = core.BASE.replace(
    "<a href='/historique'>▤ Historique académique</a>",
    "<a href='/historique'>▤ Historique académique</a><a href='/passages'>↗ Passages de classe</a>"
)

register_progression_routes(
    app, db, Student, Grade, Enrollment, StudentHistory, AcademicYear, page
)
register_class_routes(
    app, db, Student, User, TeacherAssignment, AcademicYear, page
)
register_timetable_routes(app, db, User, TeacherAssignment, CourseSlot, page, AcademicYear)
register_teacher_followup(app, db, User, page)
register_teacher_profile(app, db, User, Personnel, StaffContract, PayrollRecord, TeacherAssignment, page)
register_parent_portal(app, db, Student, Grade, Attendance, SchoolFee, FeePayment, parent_children, page)

core.BASE = core.BASE.replace(
    "<a href='/horaire'>▦ Emploi du temps</a>",
    "<a href='/horaire'>▦ Emploi du temps</a><a href='/planning-cours'>▤ Planning des cours</a>"
)

core.BASE = core.BASE.replace(
    "<a href='/planning-cours'>▤ Planning des cours</a>",
    "<a href='/planning-cours'>▤ Planning des cours</a><a href='/suivi-enseignant'>♧ Suivi enseignants</a>"
)

core.BASE = core.BASE.replace(
    "<a href='/mon-salaire'>◈ Mon salaire</a>",
    "<a href='/mon-salaire'>◈ Mon salaire</a><a href='/espace-professionnel'>♙ Dossier professionnel</a>"
)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)),
            debug=os.getenv("FLASK_DEBUG") == "1")

