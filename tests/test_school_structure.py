import unittest

from school_structure import (
    NIVEAUX_SCOLAIRES,
    OPTIONS_SECONDAIRE,
    classe_valide,
    option_valide,
)


class SchoolStructureTests(unittest.TestCase):
    def test_expected_school_cycles_are_available(self):
        self.assertEqual(tuple(NIVEAUX_SCOLAIRES), ("Maternelle", "Primaire", "Secondaire"))
        self.assertEqual(len(NIVEAUX_SCOLAIRES["Maternelle"]), 3)
        self.assertEqual(len(NIVEAUX_SCOLAIRES["Primaire"]), 6)
        self.assertEqual(len(NIVEAUX_SCOLAIRES["Secondaire"]), 6)

    def test_valid_classes(self):
        self.assertTrue(classe_valide("Maternelle", "1re année maternelle"))
        self.assertTrue(classe_valide("Primaire", "6e année primaire"))
        self.assertTrue(classe_valide("Secondaire", "6e secondaire"))

    def test_rejects_class_from_another_cycle(self):
        self.assertFalse(classe_valide("Maternelle", "1re secondaire"))
        self.assertFalse(classe_valide("Primaire", "3e année maternelle"))
        self.assertFalse(classe_valide("Inconnu", "1re secondaire"))

    def test_options_only_apply_to_secondary(self):
        self.assertTrue(option_valide("Secondaire", OPTIONS_SECONDAIRE[0]))
        self.assertFalse(option_valide("Secondaire", "Option inventée"))
        self.assertTrue(option_valide("Primaire", "Aucune"))
        self.assertFalse(option_valide("Primaire", "Scientifique"))


if __name__ == "__main__":
    unittest.main()
