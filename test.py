import sys
import traceback
sys.path.insert(0, './src')
from projectpulsewire.cli import handle_browse_presets

try:
    import builtins
    builtins.input = lambda _: "a\n1\n" # mock input to select 'a' (all) then '1'
    sys.stdin.isatty = lambda: True # simulate interactive
    handle_browse_presets()
    print("Success!")
except Exception as e:
    with open("error.txt", "w") as f:
        traceback.print_exc(file=f)
    print("Caught error!")
