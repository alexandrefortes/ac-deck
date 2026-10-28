# Community release checklist

Source is available in this repository under [PolyForm Noncommercial 1.0.0](../LICENSE), alongside the community builder, synthetic tests and interface previews. A community candidate has passed local automated checks. A runtime package is not published: bundled-library LGPL compliance review remains pending. Physical Steam Deck validation remains separate. Track source publication and binary readiness separately.

- [ ] Define the canonical source repository, this repository's role and how documentation, source exports and release versions stay in sync.
- [ ] Review any source export and its history for private data and material outside the approved public scope.
- [x] Choose and record PolyForm Noncommercial 1.0.0 for project-owned code, retaining its stated personal and organizational permissions and fair-use provisions.
- [ ] Complete the [bundled-library licensing review](../THIRD_PARTY_NOTICES.md#binary-distribution-review), preserve required notices and meet the applicable LGPL requirements before binary distribution.
- [ ] Review public redistribution rights for every included mod, font, image, audio clip and other asset. Exclude or replace material without confirmed permission. Review screenshots separately.
- [ ] Produce a reviewed public package with matching source provenance, an explicit payload inventory and verified hashes. Keep game/DLC files, Steam data, credentials and player data outside the distribution.
- [ ] Document prerequisites and installation using a legitimate Steam/Assetto Corsa setup, with supported SteamOS/Proton versions and optional AI requirements.
- [ ] Document updates, data preservation and recovery; verify that existing game attachments, saves, settings and caches survive the supported update path.
- [ ] Verify packaged startup, resource lookup and relocation. Record actual Steam Deck testing separately from automated tests and demonstration screenshots.
- [ ] Check first-use instructions with a new user and publish known limitations without presenting performance or offline goals as verified results.
- [ ] Define contribution/build instructions for the source that is actually public, plus a clear GitHub issue workflow for reports and proposals.
- [ ] Complete an explicit review of the exact public source, package, documentation and screenshots before publication. This checklist alone does not publish a release or change repository visibility.
