"""A safe arithmetic calculator.

The LLM router hands us a free-form Portuguese expression like
``"15 vezes 3 mais 2"`` or ``"raiz de 81"`` and we need a number back —
without ever running ``eval()`` on untrusted text. This module:

1. Normalizes common Portuguese math words to symbols/functions.
2. Parses the result with :mod:`ast` into a syntax tree.
3. Walks that tree with a strict whitelist evaluator that only allows
   numeric literals, the basic arithmetic operators, and a small set of
   named functions/constants — anything else (attribute access, function
   calls to unknown names, string literals, comprehensions, ...) is
   rejected instead of executed.
"""

import ast
import math
import operator
import re

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_FUNCTIONS = {
    "raiz": math.sqrt,
    "sqrt": math.sqrt,
    "abs": abs,
    "absoluto": abs,
    "round": round,
    "arredondar": round,
    "seno": math.sin,
    "sin": math.sin,
    "cosseno": math.cos,
    "cos": math.cos,
    "tangente": math.tan,
    "tan": math.tan,
    "log": math.log10,
    "ln": math.log,
    "min": min,
    "max": max,
}

_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}

# Longest phrases first so "dividido por" matches before a bare "por".
_WORD_REPLACEMENTS = [
    (r"\belevado\s+a\b", "**"),
    (r"\bao\s+quadrado\b", "**2"),
    (r"\bao\s+cubo\b", "**3"),
    (r"\bdividido\s+por\b", "/"),
    (r"\bdividido\b", "/"),
    (r"\bmultiplicado\s+por\b", "*"),
    (r"\bmultiplicado\b", "*"),
    (r"\bmais\b", "+"),
    (r"\bmenos\b", "-"),
    (r"\bvezes\b", "*"),
    (r"\bx\b", "*"),
]

# "10 por cento de 200" / "10% de 200" -> "((10/100)*200)"
_PERCENT_OF = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(?:%|por\s+cento)\s+de\s+(-?\d+(?:\.\d+)?)"
)

# A bare "10%" -> "(10/100)"
_PERCENT_BARE = re.compile(r"(-?\d+(?:\.\d+)?)\s*%")

# "raiz de 81" / "seno de 30" -> "raiz(81)" / "seno(30)"
_FUNCTION_OF = re.compile(
    r"\b(raiz|sqrt|seno|sin|cosseno|cos|tangente|tan|log|ln|absoluto|abs|arredondar|round)"
    r"\s+de\s+(-?\d+(?:\.\d+)?)"
)

_ALLOWED_CHARS = re.compile(r"^[0-9a-zA-Zà-úÀ-Ú_+\-*/%().,\s^]*$")


class CalculatorSkill:
    """Evaluates simple arithmetic expressions, safely."""

    def normalize_expression(self, text):
        expression = str(text or "").strip().lower()
        expression = expression.replace(",", ".")

        expression = _PERCENT_OF.sub(r"((\1/100)*\2)", expression)
        expression = _PERCENT_BARE.sub(r"(\1/100)", expression)
        expression = _FUNCTION_OF.sub(r"\1(\2)", expression)

        for pattern, replacement in _WORD_REPLACEMENTS:
            expression = re.sub(pattern, replacement, expression)

        # "^" is a very common way people type "power of" outside math class.
        expression = expression.replace("^", "**")

        return expression.strip()

    def evaluate(self, text):
        """Returns ``(ok, result_or_message)``.

        ``result_or_message`` is a ``float``/``int`` on success, or a
        human-readable Portuguese error string on failure.
        """

        expression = self.normalize_expression(text)

        if not expression:
            return False, "Não recebi nenhuma expressão para calcular."

        if not _ALLOWED_CHARS.match(expression):
            return False, "Essa expressão tem caracteres que não sei calcular."

        try:
            tree = ast.parse(expression, mode="eval")
            value = self._eval_node(tree.body)
        except ZeroDivisionError:
            return False, "Não dá para dividir por zero."
        except (SyntaxError, TypeError, ValueError, KeyError):
            return False, "Não consegui entender essa conta."
        except OverflowError:
            return False, "Esse número ficou grande demais para calcular."

        if isinstance(value, float) and value.is_integer():
            value = int(value)

        return True, value

    # -----------------------------------------------------------
    # AST WALKER (whitelist only)
    # -----------------------------------------------------------

    def _eval_node(self, node):
        if isinstance(node, ast.Expression):
            return self._eval_node(node.body)

        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("constante não numérica")

        if isinstance(node, ast.BinOp):
            op = _BIN_OPS.get(type(node.op))
            if op is None:
                raise ValueError("operador não suportado")
            return op(self._eval_node(node.left), self._eval_node(node.right))

        if isinstance(node, ast.UnaryOp):
            op = _UNARY_OPS.get(type(node.op))
            if op is None:
                raise ValueError("operador unário não suportado")
            return op(self._eval_node(node.operand))

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("chamada inválida")

            function = _FUNCTIONS.get(node.func.id)
            if function is None:
                raise ValueError(f"função desconhecida: {node.func.id}")

            args = [self._eval_node(arg) for arg in node.args]
            return function(*args)

        if isinstance(node, ast.Name):
            if node.id in _CONSTANTS:
                return _CONSTANTS[node.id]
            raise ValueError(f"nome desconhecido: {node.id}")

        raise ValueError("expressão não suportada")
