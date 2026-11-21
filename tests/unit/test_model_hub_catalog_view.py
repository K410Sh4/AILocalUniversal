from PySide6.QtWidgets import QApplication

from app.views.model_hub_view import ModelHubView
from model_hub.catalog import parse_catalog


def _catalog():
    return parse_catalog(
        {
            "schema_version": 1,
            "catalog_version": "test.1",
            "updated_at": "2026-11-20",
            "models": [
                {
                    "record_id": "ollama:qwen3.5:2b",
                    "display_name": "Qwen 3.5 2B",
                    "family": "Qwen 3.5",
                    "summary": "Compact chat and reasoning model.",
                    "publisher": "Alibaba Cloud",
                    "categories": ["general", "reasoning"],
                    "capabilities": ["chat", "reasoning"],
                    "modalities": ["text"],
                    "source_url": "https://ollama.com/library/qwen3.5",
                    "variants": [
                        {
                            "reference": "qwen3.5:2b-q4_K_M",
                            "size_label": "1.9 GB",
                            "quantization": "Q4_K_M",
                            "supported_platforms": ["linux", "macos", "windows"],
                        }
                    ],
                },
                {
                    "record_id": "ollama:phonon:40m-multilingual",
                    "display_name": "Phonon 40M Multilingual",
                    "family": "Phonon",
                    "summary": "Text to speech.",
                    "publisher": "Gradium",
                    "categories": ["audio", "speech"],
                    "capabilities": ["text_to_speech"],
                    "modalities": ["text", "audio"],
                    "source_url": "https://ollama.com/library/phonon",
                    "variants": [
                        {
                            "reference": "phonon:40m-multilingual",
                            "supported_platforms": ["macos"],
                        }
                    ],
                },
            ],
        },
        source="test",
    )


def test_catalog_ui_filters_by_category_and_disables_unsupported_platform() -> None:
    app = QApplication.instance() or QApplication([])
    view = ModelHubView()
    view.set_catalog_data(_catalog(), set())

    assert view.catalog_table.rowCount() == 2
    speech_index = view.category_filter.findData("speech")
    view.category_filter.setCurrentIndex(speech_index)
    assert view.catalog_table.rowCount() == 1
    assert view.catalog_table.item(0, 0).text() == "Phonon 40M Multilingual"
    assert not view.install_button.isEnabled()

    view.category_filter.setCurrentIndex(view.category_filter.findData("general"))
    assert view.catalog_table.rowCount() == 1
    assert view.catalog_table.item(0, 0).text() == "Qwen 3.5 2B"
    assert view.install_button.isEnabled()

    emitted: list[str] = []
    view.install_requested.connect(emitted.append)
    view.install_button.click()
    assert emitted == ["qwen3.5:2b-q4_K_M"]

    view.close()
    app.processEvents()
