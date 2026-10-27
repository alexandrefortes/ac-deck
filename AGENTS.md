# Project guidance

ac-deck is one Python/SDL2 application around the original Assetto Corsa on
Steam Deck. Preserve the simulator, the player's legitimate Steam/Proton setup,
existing game attachments and persistent data.

- Read CONTRIBUTING.md and the relevant docs before changing an area.
- Production code belongs in src/launcher. Keep scripts/jogo_deck.py and
  scripts/pratica_deck.py as stable command entrypoints; runtime modules do
  not import development scripts or investigation models.
- Keep the interface in English and public branding exactly ac-deck. Internal
  protocol, receipt and data identifiers retain their compatibility contracts.
- Preserve exclusive writes, atomic updates, locks, backup/recovery and receipt
  deduplication. Use the existing file_io mechanisms and feature-owned policies.
- Use the community builder profile and explicit source/payload inventories.
  Do not include game/DLC files, Steam data, credentials, private history or
  third-party material without verified redistribution rights.
- Use synthetic fixtures and offscreen composition for automated checks. Only
  open Steam, the launcher, a race, physical microphone or paid API when the
  user explicitly requests that action. Do not activate monitors by inference.
- Record the tested version and distinguish source changes, compiled behavior,
  published packages and physical Deck observations. A screenshot is not a
  performance measurement.
- Keep source changes focused and update their documentation and inventories
  together. Preserve contributor edits when synchronizing an exported revision.
- This repository has no local skills to duplicate. Shared project procedures
  are documented in CONTRIBUTING.md and docs; add a skill only for a concrete,
  recurring workflow.

Public release prerequisites are tracked in docs/community-release-checklist.md.
