# Community release checklist

This public branch contains documentation and interface previews. A reviewed source export, tests and compiled community candidate are prepared locally; their public release awaits the first-party license decision. Complete the following before presenting a package as a supported public release.

- [ ] Define the canonical source repository, this repository's role and how documentation, source exports and release versions stay in sync.
- [ ] Review any source export and its history for private data and material outside the approved public scope.
- [ ] Choose and record the license for project-owned code; retain required third-party notices.
- [ ] Review public redistribution rights for every included mod, font, image, audio clip and other asset. Exclude or replace material without confirmed permission. Review screenshots separately.
- [ ] Produce a reviewed public package with matching source provenance, an explicit payload inventory and verified hashes. Keep game/DLC files, Steam data, credentials and player data outside the distribution.
- [ ] Document prerequisites and installation using a legitimate Steam/Assetto Corsa setup, with supported SteamOS/Proton versions and optional AI requirements.
- [ ] Document updates, data preservation and recovery; verify that existing game attachments, saves, settings and caches survive the supported update path.
- [ ] Verify packaged startup, resource lookup and relocation. Record actual Steam Deck testing separately from automated tests and demonstration screenshots.
- [ ] Check first-use instructions with a new user and publish known limitations without presenting performance or offline goals as verified results.
- [ ] Define contribution/build instructions for the source that is actually public, plus a clear GitHub issue workflow for reports and proposals.
- [ ] Complete an explicit review of the exact public source, package, documentation and screenshots before publication. This checklist alone does not publish a release or change repository visibility.
