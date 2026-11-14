# Third-party integrations and distribution

This inventory describes **v0.1.0-preview.2** and its public source/runtime
boundary. The [dependency review](dependency-license-review.md) identifies the
exact compiled distribution. Physical Steam Deck compatibility remains untested.
Official sources were checked on 3 November 2026; a public download alone is
not permission to mirror or bundle a mod.

## Required game environment

Use updated SteamOS and system certificates for HTTPS downloads and optional
AI services; see the scoped [security review](security-review.md).
The player supplies legitimate Steam, Assetto Corsa and Proton. **CSP 0.3.1 is
the only required game mod.** AGA, extra cameras, Sidekick, Sol, Pure and Content
Manager are not installation prerequisites. The [one-command installer](installation.md)
includes the launcher runtime and downloads CSP separately; end users need no
SDK, compilation, Git checkout or manual mod copy for the default path.

| Component | Installation and distribution | Official origin and terms |
| --- | --- | --- |
| Assetto Corsa and DLC | Separately installed player content. ac-deck attaches to it and does not redistribute it. | [Steam App 244210](https://store.steampowered.com/app/244210/Assetto_Corsa/); proprietary game/Steam terms apply. |
| Steam and Proton | External environment, not bundled. Preserve the original Steam entry and selected Proton. First Play can initialize missing Proton folders through that chain without starting a race. | [Steam](https://store.steampowered.com/about/) and [Proton source](https://github.com/ValveSoftware/Proton); components retain their terms. |
| CSP 0.3.1 | Official HTTPS download during setup with verified archive/kit and owned game files. Matching files are reused; missing files installed; recognised managed upgrades use backup/recovery. Unknown or modified conflicts are preserved. Absent from release assets. | [Publisher](https://acstuff.club/patch/) and [pinned download](https://acstuff.club/patch/?get=0.3.1). ZIP: 147,534,836 bytes; SHA-256 `f7b157edeacaaa4ff89af3b416af0acf5216fcee40631425ce5c7cf263e3f5a1`; 754 extracted files checked. Publisher labels 0.3.1 untested and 0.2.11 recommended. No general redistribution grant asserted. |
| CSP Gamepad Force, base cameras/weather | Supplied by the separate CSP kit. Defaults are Gamepad Force and Original chase camera. Sol/Pure are unnecessary for base weather. | Terms of the exact CSP distribution; not separately bundled mod assets. |

## Optional integrations

| Component | Behavior and limit | Origin and distribution decision |
| --- | --- | --- |
| Advanced Gamepad Assist 1.5.5 | Detects an installed Gamepad FX script. Authored bridge settings target 1.5.5; it does not distribute or edit AGA. | [Author's v1.5.5 release](https://github.com/adam10603/AC-Advanced-Gamepad-Assist/releases/tag/v1.5.5), [MIT source/license](https://github.com/adam10603/AC-Advanced-Gamepad-Assist); applicable notice in [third-party notices](../THIRD_PARTY_NOTICES.md). |
| ACC DualSense Feedback 1.0.1 | Referenced haptics event/envelope design; the separate Windows ACC app is not required or embedded. | [Author's project](https://github.com/Adudumax/ACC-DualSense-Feedback), MIT; [original notice](../licenses/ACC-DualSense-Feedback.txt) retained. |
| GT5 Spec 2.0 camera | Optional exact user-acquired ZIP. Its adapter combines verified original Lua with ac-deck code during installation. Selection without that archive cannot install it. | [Author page](https://www.overtake.gg/downloads/spec-2-0-gran-turismo-5-gt5-chase-camera.68401/); provider account required. No public redistribution grant established; no bundled archive or automatic account-gated download. |
| BACC NFS Unbound 1.0 / GT 1.2 | Optional exact user-acquired ZIPs combined with adapters after verification. Not default cameras. | [Unbound](https://www.overtake.gg/downloads/bacc-unbound-better-arcade-chaser-camera-for-csp.57812/) and [GT](https://www.overtake.gg/downloads/bacc-gran-turismo-better-arcade-chaser-camera-for-csp.49548/). No redistribution grant established; excluded. Unbound page returned an access error during review. |
| Sidekick | Optional player app; no community installer/integration supplied here. | [Original page](https://www.overtake.gg/downloads/sidekick.11007/), [extended version](https://www.nutrimatic.cc/assetto-corsa/sidekick-v1-14/). Rights unverified; excluded. |
| Sol / Pure / Content Manager | Not bundled or needed by default. Optional installations retain their own requirements and terms. | No automatic download or distribution supplied. |
| GT7 HUD | Retired; recovery/cleanup code for an earlier managed installation remains. | No active installer/archive; rights not asserted. |

The authored CSP adjustable-camera, haptics, proximity and AGA bridge apps use
CSP interfaces and owned files; they are not copies of the optional mods above.
Camera adapters incorporate the user's verified original scripts, so a blanket
claim that no third-party script is ever copied would be inaccurate.

## Media and runtime dependencies

Preview 3 adds the authored Speed Chase script for CSP. Its physical behavior
with the public installer’s CSP 0.3.1 remains untested. The community runtime
omits the private victory tracks. The Rogue objectives and victory screen still
work with silent celebrations.

Private album pictures and Toasty image/audio are excluded. Missing album art
falls back without losing XP, stickers or Rogue state; missing Toasty media
disables that cosmetic effect without blocking the race. The three attributed
English quotations retain the [US/Brazil review](content-rights.md). Current
gallery PNGs are omitted; their [historical record](screenshots/README.md)
does not establish redistribution rights.

The compiled runtime intentionally includes Python, native libraries, Pillow,
a font and original notices. Their licenses, corresponding sources and
replacement rights are covered by the [dependency inventory](../licenses/dependency-sources.json),
[source companion](dependency-sources.md) and
[third-party notices](../THIRD_PARTY_NOTICES.md#binary-distribution-review).
Player-installed cars, tracks and other mods remain outside that inventory;
do not redistribute them without their own rights review.
