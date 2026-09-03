import unittest

from core.skills.calculator import CalculatorSkill


class CalculatorSkillTests(unittest.TestCase):
    def setUp(self):
        self.calc = CalculatorSkill()

    def test_basic_arithmetic(self):
        ok, result = self.calc.evaluate("2 + 3 * 4")
        self.assertTrue(ok)
        self.assertEqual(result, 14)

    def test_portuguese_words(self):
        ok, result = self.calc.evaluate("15 vezes 3 mais 2")
        self.assertTrue(ok)
        self.assertEqual(result, 47)

    def test_dividido_por(self):
        ok, result = self.calc.evaluate("100 dividido por 4")
        self.assertTrue(ok)
        self.assertEqual(result, 25)

    def test_elevado_a(self):
        ok, result = self.calc.evaluate("2 elevado a 10")
        self.assertTrue(ok)
        self.assertEqual(result, 1024)

    def test_ao_quadrado(self):
        ok, result = self.calc.evaluate("5 ao quadrado")
        self.assertTrue(ok)
        self.assertEqual(result, 25)

    def test_percent_of(self):
        ok, result = self.calc.evaluate("10 por cento de 200")
        self.assertTrue(ok)
        self.assertEqual(result, 20)

    def test_bare_percent(self):
        ok, result = self.calc.evaluate("50%")
        self.assertTrue(ok)
        self.assertEqual(result, 0.5)

    def test_functions_with_parens(self):
        ok, result = self.calc.evaluate("raiz(9)")
        self.assertTrue(ok)
        self.assertEqual(result, 3)

    def test_function_of_phrasing(self):
        ok, result = self.calc.evaluate("raiz de 81")
        self.assertTrue(ok)
        self.assertEqual(result, 9)

    def test_decimal_comma(self):
        ok, result = self.calc.evaluate("1,5 + 1,5")
        self.assertTrue(ok)
        self.assertEqual(result, 3)

    def test_division_by_zero(self):
        ok, message = self.calc.evaluate("5 / 0")
        self.assertFalse(ok)
        self.assertIn("dividir", message.lower())

    def test_empty_expression(self):
        ok, message = self.calc.evaluate("")
        self.assertFalse(ok)

    def test_disallowed_characters_rejected(self):
        ok, message = self.calc.evaluate("__import__('os')")
        self.assertFalse(ok)

    def test_unknown_function_rejected(self):
        ok, message = self.calc.evaluate("evil(1)")
        self.assertFalse(ok)

    def test_attribute_access_rejected(self):
        ok, message = self.calc.evaluate("(1).__class__")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
