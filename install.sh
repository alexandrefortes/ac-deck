#!/usr/bin/env bash
# Public installer for the exact community preview below. No GitHub login.
set -euo pipefail

release='v0.1.0-preview.2'
bootstrap_sha256='263a563f54bfadad0ff3d4b47bcf01ac285c0092fb3ab74407cc71436e437cda'
archive_sha256='72c1124a647fad0f7d03a1612aac6d9bda5deebd0e172ad9a6e541c1e851d28f'
minimum_glibc='2.38'
base="https://github.com/alexandrefortes/ac-deck/releases/download/$release"

fail() { printf 'Installation stopped: %s\n' "$*" >&2; exit 1; }
[ "$(uname -s)" = Linux ] || fail 'Run this command on your Steam Deck in Desktop Mode.'
[ "$(uname -m)" = x86_64 ] || fail 'This preview requires Linux x86_64.'
[ "$(id -u)" != 0 ] || fail 'Run as your normal Deck user, without sudo.'
for tool in curl python3 sha256sum getconf mktemp; do
    command -v "$tool" >/dev/null || fail "Required system command is missing: $tool."
done
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' \
    || fail 'System Python 3.10 or newer is required.'
glibc=$(getconf GNU_LIBC_VERSION) || fail 'Cannot identify the system C library.'
glibc=${glibc#glibc }
python3 -c 'import sys; version=lambda s: tuple(map(int,s.split("."))); sys.exit(version(sys.argv[1]) < version(sys.argv[2]))' "$glibc" "$minimum_glibc" \
    || fail "This preview requires GLIBC $minimum_glibc or newer. Update SteamOS through its normal updater."

temporary=$(mktemp -d) || fail 'Cannot create the download folder.'
trap 'rm -f -- "$temporary/install_ac_deck.py"; rmdir -- "$temporary"' EXIT
printf 'Downloading ac-deck %s. No GitHub account is needed.\n' "$release"
curl --fail --show-error --location --proto '=https' --proto-redir '=https' \
    "$base/install_ac_deck.py" --output "$temporary/install_ac_deck.py"
printf '%s  %s\n' "$bootstrap_sha256" "$temporary/install_ac_deck.py" | sha256sum --check --status \
    || fail 'The installer checksum does not match. No setup was started.'
python3 -B "$temporary/install_ac_deck.py" \
    --url "$base/ac-deck-linux-x86_64.tar.gz" --sha256 "$archive_sha256" \
    --reuse-verified --run-setup "$@"
