"""Point d'entrée de l'application web École Shemec."""
import shemec_app as core
from shemec_app import *
from progression import register_progression_routes

# Ajoute le nouvel écran dans la navigation commune sans toucher aux autres pages.
core.BASE = core.BASE.replace(
    "<a href='/historique'>▤ Historique académique</a>",
    "<a href='/historique'>▤ Historique académique</a><a href='/passages'>↗ Passages de classe</a>"
)

register_progression_routes(
    app, db, Student, Grade, Enrollment, StudentHistory, AcademicYear, page
)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)),
            debug=os.getenv("FLASK_DEBUG") == "1")
