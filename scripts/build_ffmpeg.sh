#!/bin/zsh
# Builds an LGPL ffmpeg + ffprobe for bundling in MSTR-SL8R Ingest, into vendor/ffmpeg/bin.
#
#   scripts/build_ffmpeg.sh            # build (needs Xcode CLT, nasm optional, ~5 min on Apple Silicon)
#
# Why build it ourselves: third-party static builds are usually GPL (x264/x265) and of
# unknown provenance. Everything the ingest presets need is available without GPL:
# VideoToolbox (ProRes / H.264 / HEVC hardware encode), native prores_ks, dnxhd, aac,
# lut3d, scale/pad. No --enable-gpl, no --enable-nonfree.
# drawtext (burn-ins) needs libfreetype; not enabled here yet (it would need a static
# freetype build too), so burn-ins stay off with the bundled binary.
#
# Supply chain: the source tarball is downloaded from ffmpeg.org and must match
# FFMPEG_SHA256 below. On a version bump, fetch the tarball, verify it against the
# published .asc signature (gpg --verify), then pin the new SHA-256 here.
set -euo pipefail
cd "${0:A:h}/.."

FFMPEG_VERSION="${FFMPEG_VERSION:-9.0.2}"
FFMPEG_SHA256="${FFMPEG_SHA256:-PIN_ME_AFTER_VERIFYING_THE_SIGNATURE}"
ARCHS=(${=FFMPEG_ARCHS:-arm64 x86_64})
MIN_MACOS="14.0"
WORK="build/ffmpeg-src"
OUT="vendor/ffmpeg"
TARBALL="$WORK/ffmpeg-$FFMPEG_VERSION.tar.xz"

mkdir -p "$WORK" "$OUT/bin"
if [[ ! -f "$TARBALL" ]]; then
  echo "Downloading ffmpeg $FFMPEG_VERSION source from ffmpeg.org"
  curl -fL --proto '=https' -o "$TARBALL" "https://ffmpeg.org/releases/ffmpeg-$FFMPEG_VERSION.tar.xz"
fi
GOT=$(shasum -a 256 "$TARBALL" | cut -d' ' -f1)
if [[ "$GOT" != "$FFMPEG_SHA256" ]]; then
  echo "error: SHA-256 mismatch for $TARBALL"
  echo "  expected $FFMPEG_SHA256"
  echo "  got      $GOT"
  echo "Verify the tarball's signature from ffmpeg.org, then pin FFMPEG_SHA256 in this script."
  exit 1
fi

COMMON=(
  --disable-gpl --disable-nonfree --enable-version3
  --enable-static --disable-shared --disable-autodetect
  --enable-videotoolbox --enable-audiotoolbox --enable-pthreads
  --disable-ffplay --disable-doc --disable-network --disable-debug
  --disable-xlib --disable-sdl2 --disable-iconv --disable-securetransport
)

for ARCH in "${ARCHS[@]}"; do
  SRC="$WORK/src-$ARCH"
  rm -rf "$SRC"; mkdir -p "$SRC"
  tar -xJf "$TARBALL" -C "$SRC" --strip-components 1
  echo "Configuring for $ARCH"
  (cd "$SRC" && ./configure "${COMMON[@]}" --prefix="$PWD/../install-$ARCH" \
      --arch="$ARCH" --target-os=darwin --enable-cross-compile \
      --cc="clang -arch $ARCH" \
      --extra-cflags="-mmacosx-version-min=$MIN_MACOS" --extra-ldflags="-mmacosx-version-min=$MIN_MACOS" \
      $( [[ "$ARCH" == x86_64 ]] && command -v nasm >/dev/null || echo --disable-x86asm ) >/dev/null)
  (cd "$SRC" && make -j"$(sysctl -n hw.ncpu)" >/dev/null && make install >/dev/null)
done

for TOOL in ffmpeg ffprobe; do
  lipo -create $(for A in "${ARCHS[@]}"; do echo "$WORK/install-$A/bin/$TOOL"; done) -output "$OUT/bin/$TOOL"
done
"$OUT/bin/ffmpeg" -hide_banner -version | head -1 > "$OUT/VERSION"
"$OUT/bin/ffmpeg" -hide_banner -buildconf > "$OUT/BUILDCONF"
cp "$WORK/src-${ARCHS[1]}/COPYING.LGPLv3" "$OUT/LICENSE.txt" 2>/dev/null || cp "$WORK/src-${ARCHS[1]}/COPYING.LGPLv2.1" "$OUT/LICENSE.txt"
echo "$FFMPEG_VERSION $FFMPEG_SHA256 https://ffmpeg.org/releases/ffmpeg-$FFMPEG_VERSION.tar.xz" > "$OUT/SOURCE"
if grep -q -- "--enable-gpl" "$OUT/BUILDCONF"; then echo "error: GPL build"; exit 1; fi
echo "Built $(cat "$OUT/VERSION") → $OUT/bin ($(lipo -archs "$OUT/bin/ffmpeg"))"
