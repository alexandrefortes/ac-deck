# Third party notices

The community source selection contains the launcher implementation and
integration code. It excludes the game, DLCs, Steam, CSP, mod archives and
private media. Project-owned code is available under [PolyForm Noncommercial
License 1.0.0](LICENSE), a source-available license with purpose restrictions.
Its permitted purposes include the personal and organizational uses expressly
listed in that license, and it does not limit fair-use rights. These terms do
not replace any third-party component's own license.

See the [integration inventory](docs/third-party-integrations.md) for sources,
download links, bundled components and unresolved redistribution rights.

The driving-haptics integration retains the attribution supplied in
[ACC DualSense Feedback](licenses/ACC-DualSense-Feedback.txt).

The optional Gamepad FX bridge follows the shared data layout of Advanced
Gamepad Assist 1.5.5 by Adam D. The mod itself is not included. Its license
notice follows:

```text
MIT License

Copyright (c) 2023 Adam D.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

The experimental community preview contains its selected runtime dependencies
and license notices under licenses/. Review the exact package inventory:

| Component | Notice location in the compiled package |
| --- | --- |
| Python and selected system libraries | licenses/sdk/ |
| SDL2 | licenses/sdk/ |
| DejaVu UI font | licenses/sdk/ |
| Pillow | licenses/Pillow-LICENSE |
| PyInstaller | licenses/PyInstaller.txt |
| Other selected ELF dependencies and referenced common license texts | licenses/sdk/ |

Keep original notice bytes. An optional component installed by a player keeps
its own license; its presence on that player's machine does not add it to the
community distribution.

## Binary distribution review

The [v0.1.0-preview.1 release](https://github.com/alexandrefortes/ac-deck/releases/tag/v0.1.0-preview.1)
provides the matching dependency-source companion, inventory and checksums.
This preview builds CPython 3.13.5 from its pinned upstream sources without
Berkeley DB or GDBM; those components of the older standalone interpreter
are not incorporated in this runtime. Original Python and static dependency
notices are retained under licenses/sdk/python-nodb/. The release source
includes the reproducible SDK recipe and the exact component/source inventory. LGPL recipients retain applicable rights to modify or replace those
libraries for their own use and reverse engineer the combined work for
debugging such modifications. The first-party license does not supersede the
third-party licenses. Review notices and corresponding sources for each build.
