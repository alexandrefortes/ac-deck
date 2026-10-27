# Troubleshooting

The prepared repository contains reviewed source, a community builder, synthetic tests and interface previews. There is no validated public installer or runtime release yet. Reports can identify source-test failures, local build issues, incorrect documentation, broken links and unreadable previews.

## Check the available evidence

- For documentation, include the page and the step or sentence that caused the problem.
- For interface previews, include the screen and image resolution. The screenshots use demonstration data and do not establish real race or hardware behavior.
- For a future public runtime report, identify the exact launcher version or source revision and how it was installed.

## Runtime checks for a reviewed package

| Symptom | Useful checks |
| --- | --- |
| Launcher does not start | Confirm the documented platform, package checksum, launch entry and complete extraction. Include the first error and the launcher version. |
| Game is not found | Confirm that the original Assetto Corsa is installed through Steam and that the documented game attachment points to that installation. |
| Car, track or event is missing | Confirm that the required game/DLC/mod content is installed and compatible. The launcher discovers content from the player's installation. |
| Race fails to start | Record the selected content, launcher graphics profile, SteamOS and Proton versions, and the displayed error. Distinguish launcher startup from game startup. |
| Optional AI or dictation fails | Check the selected service/model, network access and configured credentials. Share the error text with credentials removed. Manual setup remains independent of AI. |
| Progress or settings appear missing | Stop changes to that data, identify the effective attachment/data paths and consult the release's [recovery instructions](update-and-recovery.md). |

These checks help gather evidence; they are not a published compatibility guarantee. Game reinstalls, prefix deletion and profile resets should not be used as generic diagnostic steps.

## Report a reproducible problem

Use [GitHub issues](https://github.com/alexandrefortes/ac-deck/issues) and provide:

1. The affected page or the exact launcher version/source revision.
2. SteamOS and Proton versions for a runtime issue.
3. The smallest steps that reproduce the problem.
4. Expected behavior, actual behavior and any displayed error.
5. Relevant screenshots or a short sanitized log excerpt.

Remove API keys, tokens, account details and private paths before attaching files. Share a relevant excerpt rather than an entire Steam/Proton prefix, game installation or session archive.

For a feature proposal, describe the task you want to complete and how the current behavior gets in the way. See [CONTRIBUTING](../CONTRIBUTING.md).
