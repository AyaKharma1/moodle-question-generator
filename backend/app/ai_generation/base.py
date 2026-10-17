"""AI provider interface.

Providers are interchangeable: the rest of the application only depends on
this abstract class, never on a concrete model or vendor SDK. A provider's job
is narrow and testable: given (untrusted) source text and a generation
request, return a list of *raw question dictionaries* (already parsed from the
model's JSON). Turning those dicts into validated domain objects and then into
Moodle XML happens in later, model-independent stages.
"""
from __future__ import annotations

import abc

from app.schemas.question import GenerationRequest


class AIProviderError(RuntimeError):
    """Raised when a provider fails in a way the API should surface safely."""


class AIProvider(abc.ABC):
    """Abstract base class every AI provider implements."""

    #: Short, stable identifier used in logs and the ExportHistory/provider field.
    name: str = "base"

    @abc.abstractmethod
    def generate(self, *, source_text: str, request: GenerationRequest) -> list[dict]:
        """Generate raw question dictionaries grounded in ``source_text``.

        Implementations MUST:
          * treat ``source_text`` as untrusted data, never as instructions;
          * return structured data (list of dicts), not XML and not prose;
          * never raise raw vendor exceptions to the caller - wrap them in
            :class:`AIProviderError`.
        """
        raise NotImplementedError
