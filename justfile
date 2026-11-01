default:
    @just --list

# Render all firmware layers from the keymap and config/info.json.
[group('docs')]
render:
    python3 scripts/render_keymap.py

# Fetch the firmware dependencies into .build (requires rootless Podman).
[group('build')]
setup:
    bash scripts/firmware.sh setup

# Build both keyboard halves; output: .build/left and .build/right.
[group('build')]
build:
    bash scripts/firmware.sh build

# Check the actual keycodes against German and Neo using libxkbcommon.
[group('test')]
test:
    python3 -m unittest discover -s tests -v

[group('validate')]
check: test build
    git diff --check
