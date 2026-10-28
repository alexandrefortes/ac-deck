# Community candidate validation

The local candidate community-preview-002 was built from source revision
27a9bf1cb05904490f36481ee491d9b6ef88ccae. Its reviewed source export is recorded
in [the public source manifest](../public-source-manifest.json).
That manifest identifies the private source origin as
498812dca4d3e21f4c2624b099278402ba3ed854; 27a9bf1 is the independent exported
repository revision used to compile the candidate. The recorded source hashes
match both trees.
Source is available in this repository under [PolyForm Noncommercial
1.0.0](../LICENSE). This report records the original local candidate. An [experimental assembled
preview](https://github.com/alexandrefortes/ac-deck/tree/community-preview-001)
is now public, with first-party license and notice, third-party notices and
corresponding dependency sources. Physical Steam Deck validation remains
separate. The archive hash below identifies the original local candidate; the
published preview has its own checksum in the preview branch.

| Check | Result |
| --- | --- |
| Public source tests | 62 passed, no failures or skips |
| Compiled runtime tests | 62 passed, no runtime source fallback |
| Informational CLI | Help passed from an unrelated directory, cold and warm |
| Relocation | Passed with spaces in the folder name |
| Installed-game attachment | Passed using authored temporary fixtures; no game was started or copied |
| UI composition | Five screens rendered at 1280 × 800 and 1920 × 1200 |
| Distribution inventory | 166 files; no bundled CSP, mods, private media, game or player data |
| Runtime compatibility | Linux x86_64, highest required GLIBC symbol 2.39 |
| SDK notices | 50 exact notice files, with selected-library copyright and referenced license texts |

SDK: Python 3.13.5, PyInstaller 6.22.3, hooks 2026.9 and Pillow 12.2.0.
The archive SHA-256 is
8db2adab138b28fee5013d78a09b4f5662706870998bc8b37bd1cfe8e2cfd7a3.

Completing notices did not change the executable or shared libraries. Standard
library ZIP entries also remained identical; only ZIP container metadata changed.
The final inventory, source hashes, notices and CLI were verified again.

No Steam, launcher window, race, physical microphone or paid API was opened.
These checks do not establish physical Steam Deck behavior, minimum FPS,
offline operation or complete game-data portability. The first-party license
choice is resolved; the dependencies retain their own terms. The experimental
package and corresponding dependency sources are published; hardware validation
remains separate in the [release checklist](community-release-checklist.md).
