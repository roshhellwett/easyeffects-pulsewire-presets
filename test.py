import sys
import traceback
from pathlib import Path
from itertools import chain, repeat
from unittest.mock import patch

sys.path.insert(0, './src')
from projectpulsewire.cli import handle_browse_presets

try:
    error_log = Path("error.txt")
    if error_log.exists():
        error_log.unlink()
    responses = chain(["a", "1", "", "b"], repeat("b"))
    with patch("builtins.input", side_effect=lambda *args, **kwargs: next(responses)):
        sys.stdin.isatty = lambda: True # simulate interactive
        handle_browse_presets()
    print("Success!")
except Exception as e:
    with open("error.txt", "w") as f:
        traceback.print_exc(file=f)
    print("Caught error!")
