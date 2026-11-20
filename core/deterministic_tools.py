"""Ferramentas determinísticas locais sem eval ou execução de código arbitrário."""

from __future__ import annotations

import ast
import math
import operator
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class ToolResult:
    name: str
    matched: bool
    success: bool
    content: str
    value: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DeterministicTool(Protocol):
    name: str

    def execute(self, text: str) -> ToolResult | None:
        ...


_BINARY_OPERATORS: dict[type[ast.operator], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS: dict[type[ast.unaryop], Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_FUNCTIONS: dict[str, Any] = {
    "abs": abs,
    "ceil": math.ceil,
    "cos": math.cos,
    "exp": math.exp,
    "floor": math.floor,
    "log": math.log,
    "log10": math.log10,
    "max": max,
    "min": min,
    "round": round,
    "sin": math.sin,
    "sqrt": math.sqrt,
    "tan": math.tan,
}
_CONSTANTS = {"e": math.e, "pi": math.pi}
_CALCULATION_PREFIX = re.compile(
    r"(?i)^(?:quanto\s+(?:é|e|da)|calcule|calcular|resolva|resolver|"
    r"resultado\s+de|compute|evaluate|what\s+is)\s*:?\s*"
)
_ALLOWED_EXPRESSION = re.compile(r"^[0-9a-zA-Z_\s()+\-*/%^.,]+$")


class _ExpressionRejected(ValueError):
    pass


def _checked_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _ExpressionRejected("A expressão não produziu um número.")
    number = float(value)
    if not math.isfinite(number) or abs(number) > 1e100:
        raise _ExpressionRejected("O resultado excede os limites numéricos permitidos.")
    return number


def _evaluate_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return _checked_number(node.value)
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _checked_number(_UNARY_OPERATORS[type(node.op)](_evaluate_node(node.operand)))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 12:
            raise _ExpressionRejected("Expoentes acima de 12 não são permitidos.")
        return _checked_number(_BINARY_OPERATORS[type(node.op)](left, right))
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _FUNCTIONS
        and not node.keywords
        and 1 <= len(node.args) <= 3
    ):
        arguments = [_evaluate_node(argument) for argument in node.args]
        return _checked_number(_FUNCTIONS[node.func.id](*arguments))
    raise _ExpressionRejected("A expressão contém operações não permitidas.")


def _extract_expression(text: str) -> str | None:
    candidate = _CALCULATION_PREFIX.sub("", text.strip()).strip()
    candidate = candidate.rstrip(" ?!;=")
    if not candidate or len(candidate) > 160 or not _ALLOWED_EXPRESSION.fullmatch(candidate):
        return None
    if re.fullmatch(r"\d+,\d+", candidate):
        candidate = candidate.replace(",", ".")
    candidate = candidate.replace("^", "**")
    if not re.search(r"[+\-*/%()]|\*\*", candidate):
        return None
    return candidate


class CalculatorTool:
    """Calculadora AST restrita a números, operadores e funções matemáticas permitidas."""

    name = "calculator"

    def execute(self, text: str) -> ToolResult | None:
        expression = _extract_expression(text)
        if expression is None:
            return None
        try:
            parsed = ast.parse(expression, mode="eval")
            if sum(1 for _ in ast.walk(parsed)) > 64:
                return None
            value = _evaluate_node(parsed)
            formatted = f"{value:.12g}"
            return ToolResult(
                name=self.name,
                matched=True,
                success=True,
                content=f"Resultado: {formatted}",
                value=value,
                metadata={"expression": expression},
            )
        except SyntaxError:
            # Texto composto ou expressão incompleta não é reivindicado pela calculadora.
            return None
        except (TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
            if isinstance(exc, _ExpressionRejected):
                return None
            message = "Não foi possível calcular a expressão com segurança."
            if isinstance(exc, ZeroDivisionError):
                message = "Não é possível dividir por zero."
            elif isinstance(exc, ValueError):
                message = "A expressão matemática está fora do domínio permitido."
            return ToolResult(
                name=self.name,
                matched=True,
                success=False,
                content=message,
                error=type(exc).__name__,
                metadata={"expression": expression},
            )


_UNIT_FACTORS: dict[str, tuple[str, float]] = {
    "mm": ("length", 0.001),
    "cm": ("length", 0.01),
    "m": ("length", 1.0),
    "km": ("length", 1000.0),
    "mg": ("mass", 0.001),
    "g": ("mass", 1.0),
    "kg": ("mass", 1000.0),
    "ms": ("time", 0.001),
    "s": ("time", 1.0),
    "seg": ("time", 1.0),
    "min": ("time", 60.0),
    "h": ("time", 3600.0),
    "b": ("data", 1.0),
    "kb": ("data", 1000.0),
    "mb": ("data", 1_000_000.0),
    "gb": ("data", 1_000_000_000.0),
}
_TEMPERATURE_UNITS = {
    "c": "celsius",
    "°c": "celsius",
    "celsius": "celsius",
    "f": "fahrenheit",
    "°f": "fahrenheit",
    "fahrenheit": "fahrenheit",
    "k": "kelvin",
    "kelvin": "kelvin",
}
_CONVERSION_PATTERN = re.compile(
    r"(?i)^(?:(?:converta|converter|transforme|transformar)\s+)?"
    r"([-+]?\d+(?:[.,]\d+)?)\s*([a-z°]+)\s+(?:para|em|to)\s+([a-z°]+)\s*[.!]?$"
)


def _temperature_to_kelvin(value: float, unit: str) -> float:
    if unit == "celsius":
        return value + 273.15
    if unit == "fahrenheit":
        return (value - 32.0) * 5.0 / 9.0 + 273.15
    return value


def _kelvin_to_temperature(value: float, unit: str) -> float:
    if unit == "celsius":
        return value - 273.15
    if unit == "fahrenheit":
        return (value - 273.15) * 9.0 / 5.0 + 32.0
    return value


class UnitConversionTool:
    """Conversões explícitas entre unidades comuns de comprimento, massa, tempo e dados."""

    name = "unit_converter"

    def execute(self, text: str) -> ToolResult | None:
        match = _CONVERSION_PATTERN.fullmatch(text.strip())
        if match is None:
            return None

        value = float(match.group(1).replace(",", "."))
        source = match.group(2).casefold()
        target = match.group(3).casefold()

        if source in _TEMPERATURE_UNITS and target in _TEMPERATURE_UNITS:
            kelvin = _temperature_to_kelvin(value, _TEMPERATURE_UNITS[source])
            if kelvin < 0:
                return ToolResult(
                    name=self.name,
                    matched=True,
                    success=False,
                    content="A temperatura não pode ficar abaixo do zero absoluto.",
                    error="below_absolute_zero",
                )
            converted = _kelvin_to_temperature(kelvin, _TEMPERATURE_UNITS[target])
            dimension = "temperature"
        else:
            source_data = _UNIT_FACTORS.get(source)
            target_data = _UNIT_FACTORS.get(target)
            if source_data is None or target_data is None:
                return None
            if source_data[0] != target_data[0]:
                return ToolResult(
                    name=self.name,
                    matched=True,
                    success=False,
                    content="As unidades informadas pertencem a grandezas diferentes.",
                    error="incompatible_units",
                )
            converted = value * source_data[1] / target_data[1]
            dimension = source_data[0]

        if not math.isfinite(converted):
            return ToolResult(
                name=self.name,
                matched=True,
                success=False,
                content="A conversão excede os limites numéricos.",
                error="numeric_overflow",
            )

        formatted = f"{converted:.12g}"
        return ToolResult(
            name=self.name,
            matched=True,
            success=True,
            content=f"{match.group(1)} {match.group(2)} = {formatted} {match.group(3)}",
            value=converted,
            metadata={"dimension": dimension, "from": source, "to": target},
        )


class DeterministicToolRegistry:
    """Registro ordenado de ferramentas locais."""

    def __init__(self, tools: list[DeterministicTool] | None = None) -> None:
        self._tools = list(tools or [UnitConversionTool(), CalculatorTool()])

    def execute(self, text: str) -> ToolResult | None:
        for tool in self._tools:
            result = tool.execute(text)
            if result is not None and result.matched:
                return result
        return None
