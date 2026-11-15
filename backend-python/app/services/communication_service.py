# =========================================
# app/services/communication_service.py
# =========================================
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, text

from app.models.models import Communique, Conversation, Message
from app.schemas.autres_schemas import CommuniqueRequete


# --- Communiqués ---
def publier_communique(db: Session, donnees: CommuniqueRequete, auteur_id: int) -> Communique:
    communique = Communique(
        auteur_id=auteur_id, titre=donnees.titre, contenu=donnees.contenu,
        categorie=donnees.categorie, cible=donnees.cible,
    )
    db.add(communique)
    db.commit()
    db.refresh(communique)
    return communique


def lister_communiques(db: Session, cible: str | None = None, limite: int = 50):
    requete = db.query(Communique)
    if cible:
        requete = requete.filter(or_(Communique.cible == cible, Communique.cible == "tous"))
    return requete.order_by(Communique.date_pub.desc()).limit(limite).all()


# --- Messagerie ---
def obtenir_ou_creer_conversation(db: Session, user1_id: int, user2_id: int) -> Conversation:
    a, b = sorted([user1_id, user2_id])
    conversation = db.query(Conversation).filter(
        Conversation.user1_id == a, Conversation.user2_id == b
    ).first()
    if conversation:
        return conversation

    conversation = Conversation(user1_id=a, user2_id=b)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def envoyer_message(db: Session, expediteur_id: int, destinataire_id: int, contenu: str) -> Message:
    conversation = obtenir_ou_creer_conversation(db, expediteur_id, destinataire_id)
    message = Message(conversation_id=conversation.id, expediteur_id=expediteur_id, contenu=contenu)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def lister_conversations(db: Session, utilisateur_id: int):
    resultat = db.execute(
        text(
            """
            SELECT c.id AS conversation_id,
                   CASE WHEN c.user1_id = :uid THEN c.user2_id ELSE c.user1_id END AS autre_utilisateur_id,
                   u.nom, u.prenom, u.photo_url, u.role,
                   m.contenu AS dernier_message, m.date_envoi AS dernier_envoi,
                   (SELECT COUNT(*) FROM messages
                    WHERE conversation_id = c.id AND lu = FALSE AND expediteur_id != :uid) AS non_lus
            FROM conversations c
            JOIN utilisateurs u ON u.id = CASE WHEN c.user1_id = :uid THEN c.user2_id ELSE c.user1_id END
            LEFT JOIN LATERAL (
              SELECT contenu, date_envoi FROM messages
              WHERE conversation_id = c.id ORDER BY date_envoi DESC LIMIT 1
            ) m ON TRUE
            WHERE c.user1_id = :uid OR c.user2_id = :uid
            ORDER BY m.date_envoi DESC NULLS LAST
            """
        ),
        {"uid": utilisateur_id},
    )
    return [dict(row._mapping) for row in resultat]


def lister_messages(db: Session, conversation_id: int, utilisateur_id: int):
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.date_envoi.asc()).all()

    # Marquer comme lus les messages reçus
    db.query(Message).filter(
        and_(
            Message.conversation_id == conversation_id,
            Message.expediteur_id != utilisateur_id,
            Message.lu == False,  # noqa: E712
        )
    ).update({"lu": True})
    db.commit()

    return messages
