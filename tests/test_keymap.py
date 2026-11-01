"""Host interpretation of the actual keymap, using ZMK headers and libxkbcommon.

These checks do not emulate firmware timing or Windows/Citrix. Full firmware
compilation is a separate `just build` check; hardware testing is still required.
"""
import ctypes as C
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "config/imprint.keymap").read_text()
SOURCE = re.sub(r"//[^\n]*|/\*.*?\*/", "", SOURCE, flags=re.S)
NODES = dict(re.findall(r"(\w+)\s*\{([^{}]*?)\};", SOURCE, re.S))


def bindings(name):
    body = re.search(r"bindings\s*=\s*(.*?);", NODES[name], re.S)[1]
    return [b.replace(">", "").replace("<", "").replace(",", "").split()
            for b in body.split("&")[1:]]


LAYERS = list(re.findall(r"(\w+)\s*\{\s*bindings", SOURCE))


def navigation(base, position):
    active = {0, base, 3}
    for body in NODES.values():
        condition = re.search(r"if-layers\s*=\s*<([^>]+)>;", body)
        target = re.search(r"then-layer\s*=\s*<(\d+)>;", body)
        if condition and target and set(map(int, condition[1].split())) <= active:
            active.add(int(target[1]))
    for layer in sorted(active, reverse=True):
        result = bindings(LAYERS[layer])[position]
        if result != ["trans"]:
            return result
    raise AssertionError("No binding")


class Names(C.Structure):
    _fields_ = [(name, C.c_char_p) for name in ("rules", "model", "layout", "variant", "options")]


class Host:
    # USB HID usages -> Linux evdev codes (XKB adds 8).
    EVDEV = dict(zip(range(30, 40), range(2, 12))) | {
        5: 48, 8: 18, 28: 21, 44: 57, 46: 13, 48: 27, 53: 41, 83: 69,
        87: 78, 89: 79, 90: 80, 91: 81, 92: 75, 93: 76,
        94: 77, 95: 71, 96: 72, 97: 73, 98: 82, 103: 117,
    }

    def __init__(self, variant):
        self.lib = C.CDLL(os.environ["XKB_LIBRARY"])
        for name, args, result in [
            ("context_new", [C.c_int], C.c_void_p),
            ("keymap_new_from_names", [C.c_void_p, C.POINTER(Names), C.c_int], C.c_void_p),
            ("state_new", [C.c_void_p], C.c_void_p),
            ("state_update_key", [C.c_void_p, C.c_uint, C.c_int], C.c_int),
            ("state_key_get_one_sym", [C.c_void_p, C.c_uint], C.c_uint),
            ("keysym_to_utf32", [C.c_uint], C.c_uint),
            ("state_unref", [C.c_void_p], None),
            ("keymap_unref", [C.c_void_p], None),
            ("context_unref", [C.c_void_p], None),
            ("compose_table_new_from_locale", [C.c_void_p, C.c_char_p, C.c_int], C.c_void_p),
            ("compose_state_new", [C.c_void_p, C.c_int], C.c_void_p),
            ("compose_state_feed", [C.c_void_p, C.c_uint], C.c_int),
            ("compose_state_get_status", [C.c_void_p], C.c_int),
            ("compose_state_get_utf8", [C.c_void_p, C.c_char_p, C.c_size_t], C.c_int),
            ("compose_state_reset", [C.c_void_p], None),
            ("compose_state_unref", [C.c_void_p], None),
            ("compose_table_unref", [C.c_void_p], None),
        ]:
            fn = getattr(self.lib, "xkb_" + name)
            fn.argtypes, fn.restype = args, result
        self.context = self.lib.xkb_context_new(0)
        names = Names(b"evdev", b"pc105", b"de", variant.encode(), b"")
        self.keymap = self.lib.xkb_keymap_new_from_names(self.context, C.byref(names), 0)
        assert self.keymap, "Could not load XKB layout"
        self.state = self.lib.xkb_state_new(self.keymap)

    def close(self):
        self.lib.xkb_state_unref(self.state)
        self.lib.xkb_keymap_unref(self.keymap)
        self.lib.xkb_context_unref(self.context)

    def tap(self, code):
        modifiers = [key + 8 for bit, key in [(1, 29), (2, 42), (64, 100)] if (code >> 24) & bit]
        key = self.EVDEV[code & 0xFFFF] + 8
        for modifier in modifiers:
            self.lib.xkb_state_update_key(self.state, modifier, 1)
        self.lib.xkb_state_update_key(self.state, key, 1)
        symbol = self.lib.xkb_state_key_get_one_sym(self.state, key)
        self.lib.xkb_state_update_key(self.state, key, 0)
        for modifier in reversed(modifiers):
            self.lib.xkb_state_update_key(self.state, modifier, 0)
        return symbol

    def text(self, code):
        return chr(self.lib.xkb_keysym_to_utf32(self.tap(code)))

    def compose(self, codes):
        table = self.lib.xkb_compose_table_new_from_locale(self.context, b"en_US.UTF-8", 0)
        assert table, "Could not load Compose table"
        state = self.lib.xkb_compose_state_new(table, 0)
        output = ""
        try:
            for code in codes:
                symbol = self.tap(code)
                self.lib.xkb_compose_state_feed(state, symbol)
                status = self.lib.xkb_compose_state_get_status(state)
                if status == 0:  # Nothing composing: ordinary character.
                    output += chr(self.lib.xkb_keysym_to_utf32(symbol))
                elif status == 2:  # Composed.
                    buffer = C.create_string_buffer(64)
                    self.lib.xkb_compose_state_get_utf8(state, buffer, len(buffer))
                    output += buffer.value.decode()
                    self.lib.xkb_compose_state_reset(state)
                else:
                    assert status == 1, "Compose sequence cancelled"
            assert self.lib.xkb_compose_state_get_status(state) == 0, "Unfinished dead key"
            return output
        finally:
            self.lib.xkb_compose_state_unref(state)
            self.lib.xkb_compose_table_unref(table)


class KeymapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        expressions = {b[-1] for name in NODES if "bindings" in NODES[name]
                       for b in bindings(name) if b[0] in ("kp", "lt", "mt")}
        expressions |= {"KP_NUMLOCK", "SPACE"}
        expressions = sorted(expressions)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "codes.c"
            source.write_text('#include <stdio.h>\n#include <dt-bindings/zmk/keys.h>\n#include "keys_de.h"\nint main(void) {\n' +
                              "\n".join(f'printf("%u\\n", (unsigned)({e}));' for e in expressions) + "\n}\n")
            subprocess.run(["cc", "-I", str(ROOT / ".build/zmk/app/include"), "-I", str(ROOT / "config"),
                            str(source), "-o", tmp + "/codes"], check=True)
            values = subprocess.check_output([tmp + "/codes"], text=True).splitlines()
        cls.codes = dict(zip(expressions, map(int, values)))

    def test_navigation_symbols_on_both_hosts(self):
        for base, variant in [(0, "neo"), (1, "")]:
            host = Host(variant)
            self.addCleanup(host.close)
            for position, expected in [(18, "="), (22, "+")]:
                with self.subTest(variant=variant, position=position):
                    self.assertEqual(host.text(self.codes[navigation(base, position)[1]]), expected)

    def test_navigation_numbers_ignore_numlock(self):
        positions = {19: "7", 20: "8", 21: "9", 31: "4", 32: "5", 33: "6",
                     43: "1", 44: "2", 45: "3", 54: "0", 63: "0"}
        for base, variant in [(0, "neo"), (1, "")]:
            host = Host(variant)
            self.addCleanup(host.close)
            for numlock in [False, True]:
                if numlock:
                    host.tap(self.codes["KP_NUMLOCK"])
                for position, expected in positions.items():
                    with self.subTest(variant=variant, numlock=numlock, position=position):
                        self.assertEqual(host.text(self.codes[navigation(base, position)[1]]), expected)

    def test_undo_is_ctrl_z_for_each_host(self):
        for base, variant in [(0, "neo"), (1, "")]:
            host = Host(variant)
            self.addCleanup(host.close)
            code = self.codes[navigation(base, 41)[1]]
            with self.subTest(variant=variant):
                self.assertEqual(code >> 24, 1, "Undo must use Control")
                self.assertEqual(host.text(code & 0xFFFFFF), "z")

    def test_programming_accents_do_not_change_next_letter(self):
        host = Host("")
        self.addCleanup(host.close)
        for position, expected in [(17, "^e"), (41, "`e")]:
            binding = bindings("Programming")[position]
            with self.subTest(position=position):
                sequence = [binding] if binding[0] == "kp" else bindings(binding[0])
                codes = [self.codes[b[1]] for b in sequence] + [self.codes["DE_E"]]
                self.assertEqual(host.compose(codes), expected)

    def test_factory_test_has_an_exit(self):
        exit_binding = bindings("factory_test")[11]
        exit_steps = [exit_binding] if exit_binding[0] == "to" else bindings(exit_binding[0])
        self.assertIn(["to", "0"], exit_steps)

    def test_mouse_is_reachable_and_automatic(self):
        self.assertIn(["mo", "8"], bindings("Qwertz"))
        self.assertRegex(SOURCE, r"&trackball_peripheral_listener\s*\{\s*input-processors\s*=\s*<&zip_temp_layer\s+5\s+\d+>")
        for position in (26, 27, 28):
            self.assertEqual(bindings("Manual_Mouse_Layer")[position], bindings("Auto_Mouse_Layer")[position])

    def test_thumb_enter_holds_scroll_in_both_host_modes(self):
        self.assertEqual(bindings("Qwertz")[62], ["lt", "9", "ENTER"])
        self.assertEqual(bindings("NEO_Layout")[62], ["trans"])
        self.assertEqual(bindings("Scroll_Mode")[62], ["trans"])

    def test_battery_shortcut_uses_os_keys(self):
        for position in (48, 57):
            self.assertEqual(bindings("Qwertz")[position], ["mo", "4"])
        for position in (50, 65):
            self.assertEqual(bindings("Keyboard_Control_Layer")[position], ["bat_led"])

    def test_layer_sizes(self):
        for layer in LAYERS:
            self.assertEqual(len(bindings(layer)), 70, layer)


if __name__ == "__main__":
    unittest.main()
