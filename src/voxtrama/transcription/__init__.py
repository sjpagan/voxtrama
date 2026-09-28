"""Public surface of the transcription package: a Recording in, a Transcript out."""

from voxtrama.transcription.asr import transcribe, weights_for

__all__ = ["transcribe", "weights_for"]
