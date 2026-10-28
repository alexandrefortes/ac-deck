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

Local compiled candidates contain their selected runtime dependencies and
license notices under licenses/. A runtime package has not been published.
Review the exact package inventory:

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

Public binary distribution remains pending review of the bundled libraries'
applicable LGPL obligations and their interaction with the first-party terms.
The review must cover the exact libraries and versions, required notices,
corresponding source or source-offer requirements where applicable, and users'
applicable rights to replace or relink those libraries and debug modifications.
Including license notice files alone does not establish full compliance.

Keep third-party rights intact and review the combined package before upload.
Source availability under PolyForm is not a statement that the compiled
candidate is cleared for distribution. Physical Steam Deck validation is also
pending, as recorded in the [community release checklist](docs/community-release-checklist.md).
