# Contributing to ac-deck

ac-deck contains a reviewed launcher source export, a community builder, synthetic tests and interface previews. These files are prepared locally; publication, the first-party license decision and a validated public package remain pending.

## Useful contributions now

- Correct confusing documentation and broken links.
- Identify missing installation or update information from a new user's perspective.
- Report a preview's readability or navigation problem with the screen and image resolution.
- Propose a focused improvement to the Steam Deck single-player experience.

Use [GitHub issues](https://github.com/alexandrefortes/ac-deck/issues) for questions, bug reports and feature proposals. Small documentation corrections can be submitted as a focused pull request.

## Reporting a problem

Follow [troubleshooting](docs/troubleshooting.md). Include a reproducible example, the affected page or exact runtime version, and expected versus actual behavior. Identify whether the evidence comes from a demonstration preview, an automated check or real Steam Deck use.

Remove credentials, account details and private paths from screenshots and logs. Include only the files needed to understand the report.

## Code contributions and checks

Production code belongs in `src/launcher/`. `scripts/jogo_deck.py` and `scripts/pratica_deck.py` are stable command entrypoints. The [source inventory](public-source-manifest.json) records the selected export; the repository does not include unrelated private history.

Use Python **3.13.5** and install the [hash-pinned dependencies](scripts/launcher-linux-requirements.txt) into an explicit local virtual environment, as shown in the [source build guide](docs/installation.md#building-from-source).

From the repository root, run the public test selection:

```sh
python -B -m unittest discover -s tests -v
```

This selection checks filesystem safety, pure INI/session contracts, command entrypoints and the community builder's payload boundary. Its fixtures are authored demonstration data. The builder tests simulate compilation and do not establish real packaged or Steam Deck behavior.

Safe command-line checks are also available:

```sh
python -B scripts/jogo_deck.py --help
python -B scripts/pratica_deck.py --help
python -B scripts/build_launcher_linux.py --help
```

Compile the community profile with the real builder documented in the [installation guide](docs/installation.md#building-from-source). Its native-library, font and license-notice paths are explicit inputs; the builder does not download or install them. Use `--community` for the public candidate.

For code changes:

1. Start with a concrete behavior or ownership problem and keep the change focused.
2. Preserve existing game attachments, player data, Steam/Proton integration and explicit player control over race starts.
3. Run the affected tests and the public selection above. Report failures, skips and the tested Python/platform accurately.
4. Describe the change, its verification and any remaining Steam Deck validation in the pull request.

## Licensing and third-party material

Project-owned code licensing is still being finalized. Check the repository's recorded licensing before reusing code or submitting material under license terms.

Contributions must identify their provenance and applicable permissions. Game/DLC files, Steam data, CSP archives, credentials, private session records and unreviewed third-party mod/media payloads are outside the public distribution. Software licenses do not automatically grant rights to unrelated images or audio.

## Public release review

Source, package, documentation and screenshots must pass an explicit review before a public release is marked verified. Follow the [community release checklist](docs/community-release-checklist.md). Source tests, simulated builds and screenshots do not establish physical Steam Deck support.
