"""Public surface of the CLI command implementations.

The exported names deliberately differ from the module names: an
__init__ that re-exports a name equal to one of its submodules hides
that submodule, and `import voxtrama.cli.commands.run` would then
resolve to a function.
"""

from voxtrama.cli.commands.calibrate import calibrate_command
from voxtrama.cli.commands.compare import compare_command
from voxtrama.cli.commands.correct import correct_command
from voxtrama.cli.commands.demo import demo_command
from voxtrama.cli.commands.doctor import doctor_command
from voxtrama.cli.commands.retention import retention_command
from voxtrama.cli.commands.run import run_command
from voxtrama.cli.commands.version import version_command

__all__ = [
    "calibrate_command",
    "compare_command",
    "correct_command",
    "demo_command",
    "doctor_command",
    "retention_command",
    "run_command",
    "version_command",
]
