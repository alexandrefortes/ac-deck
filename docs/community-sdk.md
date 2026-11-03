# Community build SDK

Players install the compiled [preview](installation.md); they need no build
SDK. Contributors preparing a binary use an explicit persistent Linux x86_64
SDK with CPython 3.13.5, PyInstaller 6.22.3,
pyinstaller-hooks-contrib 2026.9, Pillow 13.0.0 and setuptools 84.1.0.
The six exact package pins are in the [requirements](../scripts/launcher-linux-requirements.txt);
see the [security review](security-review.md) for the replacement of preview 1.

The current route builds pinned upstream CPython without Berkeley DB/GDBM.
Follow [separate SDK setup](community-sdk-nodb.md) and
[dependency sources](dependency-sources.md) for its recipe and notices. Do not
use the older standalone interpreter's inventory to classify a new candidate,
or overwrite that historical SDK to make a gate pass.

Set your local path and inspect an existing SDK:

```sh
SDK_PREFIX=/path/to/persistent-sdk
"$SDK_PREFIX/bin/python3.13" -B -c 'import sys,importlib.metadata as m,importlib.util as u; print(sys.version); print({n:m.version(n) for n in ("pyinstaller","pyinstaller-hooks-contrib","Pillow","setuptools")}); assert u.find_spec("_dbm") is None and u.find_spec("_gdbm") is None'
```

Keep it outside disposable output on a Linux filesystem preserving POSIX
modes. Reuse reviewed versions and bytes; candidate builds do not reinstall
packages or fetch an SDK. Review setup separately if unavailable or changed.

Before inventorying, verify interpreter, SSL/compression/SQLite, ctypes,
multiprocessing, Pillow, original notices and ELF/link inputs. The new SDK's
105 ELF files required at most GLIBC 2.38, with no checked DB/GDBM dependencies
or dynamic symbols. That is SDK evidence; the complete runtime still needs its
own ELF inventory, source mapping and check against the product's 2.39 ceiling.

A candidate additionally needs explicit native libraries, licensed DejaVu font
and the selected 103-notice collection. Keep original bytes. Community policy
files come from the public checkout; a canonical build can select it using
`--community-notices /path/to/ac-deck`. SDK notices use `--licenses-dir`;
these arguments do not change their legal scope.

Configure only ignored `local/ciclo-entrega.json` with actual SDK root,
reviewed inventory, native/font/notices paths and a separate persistent Linux
work directory. Use the [community cycle](community-delivery.md#candidate-preparation).
Preflight compares SDK bytes with the inventory and pins the environment
before freezing sources. Changed inputs need a new reviewed inventory and
candidate; never edit an old successful receipt to accept them.

Automated checks use synthetic fixtures/processes and offscreen composition.
They do not start Steam, races, microphone or paid APIs. Record input checks,
source tests, compilation, packaging and compiled verification separately.
Their success does not establish physical Steam Deck support.
