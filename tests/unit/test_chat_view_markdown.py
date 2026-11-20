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


def test_inline_latex_and_parenthesis_delimiters_are_supported() -> None:
    rendered = markdown_to_html(
        r"$E = mc^2$ and \(x_1 + \pi\)."
    )

    assert 'class="math-inline"' in rendered
    assert "<sup>2</sup>" in rendered
    assert "<sub>1</sub>" in rendered
    assert "π" in rendered


def test_math_delimiters_inside_code_are_preserved_as_code() -> None:
    rendered = markdown_to_html("Use " + chr(96) + "$x^2$" + chr(96) + " in code.")

    assert "$x^2$" in rendered
    assert "math-inline" not in rendered



def test_latex_supports_physics_symbols_vectors_and_overbars() -> None:
    rendered = markdown_to_html(
        r"Fluxo: $\Phi_E = \oint_S \vec{E}\cdot d\vec{A}$; "
        r"massa: $\bar{x} = \frac{1}{M}\int x\,dm$; densidade $\rho(x)$."
    )

    assert "Φ" in rendered
    assert "∮" in rendered
    assert "⃗" in rendered
    assert 'class="math-overbar"' in rendered
    assert "ρ(x)" in rendered
    assert "·" in rendered


def test_display_equation_is_centered_and_highlighted_as_own_block() -> None:
    rendered = markdown_to_html(
        "Equação importante:\n\n"
        r"\[ \Phi_E = \oint_S \vec{E}\cdot d\vec{A} \]"
        "\n\nTexto depois."
    )

    assert 'td align="center" bgcolor="#2b323b"' in rendered
    assert 'class="math-display"' in rendered
    assert 'padding:20px 16px' in rendered
    assert 'border:1px solid #46515e' in rendered
    assert "Φ" in rendered
    assert "font-size:20pt" in rendered
    assert "font-weight:600" in rendered
    assert 'height="14"' in rendered
    assert "color:#e8edf4" in rendered
    assert "line-height:1.35" in rendered
    assert "∮" in rendered
    assert "Texto depois." in rendered


def test_display_dollar_delimiter_uses_highlighted_block() -> None:
    rendered = markdown_to_html(r"$$E = mc^2$$")

    assert 'td align="center" bgcolor="#2b323b"' in rendered
    assert "E = mc" in rendered
    assert "<sup>2</sup>" in rendered


def test_limited_recovery_for_common_malformed_commands() -> None:
    rendered = markdown_to_html(r"$\limn \barx + \vecE$")

    assert "lim" in rendered
    assert "<sub>n</sub>" in rendered
    assert 'class="math-overbar">x</span>' in rendered
    assert "E⃗" in rendered


def test_unknown_latex_command_remains_visible_instead_of_being_guessed() -> None:
    rendered = markdown_to_html(r"$\unknownmacro{x}$")

    assert r"\unknownmacro" in rendered



def test_transcript_styles_additional_paragraph_and_list_spacing() -> None:
    rendered = build_transcript_html(
        [{"role": "assistant", "content": "Parágrafo um.\\n\\nParágrafo dois.\\n\\n- item"}]
    )

    assert "p{margin-top:5px;margin-bottom:11px;}" in rendered
    assert "ul,ol{margin-top:6px;margin-bottom:11px;}" in rendered
    assert "li{margin-bottom:6px;}" in rendered

