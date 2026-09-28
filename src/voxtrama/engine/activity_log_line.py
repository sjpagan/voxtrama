"""One readable run.log sentence for an activity_reporter tick.

Split out of engine.progress_file to keep that module under the project's
file-length limit. The fact (a step's position and total) is still read
there. Only the wording of the sentence built from it lives here.
"""

from __future__ import annotations

from voxtrama.humanize import human_bytes, human_clock


def activity_log_line(message: str, unit: str, done: float, total_amount: float | None) -> str:
    """`message` (progress.json's, lower-case) as a capitalised run.log line.

    `total_amount` is None only for a step whose engine.progress_file.
    activity_reporter caller never gave a total (no known caller does
    today). The result is the bare sentence with nothing to measure against.
    """
    sentence = message[0].upper() + message[1:]
    if total_amount is None:
        return sentence
    if unit == "windows":  # Parts of the transcript the model has read
        return f"{sentence}: {int(done)} of {int(total_amount)} parts read"
    position = human_bytes(done) if unit == "bytes" else human_clock(done)
    total_text = human_bytes(total_amount) if unit == "bytes" else human_clock(total_amount)
    return f"{sentence}: {position} of {total_text}"
