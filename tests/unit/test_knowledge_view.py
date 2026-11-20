from app.views.knowledge_view import KnowledgeView


def test_knowledge_view_formats_document_sizes() -> None:
    assert KnowledgeView._format_size(0) == "0.0 B"
    assert KnowledgeView._format_size(1024) == "1.0 KB"
    assert KnowledgeView._format_size(1024 * 1024) == "1.0 MB"
