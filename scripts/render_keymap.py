#!/usr/bin/env python3
"""Render the actual ZMK bindings and the repository's 70-key geometry."""
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LAYERS = [
    "0 - Host Neo: QWERTZ-Tastencodes",
    "1 - Neo-Emulation: Host QWERTZ",
    "2 - Programmierzeichen: Host QWERTZ",
    "3 - Navigation: Host Neo",
    "4 - Tastatursteuerung",
    "5 - Maus automatisch: rechter Trackball",
    "6 - Werkstest",
    "7 - Navigation QWERTZ: automatisch bei 1 + 3",
    "8 - Maus manuell: Taste halten",
    "9 - Trackball-Scrollmodus: umschaltbar",
]


def main():
    # Preserve the DE_* names instead of expanding them to opaque HID integers.
    # Their display legends come from the locale header, including its aliases.
    header = (ROOT / "config/keys_de.h").read_text()
    codes = {name: symbol.upper() if symbol.isascii() and symbol.isalpha() else symbol
             for symbol, name in re.findall(r"/\* ([^*\n]+) \*/\s*#define (DE_\w+)", header)}
    codes["DE_ASTERISK"] = "*"  # The comment for '*' contains the delimiter character.
    aliases = re.findall(r"#define (DE_\w+) \((DE_\w+)\)", header)
    for _ in range(2):
        codes.update({alias: codes[target] for alias, target in aliases if target in codes})
    codes.update({
        "DE_SPACE": "Space", "SPACE": "Space", "BACKSPACE": "Bksp",
        "ESCAPE": "Esc", "ESC": "Esc", "ENTER": "Enter", "TAB": "Tab",
        "DELETE": "Del", "DEL": "Del", "INSERT": "Ins", "PRINTSCREEN": "Print",
        "LEFT_CONTROL": "Ctrl", "LCTRL": "Ctrl", "RCTRL": "Ctrl",
        "LEFT_SHIFT": "Shift", "RSHFT": "Shift", "CAPSLOCK": "Caps/Mod3",
        "LEFT_GUI": "Super", "LGUI": "Super", "LALT": "Alt", "RALT": "AltGr",
        "KP_EQUAL": "=", "KP_PLUS": "+", "PAGE_UP": "PgUp", "PAGE_DOWN": "PgDn",
        "HOME": "Home", "END": "End", "UP": "↑", "DOWN": "↓", "LEFT": "←", "RIGHT": "→",
    })
    raw = {
        "&switch_to_neo": {"t": "Host DE", "h": "wechseln", "type": "layer"},
        "&switch_to_de": {"t": "Host Neo", "h": "wechseln", "type": "layer"},
        "&factory_exit": {"t": "Werkstest", "h": "verlassen", "type": "layer"},
        "&literal_caret": "^", "&literal_grave": "`",
        "&kp EQUAL": {"t": "´", "s": "tot"},
        "&kp DE_CARET": {"t": "^", "s": "tot"},
        "&lt 2 DE_CARET": {"t": "^", "h": "Sym", "s": "tot"},
        "&lt 9 ENTER": {"t": "Enter", "h": "Scroll", "type": "layer"},
        "&kp LC(B)": "Undo", "&kp LC(DE_Z)": "Undo",
        "&kp LC(RIGHT_ALT)": "Ctrl+AltGr",
        "&kp RA(DE_N1)": "AltGr+1", "&kp RA(DE_N2)": "²", "&kp RA(DE_N3)": "³",
        "&mkp RCLK": {"t": "Rechts", "h": "Klick", "type": "mouse"},
        "&mkp MCLK": {"t": "Mitte", "h": "Klick", "type": "mouse"},
        "&mkp LCLK": {"t": "Links", "h": "Klick", "type": "mouse"},
        "&none": {"t": "×", "type": "trans"},
        "&sys_reset": "Neustart", "&bootloader": "Bootloader",
        "&bat_led": "Akku",
        "&studio_unlock": "Studio frei", "&bt BT_CLR": "BT löschen",
        "&to 6": {"t": "Werkstest", "h": "wechseln", "type": "layer"},
        "&tog 9": {"t": "Scroll", "h": "umschalten", "type": "layer"},
    }
    for index, label in {2: "Sym", 3: "Nav", 4: "System", 8: "Maus"}.items():
        raw[f"&mo {index}"] = {"t": label, "h": "halten", "type": "layer"}
    for index in range(5):
        raw[f"&bt BT_SEL {index}"] = f"BT {index}"
    for command, label in {
        "TOG": "RGB an/aus", "EFF": "RGB Effekt", "HUI": "Farbton +", "HUD": "Farbton −",
        "SAI": "Sättigung +", "SAD": "Sättigung −", "BRI": "Helligkeit +", "BRD": "Helligkeit −",
        "SPI": "Tempo +", "SPD": "Tempo −",
    }.items():
        raw[f"&rgb_ug RGB_{command}"] = label
    config = {
        "parse_config": {"preprocess": False, "zmk_keycode_map": codes, "raw_binding_map": raw},
        "draw_config": {
            "key_w": 64, "key_h": 60, "outer_pad_w": 28, "outer_pad_h": 46,
            "append_colon_to_layer_header": False, "shrink_wide_legends": 6,
            "svg_extra_style": """
svg.keymap { font-family: 'DejaVu Sans', sans-serif; font-size: 13px; }
rect.key { fill: #f8fafc; stroke: #94a3b8; }
rect.layer { fill: #dbeafe; stroke: #3b82f6; }
rect.mouse { fill: #dcfce7; stroke: #16a34a; }
rect.trans { fill: #f1f5f9; stroke: #cbd5e1; }
text.trans { fill: #94a3b8; }
text.hold, text.shifted { font-size: 10px; }
text.label { font-size: 18px; fill: #0f172a; stroke: none; }
""",
        },
    }
    output = ROOT / "docs/keymap"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        config_file = Path(directory) / "config.json"
        keymap_file = Path(directory) / "keymap.yaml"
        config_file.write_text(json.dumps(config, ensure_ascii=False))
        command = ["keymap", "-c", str(config_file)]
        subprocess.run(command + ["parse", "-z", str(ROOT / "config/imprint.keymap"),
                                  "-o", str(keymap_file), "--layer-names", *LAYERS], check=True)
        draw = command + ["draw", str(keymap_file), "-j", str(ROOT / "config/info.json"), "-l", "Imprint"]
        subprocess.run(draw + ["-o", str(output / "all-layers.svg")], check=True)
        for index, layer in enumerate(LAYERS):
            subprocess.run(draw + ["-o", str(output / f"layer-{index}.svg"), "-s", layer], check=True)
        # Explicit SVG background stays readable in both light and dark READMEs.
        for name in ["all-layers", *(f"layer-{i}" for i in range(len(LAYERS)))]:
            path = output / f"{name}.svg"
            svg = path.read_text()
            svg = svg.replace("<style>", '<rect width="100%" height="100%" fill="white"/>\n<style>', 1)
            path.write_text(svg)
    print(f"Rendered {len(LAYERS)} layers to {output}")


if __name__ == "__main__":
    main()
