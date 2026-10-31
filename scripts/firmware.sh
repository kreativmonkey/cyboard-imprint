#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .build

# Same build environment as the ZMK workflow, pinned for local reproducibility.
image=docker.io/zmkfirmware/zmk-build-arm@sha256:ca4978c179533772d3a77296bc628f8a3ae1ed75ee1cc8b411570f9810fd821e
podman run --rm --userns=keep-id -e HOME=/tmp \
    -v "$PWD:/config:ro" -v "$PWD/.build:/work" -w /work \
    "$image" bash -euc '
        case "$1" in
            setup)
                mkdir -p config
                cp /config/config/west.yml config/west.yml
                if [ ! -d .west ]; then west init -l config; fi
                west update --narrow --fetch-opt=--depth=1
                ;;
            build)
                if [ ! -d .west ]; then echo "Run just setup first" >&2; exit 1; fi
                west zephyr-export
                for side in left right; do
                    west build -p always -s zmk/app -d "$side" -b assimilator-bt -- \
                        -DZMK_CONFIG=/config/config \
                        -DZMK_EXTRA_MODULES=/config \
                        -DSHIELD="imprint_$side"
                done
                ;;
            *) echo "Usage: firmware.sh setup|build" >&2; exit 2 ;;
        esac
    ' -- "$@"
