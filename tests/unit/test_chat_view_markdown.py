from app.views.chat_view import build_transcript_html, markdown_to_html


def test_markdown_renderer_formats_bold_lists_and_inline_code() -> None:
    rendered = markdown_to_html(
        "**Root Mean Square**\n\n- corrente\n- tensão\n\nUse `valor`."
    )

    assert "Root Mean Square" in rendered
    assert "**Root Mean Square**" not in rendered
    assert "corrente" in rendered
    assert "tensão" in rendered
    assert "valor" in rendered


def test_markdown_renderer_discards_embedded_html() -> None:
    rendered = markdown_to_html("<script>alert('x')</script>")

    assert "<script>" not in rendered



def test_transcript_uses_spaced_chat_bubbles_and_no_underlined_text() -> None:
    rendered = build_transcript_html(
        [
            {"role": "user", "content": "Olá"},
            {"role": "assistant", "content": "**Resposta**\n\n- item"},
        ]
    )

    assert '<table width="86%" align="right"' in rendered
    assert '<table width="96%" align="left"' in rendered
    assert 'bgcolor="#203b53"' in rendered
    assert 'bgcolor="#252b33"' in rendered
    assert "*{text-decoration:none;}" in rendered
    assert "Resposta" in rendered
    assert "**Resposta**" not in rendered



def test_inline_latex_renders_integrals_fractions_and_powers() -> None:
    rendered = markdown_to_html(
        r"Integral: $\int_0^1 x dx = \frac{1}{2}$ and $x^2$."
    )

    assert "∫" in rendered
    assert "<sub>0</sub>" in rendered
    assert "<sup>1</sup>" in rendered
    assert 'class="math-frac"' in rendered
    assert "<sup>2</sup>" in rendered
    assert "$" not in rendered


def test_display_latex_and_parenthesis_delimiters_are_supported() -> None:
    rendered = markdown_to_html(
        r"$$E = mc^2$$ and \(x_1 + \pi\)."
    )

    assert 'class="math-display"' in rendered
    assert "<sup>2</sup>" in rendered
    assert "<sub>1</sub>" in rendered
    assert "π" in rendered


def test_math_delimiters_inside_code_are_preserved_as_code() -> None:
    rendered = markdown_to_html("Use " + chr(96) + "$x^2$" + chr(96) + " in code.")

    assert "$x^2$" in rendered
    assert "math-inline" not in rendered
