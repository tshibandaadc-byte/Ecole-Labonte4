"""Calculs scolaires centralisés pour les résultats de l'École Shemec.

Les notes sont sur 20. Le classement est calculé sur les notes réellement
enregistrées pour la même classe, année académique et période.
"""
from collections import defaultdict


def moyenne_notes(notes):
    valeurs = [float(note) for note in notes]
    if not valeurs:
        return None
    return round(sum(valeurs) / len(valeurs), 2)


def appreciation(moyenne):
    if moyenne is None:
        return "En attente"
    if moyenne >= 16:
        return "Très bien"
    if moyenne >= 14:
        return "Bien"
    if moyenne >= 12:
        return "Assez bien"
    if moyenne >= 10:
        return "Passable"
    return "Insuffisant"


def decision_passage(moyenne, seuil=10):
    if moyenne is None:
        return "En attente de notes"
    return "Admis" if moyenne >= float(seuil) else "À renforcer"


def classement_classe(resultats, eleve_id):
    """Classe les élèves par moyenne décroissante; les ex æquo partagent le rang.

    resultats est une séquence de couples (student_id, note).
    """
    notes_par_eleve = defaultdict(list)
    for student_id, note in resultats:
        notes_par_eleve[student_id].append(note)
    moyennes = {
        student_id: moyenne_notes(notes)
        for student_id, notes in notes_par_eleve.items()
    }
    if eleve_id not in moyennes:
        return {"rang": None, "effectif": len(moyennes), "moyenne_classe": None}
    triees = sorted(moyennes.values(), reverse=True)
    moyenne = moyennes[eleve_id]
    rang = triees.index(moyenne) + 1
    return {
        "rang": rang,
        "effectif": len(moyennes),
        "moyenne_classe": round(sum(triees) / len(triees), 2) if triees else None,
    }
