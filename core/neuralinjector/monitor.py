"""Opt-in background sampling for adaptive resource decisions."""

from __future__ import annotations

import threading
from collections.abc import Callable

from .resources import (
    AdaptiveResourceManager,
    DynamicResourceDecision,
    HardwareSnapshot,
    detect_hardware,
)


class ResourceMonitor:
    """Low-overhead sampler that reports policy decisions but does not apply them.

    The monitor is inert until start() is called. Its default provider reads host
    RAM/CPU only; callers may inject a provider that also probes GPU telemetry.
    When started, callbacks run on the monitor thread; poll_once() runs on the caller thread.
    UI callbacks from the background monitor must dispatch work to the UI thread.
    """

    def __init__(
        self,
        *,
        manager: AdaptiveResourceManager | None = None,
        snapshot_provider: Callable[[], HardwareSnapshot] = detect_hardware,
        on_decision: Callable[[DynamicResourceDecision], None] | None = None,
        interval_seconds: float = 5.0,
        active_parallelism: int = 1,
        active_context_tokens: int = 4096,
    ) -> None:
        if interval_seconds < 1.0:
            raise ValueError("interval_seconds must be at least 1 second")
        if active_parallelism < 1 or active_context_tokens < 1:
            raise ValueError("active resource values must be positive")

        self.manager = manager or AdaptiveResourceManager()
        self.snapshot_provider = snapshot_provider
        self.on_decision = on_decision
        self.interval_seconds = interval_seconds
        self.active_parallelism = active_parallelism
        self.active_context_tokens = active_context_tokens
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._last_snapshot: HardwareSnapshot | None = None
        self._last_decision: DynamicResourceDecision | None = None
        self._last_error: Exception | None = None

    @property
    def is_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    @property
    def last_snapshot(self) -> HardwareSnapshot | None:
        with self._lock:
            return self._last_snapshot

    @property
    def last_decision(self) -> DynamicResourceDecision | None:
        with self._lock:
            return self._last_decision

    @property
    def last_error(self) -> Exception | None:
        with self._lock:
            return self._last_error

    def poll_once(self) -> DynamicResourceDecision:
        """Perform one synchronous sample; useful for tests and event-driven hosts."""
        snapshot = self.snapshot_provider()
        decision = self.manager.evaluate(
            snapshot,
            active_parallelism=self.active_parallelism,
            active_context_tokens=self.active_context_tokens,
        )
        with self._lock:
            self._last_snapshot = snapshot
            self._last_decision = decision
            self._last_error = None
        if self.on_decision is not None:
            self.on_decision(decision)
        return decision

    def start(self) -> None:
        """Start periodic sampling. Repeated calls while running are harmless."""
        with self._lifecycle_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            thread = threading.Thread(
                target=self._run,
                name="AILocalResourceMonitor",
                daemon=True,
            )
            self._thread = thread
            thread.start()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.poll_once()
            except Exception as exc:  # Keep the monitor alive after transient probe failures.
                with self._lock:
                    self._last_error = exc
            self._stop_event.wait(self.interval_seconds)

    def stop(self, timeout_seconds: float = 2.0) -> bool:
        """Request shutdown and return whether the monitor thread has stopped."""
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds cannot be negative")
        with self._lifecycle_lock:
            self._stop_event.set()
            thread = self._thread
        if thread is None:
            return True
        if thread is threading.current_thread():
            return False
        thread.join(timeout_seconds)
        stopped = not thread.is_alive()
        if stopped:
            with self._lifecycle_lock:
                if self._thread is thread:
                    self._thread = None
        return stopped
