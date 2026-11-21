from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.main_window import MainWindow


class FakeWorker:
    def __init__(self, wait_result: bool) -> None:
        self.wait_result = wait_result
        self.cancel_called = False
        self.timeout = None

    def isRunning(self) -> bool:
        return True

    def cancel(self) -> None:
        self.cancel_called = True

    def wait(self, timeout: int) -> bool:
        self.timeout = timeout
        return self.wait_result


class FakeCloseEvent:
    def __init__(self) -> None:
        self.accepted = False
        self.ignored = False

    def accept(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True


@pytest.mark.parametrize(
    ("worker_attribute", "timeout"),
    [("_chat_worker", 5000), ("_status_worker", 2000), ("_neuralmap_worker", 5000)],
)
def test_close_event_refuses_to_close_while_worker_is_still_running(
    monkeypatch,
    worker_attribute: str,
    timeout: int,
) -> None:
    monkeypatch.setattr(
        "app.main_window.QMessageBox",
        SimpleNamespace(information=lambda *_args: None),
    )
    worker = FakeWorker(wait_result=False)
    window = SimpleNamespace(
        _knowledge_worker=None,
        knowledge_view=SimpleNamespace(is_busy=False),
        _pull_worker=None,
        _delete_worker=None,
        _catalog_worker=None,
        _chat_worker=None,
        _neuralmap_worker=None,
        _status_worker=None,
        _kia_runtime_client=None,
        _kia_memory_store=None,
    )
    setattr(window, worker_attribute, worker)
    event = FakeCloseEvent()

    MainWindow.closeEvent(window, event)

    assert worker.cancel_called is True
    assert worker.timeout == timeout
    assert event.ignored is True
    assert event.accepted is False


def test_close_event_accepts_after_chat_worker_stops(monkeypatch) -> None:
    worker = FakeWorker(wait_result=True)
    window = SimpleNamespace(
        _knowledge_worker=None,
        knowledge_view=SimpleNamespace(is_busy=False),
        _pull_worker=None,
        _delete_worker=None,
        _catalog_worker=None,
        _chat_worker=worker,
        _neuralmap_worker=None,
        _status_worker=None,
        _kia_runtime_client=None,
        _kia_memory_store=None,
    )
    event = FakeCloseEvent()

    MainWindow.closeEvent(window, event)

    assert worker.cancel_called is True
    assert event.accepted is True
    assert event.ignored is False
