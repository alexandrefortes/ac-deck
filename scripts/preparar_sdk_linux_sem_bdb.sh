#!/usr/bin/env bash
# Setup explícito e separado; nunca é chamado pelo ciclo de entrega.
set -euo pipefail
if [[ $# != 4 ]]; then
    echo "Usage: bash $0 SOURCE_COLLECTION NEW_PREFIX NEW_WORK WHEEL_DIRECTORY" >&2
    exit 2
fi
sources=$(realpath -e "$1")
prefix=$(realpath -m "$2")
work=$(realpath -m "$3")
wheels=$(realpath -e "$4")
script=$(realpath -e "$0")
requirements=$(dirname "$script")/launcher-linux-requirements.txt
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]]
[[ $prefix != *' '* && $work != *' '* && ! -e $prefix && ! -e $work ]]
[[ $prefix != "$work" && $prefix != "$work/"* && $work != "$prefix/"* ]]
cd "$sources"
sha256sum --check <<'HASHES'
93e583f243454e6e9e4588ca2c2662206ad961659863277afcdb96801647d640  python-standalone/cpython-3.13/Python-3.13.5.tar.xz
9a93b2b7dfdac77ceba5a558a580e74667dd6fede4585b91eefb60f03b72df23  python-standalone/zlib/zlib-1.3.1.tar.gz
ab5a03176ee106d3f0fa90e381da478ddae405918153cca248e682cd0c4a2269  python-standalone/bzip2/bzip2-1.0.8.tar.gz
61bda930767dcb170a5328a895ec74cab0f5aac4558cdda561c83559db582a13  python-standalone/xz/xz-5.2.12.tar.gz
b0dea9df23c863a7a50e825440f3ebffabd65df1497108e5d437747843895a4e  python-standalone/libffi/libffi-3.4.6.tar.gz
57e03c50feab5d31b152af2b764f10379aecd8ee92f16c985983ce4a99f7ef86  python-standalone/openssl-3.0/openssl-3.0.16.tar.gz
416a6f45bf2cacd494b208fdee1beda509abda951d5f47bc4f2792126f01b452  python-standalone/sqlite/sqlite-autoconf-3470100.tar.gz
HASHES
mkdir -p "$(dirname "$prefix")" "$(dirname "$work")"
mkdir "$prefix" "$work"
exec > >(tee "$work/setup.log") 2>&1
set -x
cp "$script" "$work/recipe.sh"
cp "$requirements" "$work/requirements.lock"
uname -a
gcc --version
make --version
export CC=gcc CFLAGS='-O2 -fPIC' CPPFLAGS="-I$prefix/include"
export LDFLAGS="-L$prefix/lib -Wl,-rpath,$prefix/lib"
export LD_LIBRARY_PATH="$prefix/lib" PYTHONDONTWRITEBYTECODE=1
unset PYTHONPATH PYTHONHOME LIBRARY_PATH CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH
unset PKG_CONFIG_PATH PKG_CONFIG_LIBDIR CONFIG_SITE
mkdir "$prefix/include" "$prefix/lib"
for archive in \
    zlib/zlib-1.3.1.tar.gz bzip2/bzip2-1.0.8.tar.gz xz/xz-5.2.12.tar.gz \
    libffi/libffi-3.4.6.tar.gz openssl-3.0/openssl-3.0.16.tar.gz \
    sqlite/sqlite-autoconf-3470100.tar.gz cpython-3.13/Python-3.13.5.tar.xz; do
    tar --no-same-owner --no-same-permissions -xf "$sources/python-standalone/$archive" -C "$work"
done
cd "$work/zlib-1.3.1"
./configure --static --prefix="$prefix"
make -j8
make install
cd "$work/bzip2-1.0.8"
make -j8 libbz2.a CFLAGS='-O2 -fPIC -D_FILE_OFFSET_BITS=64'
install -m644 libbz2.a "$prefix/lib/libbz2.a"
install -m644 bzlib.h "$prefix/include/bzlib.h"
cd "$work/xz-5.2.12"
./configure --prefix="$prefix" --libdir="$prefix/lib" --disable-shared --enable-static --with-pic \
    --disable-xz --disable-xzdec --disable-lzmadec --disable-lzmainfo --disable-scripts --disable-doc --disable-nls
make -j8
make install
cd "$work/libffi-3.4.6"
./configure --prefix="$prefix" --libdir="$prefix/lib" --disable-shared --enable-static --with-pic --disable-docs
make -j8
make install
cd "$work/openssl-3.0.16"
./Configure linux-x86_64 no-shared no-tests --prefix="$prefix" --libdir=lib --openssldir=/etc/ssl -fPIC
make -j8
make install_sw
cd "$work/sqlite-autoconf-3470100"
./configure --prefix="$prefix" --libdir="$prefix/lib" --disable-shared --enable-static --with-pic --disable-readline
make -j8
make install
cd "$work/Python-3.13.5"
printf '*disabled*\n_dbm\n_gdbm\nreadline\n_tkinter\n_curses\n_curses_panel\n_uuid\n' > Modules/Setup.local
export ZLIB_CFLAGS="-I$prefix/include" ZLIB_LIBS="$prefix/lib/libz.a"
export BZIP2_CFLAGS="-I$prefix/include" BZIP2_LIBS="$prefix/lib/libbz2.a"
export LIBLZMA_CFLAGS="-I$prefix/include" LIBLZMA_LIBS="$prefix/lib/liblzma.a"
export LIBFFI_CFLAGS="-I$prefix/include" LIBFFI_LIBS="$prefix/lib/libffi.a"
export LIBSQLITE3_CFLAGS="-I$prefix/include" LIBSQLITE3_LIBS="$prefix/lib/libsqlite3.a -lm"
export OPENSSL_INCLUDES="-I$prefix/include" OPENSSL_LDFLAGS="-L$prefix/lib"
export OPENSSL_LIBS="$prefix/lib/libssl.a $prefix/lib/libcrypto.a -ldl -pthread"
./configure --prefix="$prefix" --enable-shared --without-static-libpython --with-ensurepip=install \
    --without-readline --with-pkg-config=no --with-system-libmpdec=no \
    --with-openssl="$prefix" --with-openssl-rpath=no
make -j8
make install
"$prefix/bin/python3.13" -B -m pip install --no-cache-dir --no-index --find-links="$wheels" \
    --only-binary=:all: --require-hashes -r "$work/requirements.lock"
"$prefix/bin/python3.13" -B -c 'import ssl, zlib, bz2, lzma, ctypes, sqlite3, multiprocessing, importlib.util as u; assert u.find_spec("_dbm") is None and u.find_spec("_gdbm") is None; print(ssl.OPENSSL_VERSION, zlib.ZLIB_RUNTIME_VERSION, sqlite3.sqlite_version)'
echo "SDK setup completed: $prefix"
