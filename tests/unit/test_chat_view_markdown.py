from app.views.chat_view import markdown_to_html


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
