#!/usr/bin/env bash
# Public installer for the exact community preview below. No GitHub login.
set -euo pipefail

release='v0.1.0-preview.3'
bootstrap_sha256='263a563f54bfadad0ff3d4b47bcf01ac285c0092fb3ab74407cc71436e437cda'
archive_sha256='813fba0308aee063318ef5e3c87d9323a170e3464ba39b8aa32aefb788aff9d2'
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
os_release=/etc/os-release
[ -r "$os_release" ] || os_release=/usr/lib/os-release
if [ -r "$os_release" ]; then
    ID= VERSION_ID=
    . "$os_release"
    if [ "$ID" = steamos ]; then
        python3 -c 'import re, sys; version = sys.argv[1]; sys.exit(not (re.fullmatch(r"[0-9]+[.][0-9]+[.][0-9]+", version) and tuple(map(int, version.split("."))) >= (3, 9, 5)))' "$VERSION_ID" \
            || fail 'Update to SteamOS 3.9.5 or newer on the Stable channel before installing.'
    fi
fi
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
