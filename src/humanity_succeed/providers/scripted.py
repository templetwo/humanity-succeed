"""Scripted provider: replays fixed raw strings. It is an instrument, never a model.

It receives only the serialized provider input (bytes). It records every input it was given so
leakage tests can inspect the exact model-visible bytes.
"""

from __future__ import annotations


class ScriptExhausted(Exception):
    pass


class ScriptedProvider:
    kind = "scripted"

    def __init__(self, raw_outputs: list[str]) -> None:
        self._outputs = list(raw_outputs)
        self._i = 0
        self.received_inputs: list[bytes] = []

    def generate(self, provider_input: bytes) -> str:
        if not isinstance(provider_input, (bytes, bytearray)):
            raise TypeError("providers receive serialized bytes only")
        self.received_inputs.append(bytes(provider_input))
        if self._i >= len(self._outputs):
            raise ScriptExhausted(f"script has {len(self._outputs)} outputs")
        out = self._outputs[self._i]
        self._i += 1
        return out
