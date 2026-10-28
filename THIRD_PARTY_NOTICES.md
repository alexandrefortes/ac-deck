# Third party notices

The community source selection contains the launcher implementation and
integration code. It excludes the game, DLCs, Steam, CSP, mod archives and
private media. Project-owned code is available under [PolyForm Noncommercial
License 1.0.0](LICENSE), a source-available license with purpose restrictions.
Its permitted purposes include the personal and organizational uses expressly
listed in that license, and it does not limit fair-use rights. These terms do
not replace any third-party component's own license.

The driving-haptics integration retains the attribution supplied in
[ACC DualSense Feedback](licenses/ACC-DualSense-Feedback.txt).

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

The [community preview](https://github.com/alexandrefortes/ac-deck/tree/community-preview-001)
includes a separate archive of corresponding LGPL dependency sources and their
inventory. LGPL recipients retain applicable rights to modify or replace those
libraries for their own use and reverse engineer the combined work for
debugging such modifications. The first-party license does not supersede the
third-party licenses. Review notices and corresponding sources for each build.
