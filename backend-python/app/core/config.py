# =========================================
# app/core/config.py — Configuration centrale
# =========================================
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    DB_NAME: str = os.getenv("DB_NAME", "ecole_la_bonte")

    JWT_SECRET: str = os.getenv("JWT_SECRET", "change_moi_en_prod")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = int(os.getenv("JWT_EXPIRES_MINUTES", "10080"))  # 7 jours

    # Domaines autorisés à appeler l'API (séparés par des virgules dans .env).
    # Exemple : CORS_ORIGINS=https://etudiant.labonte-ecole.ac,https://pay.labonte-ecole.ac
    CORS_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()
    ]

    # Environnement d'exécution : "dev" tolère un secret par défaut, "prod" l'interdit.
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "dev")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()


def verifier_config_production() -> None:
    """
    Empêche le démarrage en production avec des réglages non sécurisés.
    Appelée une fois au lancement du serveur (voir main.py).
    """
    if settings.ENVIRONMENT != "prod":
        return
    if settings.JWT_SECRET == "change_moi_en_prod":
        raise RuntimeError(
            "JWT_SECRET n'a pas été changé. Définis une vraie valeur secrète "
            "dans la variable d'environnement JWT_SECRET avant de lancer en production."
        )
    if len(settings.JWT_SECRET) < 32:
        raise RuntimeError("JWT_SECRET est trop court (32 caractères minimum recommandés).")
    if not settings.CORS_ORIGINS or settings.CORS_ORIGINS == ["http://localhost:3000"]:
        raise RuntimeError(
            "CORS_ORIGINS n'a pas été configuré pour la production. "
            "Définis les vrais domaines autorisés dans la variable CORS_ORIGINS."
        )
