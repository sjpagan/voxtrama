"""The languages a job's recap and extractions can be written in.

The job chooses the language its generative steps write in: the new-job
form offers these, starting from the browser's own language, and "Same as
the audio" keeps what every skill did before (the transcript's
own language). The code is what a run stores (RunChoices.output_language).
The English name is what a prompt says, since the prompts are in English.
"""

from __future__ import annotations

# code: (name in its own language, for the form; name in English, for the prompt)
OUTPUT_LANGUAGES: dict[str, tuple[str, str]] = {
    "it": ("Italiano", "Italian"),
    "en": ("English", "English"),
    "es": ("Español", "Spanish"),
    "fr": ("Français", "French"),
    "de": ("Deutsch", "German"),
    "pt": ("Português", "Portuguese"),
    "nl": ("Nederlands", "Dutch"),
}


def prompt_language(code: str) -> str:
    """What a prompt calls `code`: its English name, or the code itself if unknown."""
    return OUTPUT_LANGUAGES.get(code, (code, code))[1]
