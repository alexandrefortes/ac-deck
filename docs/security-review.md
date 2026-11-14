# Community preview security review

## Preview 3 advisory recheck

The 14 November 2026 query of GitHub-reviewed pip advisories found zero
matches for the same six exact pins listed below. The historical controls
matched 56 Pillow 12.2.0 advisories and one setuptools 84.0.0 advisory.
The release asset `security-review-six-pins.json` records aliases,
pagination, advisory IDs and the requirements hash.

SteamOS 3.9.5 Stable revoked the compromised eMudhra CAs. Update SteamOS and
its system certificates before downloading the installer. Use the official
Stable channel and its default trust store. The wrapper checks the version
on detected SteamOS. Custom trust stores need equivalent distrust.
The packaged CPython 3.13.5 lacks the built-in defense added by 3.13.18.
The installer's archive reader verifies the fixed checksum, then accepts
regular files through its own extraction code.

The package retains OpenSSL 3.0.16. Current upstream high severity
advisories for that version require DTLS, CMS or PKCS#7 operations, which the
reviewed product paths do not use. This review covers the stated paths and
versions. Physical trust stores and actual Deck operation remain untested.

Sources: [Valve SteamOS 3.9.5 announcement](https://steamcommunity.com/games/1675200/announcements/detail/694275728822244964),
[CPython 3.13.18 security release](https://www.python.org/downloads/release/python-31318/),
[OpenSSL 3.0 advisories](https://openssl-library.org/news/vulnerabilities-3.0/).

## Preview 2 historical review

Preview 1 was withdrawn on 3 November 2026 after confirmed dependency
advisories. Its tag and original artifacts are preserved; they are not the
current installation recommendation. The [historical license review](../archive/dependency-license-review-v0.1.0-preview.1.md)
records its original identities. Preview 2 replaces Pillow 12.2.0 with 13.0.0
and setuptools 84.0.0 with 84.1.0 in a separate reviewed SDK and candidate.

## Decision and affected path

The repository Dependabot API snapshot at 16:17:36 UTC on 3 November 2026
contained 55 open alerts: 54 for Pillow and one for setuptools. The API
classified five critical, 33 high, 16 medium and one low. These were relevant
current pins, not grounds to dismiss the graph as historical noise.

`src/launcher/previews.py` opens PNG/JPEG preview bytes and calls
`Image.thumbnail()`. The upstream [GHSA-8g5g-8vmr-9782](https://github.com/python-pillow/Pillow/security/advisories/GHSA-8g5g-8vmr-9782)
identifies a JPEG decoder overflow reached through that thumbnail path,
affected through 12.3.0 and patched in 13.0.0. This makes an actual launcher
image path relevant; restricting the format to JPEG does not exclude it.
The repository API snapshot labeled this alert **critical**; the publisher's
advisory page labels it **high**. Preserve those distinct source labels.
The [Pillow 13 release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html)
identify the other security corrections. No vulnerability reproducer was run.

The setuptools [GHSA-xmj3-9gf7-h52w](https://github.com/pypa/setuptools/security/advisories/GHSA-xmj3-9gf7-h52w)
is a low-severity Windows legacy wheel-installation path issue, fixed in
84.1.0. It is a build-environment dependency change; this does not assert that
the Linux launcher exercised that Windows path. The version is updated with
the rest of the pinned build inputs.

## Exact Python package check

At **2026-11-03 16:35:22 UTC**, all pages of GitHub's global **reviewed** pip
advisories were queried with `affects=package@version`, including the recorded
Pillow/PyInstaller capitalization aliases. The exact six pins returned **zero
matching reviewed advisories** in that snapshot:

| Package | Selected version |
| --- | --- |
| altgraph | 0.17.5 |
| packaging | 26.3 |
| PyInstaller | 6.22.3 |
| pyinstaller-hooks-contrib | 2026.9 |
| setuptools | 84.1.0 |
| Pillow | 13.0.0 |

Positive controls with Pillow 12.2.0 returned 54 unique advisories across its
two aliases; setuptools 84.0.0 returned one. The new versions are outside the
55 recorded vulnerable ranges. This check supports the exact pins in
[requirements](../scripts/launcher-linux-requirements.txt), whose raw SHA-256 is
`2201c8e3b8798b21286873a3c9f1b71b3e94b76a302af857392e1361dc9b6e25`.
The [sanitized audit receipt](security-review-six-pins.json) has SHA-256 `9e9bb7e53342a03c8f51a7b29924eda3b538244b4d8961bfa306923a08565cf2`.
The [GitHub endpoint documentation](https://docs.github.com/en/rest/security-advisories/global-advisories#list-global-security-advisories)
defines the filters and pagination. A zero result applies to that database,
query and time; it is not a guarantee against all vulnerabilities.

Repository alerts may remain open until the updated default branch is scanned.
The query above is independent evidence about selected versions; it does not
claim that GitHub has already closed every repository alert. Preserved older
manifests and tags remain historical evidence and must not be rewritten to
hide the earlier pins.

## Distribution checks and limits

A new version number alone does not establish the shipped bytes. Before
publication, match the candidate's actual Pillow extensions/vendor libraries
to the pinned official 13.0.0 wheel, include its complete original composite
notice and match the final dependency sources. Recheck the frozen SDK pins,
source/compiled results, ELF map and shared-library replacement proof. Keep
setuptools vendor terms separate from its root MIT license; see the
[dependency review](dependency-license-review.md) and
[source instructions](dependency-sources.md).

Run `git diff --check` and review current relevant advisories before promotion,
then verify anonymous access to the exact published material. The
[release checklist](community-release-checklist.md) records these publication
checks separately from physical acceptance. Do not replace preview 1's bytes
or reuse its tag for this candidate.

Keep SteamOS and its system certificate truststore updated. CPython 3.13.5
uses that truststore and lacks the later defense for
[CVE-2026-115557](https://www.python.org/downloads/release/python-31318/).
That conditional exposure depends on the OS still trusting compromised CA
keys; the target truststore was not inspected. This is not a claim that every
native dependency is free of vulnerabilities.

This review covers the identified 55 alerts and the six exact Python pins in
the queried database. It is not a complete review of CPython, all native
libraries, Steam/Proton, mods, operating systems or future advisories.
Source hashes prove selected bytes, not an absence of defects. No physical
Steam Deck race, performance or player acceptance is established here.
