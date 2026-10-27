# Third party notices

The community source selection contains the launcher implementation and
integration code. It excludes the game, DLCs, Steam, CSP, mod archives and
private media. The first-party code license is a separate owner decision.

The driving-haptics integration retains the attribution supplied in
[ACC DualSense Feedback](licenses/ACC-DualSense-Feedback.txt).

Compiled distributions also contain their selected runtime dependencies and
license notices under licenses/. Review the exact package inventory:

| Component | Notice location in the compiled package |
| --- | --- |
| Python and selected system libraries | licenses/sdk/ |
| SDL2 | licenses/sdk/ |
| DejaVu UI font | licenses/sdk/ |
| Pillow | licenses/Pillow-LICENSE |
| PyInstaller | licenses/PyInstaller.txt |

Keep original notice bytes. An optional component installed by a player keeps
its own license; its presence on that player's machine does not add it to the
community distribution.
