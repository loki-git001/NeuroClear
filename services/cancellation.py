import threading

class CancellationToken:
    """
    A thread-safe cancellation token used to propagate cancellation signals
    deep into synchronous ML pipelines from an async disconnect monitor.
    """
    def __init__(self):
        self._event = threading.Event()

    def cancel(self) -> None:
        """Mark the token as cancelled."""
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        """Check if a cancellation has been requested."""
        return self._event.is_set()
