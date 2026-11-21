from core.deterministic_tools import CalculatorTool, UnitConversionTool


def test_calculator_handles_expression_and_power() -> None:
    result = CalculatorTool().execute("Quanto é 12 * (3 + 2)?")

    assert result is not None
    assert result.success is True
    assert result.value == 60.0
    assert result.content == "Resultado: 60"


def test_calculator_handles_division_by_zero_without_exception() -> None:
    result = CalculatorTool().execute("calcule 1 / 0")

    assert result is not None
    assert result.matched is True
    assert result.success is False
    assert "zero" in result.content


def test_calculator_rejects_code_execution_syntax() -> None:
    result = CalculatorTool().execute("__import__('os').system('id')")

    assert result is None


def test_unit_converter_handles_distance() -> None:
    result = UnitConversionTool().execute("Converta 5 km para m")

    assert result is not None
    assert result.success is True
    assert result.value == 5000.0
    assert result.content == "5 km = 5000 m"


def test_unit_converter_handles_temperature() -> None:
    result = UnitConversionTool().execute("0 °C em °F")

    assert result is not None
    assert result.success is True
    assert result.value == 32.0



def test_calculator_handles_subtraction() -> None:
    result = CalculatorTool().execute("2 - 2")

    assert result is not None
    assert result.success is True
    assert result.value == 0.0


def test_unit_converter_rejects_below_absolute_zero() -> None:
    result = UnitConversionTool().execute("-300 °C em K")

    assert result is not None
    assert result.success is False
    assert result.error == "below_absolute_zero"



def test_calculator_does_not_claim_compound_natural_language() -> None:
    result = CalculatorTool().execute("Calcule 2 + 2 e depois explique o resultado.")

    assert result is None


def test_registry_exposes_registered_tool_names() -> None:
    from core.deterministic_tools import DeterministicToolRegistry

    names = DeterministicToolRegistry().tool_names()
    assert set(names) == {"calculator", "unit_converter"}
