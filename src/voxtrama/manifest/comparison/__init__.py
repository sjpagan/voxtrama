"""Comparing two run manifests, and the two words that split every difference in three.

A difference between two manifests is either **expected** (the catalog in
difference.py names the fields two runs may legitimately disagree on, plus
whatever determinism.py's gate opens for a given pair) or it **counts**: it
is reported, and earns the command a non-zero exit. Nothing here decides
that a manifest is *wrong*. It only says whether the two disagree in a way
that matters.

walk.py builds the raw list of disagreements. difference.py and
determinism.py each judge part of it. classify.py sorts every raw
Difference into the three buckets that judgment leaves. report.py
turns the three into the text `voxtrama compare` prints, and the
exit code that goes with it.
"""

from __future__ import annotations
