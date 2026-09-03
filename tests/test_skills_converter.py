import unittest

from core.skills.converter import ConverterSkill


class ConverterSkillTests(unittest.TestCase):
    def setUp(self):
        self.converter = ConverterSkill()

    def test_parse_basic(self):
        parsed = self.converter.parse("10 km em milhas")
        self.assertEqual(parsed, (10.0, "km", "milhas"))

    def test_parse_returns_none_for_garbage(self):
        self.assertIsNone(self.converter.parse("isso não é uma conversão"))

    def test_length_km_to_miles(self):
        ok, result = self.converter.convert("10 km em milhas")
        self.assertTrue(ok)
        self.assertAlmostEqual(result, 6.213712, places=4)

    def test_length_aliases(self):
        ok, result = self.converter.convert("1 metro em centimetros")
        self.assertTrue(ok)
        self.assertEqual(result, 100)

    def test_mass_kg_to_lb(self):
        ok, result = self.converter.convert("1 kg em lb")
        self.assertTrue(ok)
        self.assertAlmostEqual(result, 2.204623, places=3)

    def test_volume_liters_to_ml(self):
        ok, result = self.converter.convert("2 l em ml")
        self.assertTrue(ok)
        self.assertEqual(result, 2000)

    def test_temperature_c_to_f(self):
        ok, result = self.converter.convert("100 celsius em fahrenheit")
        self.assertTrue(ok)
        self.assertEqual(result, 212)

    def test_temperature_f_to_c(self):
        ok, result = self.converter.convert("32 fahrenheit em celsius")
        self.assertTrue(ok)
        self.assertEqual(result, 0)

    def test_temperature_c_to_kelvin(self):
        ok, result = self.converter.convert("0 celsius em kelvin")
        self.assertTrue(ok)
        self.assertEqual(result, 273.15)

    def test_unknown_unit(self):
        ok, message = self.converter.convert("10 parsecs em km")
        self.assertFalse(ok)
        self.assertIn("parsecs", message)

    def test_mismatched_dimensions(self):
        ok, message = self.converter.convert("10 kg em km")
        self.assertFalse(ok)

    def test_unparsable_text(self):
        ok, message = self.converter.convert("blablabla")
        self.assertFalse(ok)

    def test_describe_builds_sentence(self):
        ok, sentence = self.converter.describe("10 km em milhas")
        self.assertTrue(ok)
        self.assertIn("km", sentence)
        self.assertIn("milhas", sentence)

    def test_describe_propagates_errors(self):
        ok, sentence = self.converter.describe("blablabla")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
