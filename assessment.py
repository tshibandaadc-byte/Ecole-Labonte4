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


def resultats_annuels(notes):
    """Agrège les notes par matière pour une année académique.

    Chaque matière a une moyenne arithmétique des notes enregistrées.
    Les examens trimestriels et finaux restent identifiables séparément.
    Aucune pondération officielle n'est supposée.
    """
    matieres = defaultdict(list)
    trimestriels = defaultdict(list)
    examens_trimestriels = defaultdict(list)
    examens_finaux = defaultdict(list)
    for item in notes:
        matiere = item.cours
        valeur = float(item.note)
        matieres[matiere].append(valeur)
        periode = (item.periode or "").strip().lower()
        if periode in ("examen final", "examen de fin d'année", "examen annuel", "examen"):
            examens_finaux[matiere].append(valeur)
        elif periode in ("examen trimestriel", "examens trimestriels"):
            examens_trimestriels[matiere].append(valeur)
        elif periode.startswith("trimestre"):
            trimestriels[matiere].append(valeur)
    lignes = []
    for matiere in sorted(matieres, key=str.casefold):
        lignes.append({
            "matiere": matiere,
            "nombre": len(matieres[matiere]),
            "moyenne": moyenne_notes(matieres[matiere]),
            "moyenne_trimestrielle": moyenne_notes(trimestriels[matiere]),
            "moyenne_examens_trimestriels": moyenne_notes(examens_trimestriels[matiere]),
            "moyenne_examen_final": moyenne_notes(examens_finaux[matiere]),
        })
    moyenne_generale = moyenne_notes(ligne["moyenne"] for ligne in lignes)
    return {"matieres": lignes, "moyenne_generale": moyenne_generale}


def classement_annuel(resultats, eleve_id):
    """Classe les élèves sur leur moyenne annuelle par matière, sans pondération."""
    par_eleve = defaultdict(lambda: defaultdict(list))
    for student_id, matiere, note in resultats:
        par_eleve[student_id][matiere].append(note)
    moyennes = {
        student_id: moyenne_notes(moyenne_notes(notes) for notes in matieres.values())
        for student_id, matieres in par_eleve.items()
    }
    if eleve_id not in moyennes:
        return {"rang": None, "effectif": len(moyennes), "moyenne_classe": None}
    triees = sorted(moyennes.values(), reverse=True)
    moyenne = moyennes[eleve_id]
    return {"rang": triees.index(moyenne) + 1, "effectif": len(moyennes),
            "moyenne_classe": moyenne_notes(triees)}
