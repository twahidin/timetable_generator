"""The sums behind Will it fit? live in ttgen/checks.py, so that the skill's own check runs the same ones.
This name stays for the app and the tests: `import checks` gives that module itself."""
import sys
from ttgen import checks as _checks
sys.modules[__name__] = _checks
