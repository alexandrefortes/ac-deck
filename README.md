# ac-deck community preview 001

Experimental Linux x86_64 community package. The runtime requires GLIBC 2.39; SteamOS compatibility, physical Steam Deck operation, performance and offline behavior have not been validated. A legitimate installed Assetto Corsa and Steam/Proton are required. Game files, CSP, mods and private media are not included.

- [Runtime archive](ac-deck-linux-x86_64.tar.gz)
- [Corresponding LGPL dependency sources](ac-deck-dependency-sources.tar.gz) and [inventory](dependency-source-inventory.json)
- [SHA-256 checksums](SHA256SUMS)
- [Project source and documentation](https://github.com/alexandrefortes/ac-deck/tree/main)

Verify the checksums before extracting. The runtime archive includes LICENSE and NOTICE and the third-party notices. Project-owned code uses PolyForm Noncommercial 1.0.0, including the permissions stated in the license; third-party components retain their own licenses and rights. The corresponding dependency sources are distributed alongside the runtime. The original application source used to compile this runtime is commit `27a9bf1cb05904490f36481ee491d9b6ef88ccae` in the public source repository. The executable matches the previously tested candidate; the release assembly adds the project license and notice and updates the manifest.

This preview is provided for evaluation. It does not establish a supported installation or update path on physical Steam Deck hardware. See the main repository for known limitations and issue reporting.
