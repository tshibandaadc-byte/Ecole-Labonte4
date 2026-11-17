import unittest

from assessment import appreciation, classement_classe, decision_passage, moyenne_notes, resultats_annuels


class AssessmentTests(unittest.TestCase):
    def test_average_is_rounded_and_empty_is_none(self):
        self.assertEqual(moyenne_notes([12, 15, 14]), 13.67)
        self.assertIsNone(moyenne_notes([]))

    def test_appreciations_and_passage_threshold(self):
        self.assertEqual(appreciation(17), "Très bien")
        self.assertEqual(appreciation(14), "Bien")
        self.assertEqual(appreciation(11), "Passable")
        self.assertEqual(appreciation(8), "Insuffisant")
        self.assertEqual(decision_passage(10), "Admis")
        self.assertEqual(decision_passage(9.99), "À renforcer")
        self.assertEqual(decision_passage(None), "En attente de notes")

    def test_class_ranking_and_ties(self):
        results = [(1, 18), (1, 16), (2, 16), (3, 10), (4, 16)]
        self.assertEqual(classement_classe(results, 1)["rang"], 1)
        self.assertEqual(classement_classe(results, 2)["rang"], 2)
        self.assertEqual(classement_classe(results, 4)["rang"], 2)
        self.assertEqual(classement_classe(results, 3)["effectif"], 4)

    def test_student_without_grade_is_not_ranked(self):
        result = classement_classe([(1, 12)], 9)
        self.assertIsNone(result["rang"])
        self.assertEqual(result["effectif"], 1)


    def test_annual_results_keep_final_exam_separate(self):
        class Note:
            def __init__(self, cours, note, periode):
                self.cours, self.note, self.periode = cours, note, periode
        result = resultats_annuels([
            Note("Mathématiques", 12, "Trimestre 1"),
            Note("Mathématiques", 14, "Trimestre 2"),
            Note("Mathématiques", 16, "Examen final"),
            Note("Français", 10, "Trimestre 1"),
        ])
        maths = result["matieres"][1]
        self.assertEqual(maths["matiere"], "Mathématiques")
        self.assertEqual(maths["moyenne"], 14.0)
        self.assertEqual(maths["moyenne_examen_final"], 16.0)
        self.assertEqual(result["moyenne_generale"], 12.0)

    def test_annual_results_empty(self):
        self.assertIsNone(resultats_annuels([])["moyenne_generale"])


if __name__ == "__main__":
    unittest.main()
