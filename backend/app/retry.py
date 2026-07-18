from __future__ import annotations

from dataclasses import dataclass
import logging
import random
import time
from typing import Callable, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    base_delay_seconds: float
    max_delay_seconds: float
    backoff_multiplier: float
    jitter_seconds: float = 0.0

    def delay_for_attempt(self, attempt_number: int, rng: Callable[[], float] | None = None) -> float:
        exponent = max(attempt_number - 1, 0)
        delay = self.base_delay_seconds * (self.backoff_multiplier**exponent)
        delay = min(delay, self.max_delay_seconds)
        if self.jitter_seconds <= 0:
            return delay
        random_source = rng or random.random
        jitter_offset = random_source() * self.jitter_seconds
        return delay + jitter_offset


def retry_sync(
    operation: Callable[P, T],
    *args: P.args,
    policy: RetryPolicy,
    logger: logging.Logger | None = None,
    operation_name: str | None = None,
    retry_if: Callable[[Exception], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    **kwargs: P.kwargs,
) -> T:
    operation_label = operation_name or getattr(operation, "__name__", "operation")
    last_error: Exception | None = None
    for attempt_number in range(1, policy.max_attempts + 1):
        try:
            return operation(*args, **kwargs)
        except Exception as caught_error:  # noqa: BLE001
            if retry_if is not None and not retry_if(caught_error):
                raise
            last_error = caught_error
            if attempt_number >= policy.max_attempts:
                break
            delay_seconds = policy.delay_for_attempt(attempt_number)
            if logger is not None:
                logger.warning(
                    "Retrying failed operation",
                    extra={
                        "operation_name": operation_label,
                        "attempt": attempt_number,
                        "delay_seconds": round(delay_seconds, 3),
                    },
                )
            sleep(delay_seconds)

    assert last_error is not None
    raise last_error

