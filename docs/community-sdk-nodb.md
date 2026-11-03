# Building a separate SDK without Berkeley DB

This setup prepares a persistent Linux x86_64 SDK from the exact sources in
the dependency inventory. It uses CPython 3.13.5 and the existing hash-pinned
PyInstaller 6.22.3, hooks 2026.9 and Pillow 12.2.0 wheels. It does not run as a
candidate stage. Keep the existing SDK and its inventory unchanged.

The host needs GCC, binutils, GNU make, Perl, Bash, tar and POSIX utilities.
Install or review those tools separately. The script does not install global
packages. Use a Linux filesystem for the new SDK and work directory.

First collect the pinned sources and notices using [the source collector](dependency-sources.md).
Keep that collection outside the new SDK. Download the pinned wheels with a
Linux CPython 3.13 interpreter, then run the versioned setup recipe:

```sh
python3.13 -B -m pip download --no-cache-dir --only-binary=:all: \
  --require-hashes -r scripts/launcher-linux-requirements.txt --dest /path/to/wheels
bash scripts/preparar_sdk_linux_sem_bdb.sh \
  /path/to/source-collection /path/to/new-sdk /path/to/new-work /path/to/wheels
```

Both new paths must be absent, distinct, and contain no spaces. The recipe
checks all seven source archives by SHA-256 before executing their contents.
It preserves logs and work on failure. Inspect the last completed operation
before recovery; an integral retry requires other new paths.

The recipe builds OpenSSL 3.0.16, zlib 1.3.1, bzip2 1.0.8, liblzma 5.2.12,
libffi 3.4.6 and SQLite 3.47.1 as static PIC archives in the new SDK, then
links them into the corresponding Python extension modules. CPython's
bundled Expat, libmpdec, HACL, mimalloc and BLAKE2 code comes from that exact
CPython source archive. It does not reuse the previous standalone libpython
or its incorporated components. No C source patches are applied.

`Modules/Setup.local` explicitly disables `_dbm` and `_gdbm`. Readline,
Tcl/Tk, curses and `_uuid` are also disabled. Python's `dbm.sqlite3` and
`dbm.dumb` remain available; those modules do not incorporate Berkeley DB.
SSL, compression, ctypes and SQLite are required. The setup does not require
PGO or JIT. Its absolute SDK library path is for a persistent build toolchain;
the packaged launcher needs its separate relocation checks.

Retain `NEW_WORK/setup.log`, `recipe.sh`, `requirements.lock`, generated
Makefiles, `config.log`, `pyconfig.h` and `Modules/Setup.local`, together with
the exact source archives. Record compiler and linker versions from the log.
The script and these receipts identify a build procedure; byte-identical
results across different hosts have not been established.

Before inventorying the SDK, run its focused standard-library tests:

```sh
/path/to/new-sdk/bin/python3.13 -B -m test \
  test_ssl test_hashlib test_zlib test_bz2 test_lzma test_ctypes \
  test_sqlite3 test_multiprocessing_spawn test_tarfile test_zipfile test_gzip test_dbm
```

Record skips and failures. Also verify a real HTTPS handshake with certificate
validation, compression round trips, SQLite operations, ctypes loading of the
selected SDL library, multiprocessing spawn and Pillow PNG/JPEG/WebP decoding.
SDL's explicit native input directory may be needed in `LD_LIBRARY_PATH` for
this direct SDK check. This does not open a launcher window or a game.

Inspect all new ELF files with readelf and nm, including libpython and every
extension. Check their required libraries, GLIBC ceiling and DB/GDBM symbols
against the actual build/link records. Preserve the source notices, including
the licenses in CPython's documentation and applicable vendor file headers.
The source inventory must distinguish this build from historical standalone
Python binaries and must identify the newly packaged bytes.

Create a new reviewed SDK inventory with the explicit `sdk-inventory` setup
command in [community delivery](community-delivery.md). Only then select the
new interpreter, root, inventory and matching notices in local configuration,
and prepare a new candidate through that workflow. Do not overwrite an older
candidate or use its inventory to classify the new runtime.

Removing Berkeley DB addresses that incorporated component. It does not
approve other dependency terms, content rights, source access, public release
or physical Steam Deck performance. Verify the resulting package and provide
its matching source material and notices before release.
