"""Unit conversion: "10 km em milhas", "30 graus celsius em fahrenheit", ...

Handles length, mass, volume, speed and temperature. Everything except
temperature goes through a linear "multiply by a factor to reach the base
unit" table, so adding a new unit is a one-line addition. Temperature needs
its own formulas because Celsius/Fahrenheit/Kelvin are affine, not linear.
"""

import re

# Each entry: canonical name -> (dimension, factor to the dimension's base unit)
_LENGTH_BASE = "m"
_MASS_BASE = "g"
_VOLUME_BASE = "l"
_SPEED_BASE = "m/s"

_UNITS = {
    # length (base: meters)
    "mm": ("length", 0.001),
    "cm": ("length", 0.01),
    "m": ("length", 1.0),
    "km": ("length", 1000.0),
    "in": ("length", 0.0254),
    "polegada": ("length", 0.0254),
    "polegadas": ("length", 0.0254),
    "ft": ("length", 0.3048),
    "pe": ("length", 0.3048),
    "pes": ("length", 0.3048),
    "yd": ("length", 0.9144),
    "jarda": ("length", 0.9144),
    "mi": ("length", 1609.344),
    "milha": ("length", 1609.344),
    "milhas": ("length", 1609.344),
    # mass (base: grams)
    "mg": ("mass", 0.001),
    "g": ("mass", 1.0),
    "kg": ("mass", 1000.0),
    "lb": ("mass", 453.59237),
    "libra": ("mass", 453.59237),
    "libras": ("mass", 453.59237),
    "oz": ("mass", 28.349523125),
    "onca": ("mass", 28.349523125),
    "oncas": ("mass", 28.349523125),
    "ton": ("mass", 1_000_000.0),
    "tonelada": ("mass", 1_000_000.0),
    # volume (base: liters)
    "ml": ("volume", 0.001),
    "l": ("volume", 1.0),
    "litro": ("volume", 1.0),
    "litros": ("volume", 1.0),
    "gal": ("volume", 3.785411784),
    "galao": ("volume", 3.785411784),
    "galoes": ("volume", 3.785411784),
    # speed (base: m/s)
    "m/s": ("speed", 1.0),
    "km/h": ("speed", 1 / 3.6),
    "kmh": ("speed", 1 / 3.6),
    "mph": ("speed", 0.44704),
    "no": ("speed", 0.514444),
    "nos": ("speed", 0.514444),
}

_TEMP_UNITS = {"c", "celsius", "f", "fahrenheit", "k", "kelvin"}

_UNIT_ALIASES = {
    "metro": "m",
    "metros": "m",
    "centimetro": "cm",
    "centimetros": "cm",
    "milimetro": "mm",
    "milimetros": "mm",
    "quilometro": "km",
    "quilometros": "km",
    "quilo": "kg",
    "quilos": "kg",
    "quilograma": "kg",
    "quilogramas": "kg",
    "grama": "g",
    "gramas": "g",
    "miligrama": "mg",
    "miligramas": "mg",
}

_PARSE_RE = re.compile(
    r"^\s*(-?\d+(?:[.,]\d+)?)\s*([a-zçãáéíóúâêôõ/]+)\s*"
    r"(?:para|em|pra|to|->|=)\s*([a-zçãáéíóúâêôõ/]+)\s*$",
    re.IGNORECASE,
)


def _strip_accents(text):
    replacements = str.maketrans("áàâãéèêíìîóòôõúùûç", "aaaaeeeiiiooooiuuc")
    return text.translate(replacements)


def _canon_unit(raw):
    unit = _strip_accents(str(raw or "").strip().lower())
    unit = _UNIT_ALIASES.get(unit, unit)
    return unit


class ConverterSkill:
    """Parses and performs simple, well-known unit conversions."""

    def parse(self, text):
        """Returns ``(value, from_unit, to_unit)`` or ``None`` if unparsable."""

        match = _PARSE_RE.match(str(text or "").strip())
        if not match:
            return None

        raw_value, raw_from, raw_to = match.groups()

        try:
            value = float(raw_value.replace(",", "."))
        except ValueError:
            return None

        return value, _canon_unit(raw_from), _canon_unit(raw_to)

    def convert(self, text):
        """Returns ``(ok, result_or_message)``."""

        parsed = self.parse(text)
        if parsed is None:
            return False, (
                "Não entendi essa conversão. Tente algo como "
                "'10 quilômetros em milhas'."
            )

        value, from_unit, to_unit = parsed

        if from_unit in _TEMP_UNITS or to_unit in _TEMP_UNITS:
            return self._convert_temperature(value, from_unit, to_unit)

        return self._convert_linear(value, from_unit, to_unit)

    def describe(self, text):
        """Returns ``(ok, sentence)`` — a ready-to-speak Portuguese sentence."""

        parsed = self.parse(text)
        ok, result = self.convert(text)

        if not ok or parsed is None:
            return False, result

        value, from_unit, to_unit = parsed

        return True, (
            f"{self._fmt(value)} {from_unit} são aproximadamente "
            f"{self._fmt(result)} {to_unit}."
        )

    @staticmethod
    def _fmt(number):
        if isinstance(number, float) and number.is_integer():
            number = int(number)
        return number

    # -----------------------------------------------------------
    # LINEAR (length / mass / volume / speed)
    # -----------------------------------------------------------

    def _convert_linear(self, value, from_unit, to_unit):
        from_info = _UNITS.get(from_unit)
        to_info = _UNITS.get(to_unit)

        if from_info is None or to_info is None:
            unknown = from_unit if from_info is None else to_unit
            return False, f"Não conheço a unidade '{unknown}'."

        from_dimension, from_factor = from_info
        to_dimension, to_factor = to_info

        if from_dimension != to_dimension:
            return False, (
                f"Não dá para converter {from_unit} em {to_unit}: "
                "são grandezas diferentes."
            )

        base_value = value * from_factor
        result = base_value / to_factor

        return True, round(result, 6)

    # -----------------------------------------------------------
    # TEMPERATURE
    # -----------------------------------------------------------

    def _convert_temperature(self, value, from_unit, to_unit):
        if from_unit not in _TEMP_UNITS or to_unit not in _TEMP_UNITS:
            return False, "Não dá para misturar temperatura com outra grandeza."

        from_key = from_unit[0]
        to_key = to_unit[0]

        # Normalize to Celsius first, then to the target.
        if from_key == "c":
            celsius = value
        elif from_key == "f":
            celsius = (value - 32) * 5 / 9
        else:  # kelvin
            celsius = value - 273.15

        if to_key == "c":
            result = celsius
        elif to_key == "f":
            result = celsius * 9 / 5 + 32
        else:  # kelvin
            result = celsius + 273.15

        return True, round(result, 2)
