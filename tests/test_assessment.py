import unittest

from assessment import appreciation, classement_classe, decision_passage, moyenne_notes


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
        results = [(1, 15), (1, 17), (2, 16), (3, 10), (4, 16)]
        self.assertEqual(classement_classe(results, 1)["rang"], 1)
        self.assertEqual(classement_classe(results, 2)["rang"], 2)
        self.assertEqual(classement_classe(results, 4)["rang"], 2)
        self.assertEqual(classement_classe(results, 3)["effectif"], 4)

    def test_student_without_grade_is_not_ranked(self):
        result = classement_classe([(1, 12)], 9)
        self.assertIsNone(result["rang"])
        self.assertEqual(result["effectif"], 1)


if __name__ == "__main__":
    unittest.main()
