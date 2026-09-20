import importlib.util
import pathlib
import sys
import unittest


TOOLS = pathlib.Path(__file__).parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
SCRIPT = TOOLS / "convert_core_hud.py"
SPEC = importlib.util.spec_from_file_location("convert_core_hud", SCRIPT)
HUD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = HUD
SPEC.loader.exec_module(HUD)


def unit(**overrides):
    values = {
        "table": HUD.TABLE_LIFE,
        "flags": 0x09,
        "mark": 0x06,
        "number": 1,
        "level": 0,
        "parent": 0xFF,
        "kind": 0,
        "tex_id": 1,
        "vtx_type": 0,
        "blend_type": 0,
        "trans_type": 0,
        "tex_flags": 0,
        "mask_id": 0xFF,
        "pos": (0.0, 0.0, 0.0),
        "size": (8.0, 4.0),
        "rot": (0.0, 0.0, 0.0),
        "col0": bytes((255, 255, 255, 255)),
        "col1": bytes((255, 255, 255, 255)),
    }
    values.update(overrides)
    return HUD.SourceUnit(**values)


class ConvertCoreHudTests(unittest.TestCase):
    def test_composite_uses_gamecube_mask_alpha(self):
        color = HUD.tpl.TplImage(
            8, 4, HUD.tpl.GX_TF_I8, bytes([0xFF]) * 32
        )
        mask = HUD.tpl.TplImage(
            8, 4, HUD.tpl.GX_TF_IA4, bytes([0x83]) * 32
        )
        frames, width, height = HUD._composite_frames((color,), (mask,))
        self.assertEqual((width, height), (8, 4))
        self.assertEqual(frames[0][0], (255, 255, 255, 136))

    def test_slice_keeps_handgun_counter_and_drops_other_bullets(self):
        handgun = unit(table=HUD.TABLE_BULLET, mark=0x31)
        other = unit(table=HUD.TABLE_BULLET, mark=0x32)
        self.assertTrue(HUD.unit_uses_r100_slice_texture(handgun, [handgun]))
        self.assertFalse(HUD.unit_uses_r100_slice_texture(other, [other]))

    def test_slice_drops_children_of_hidden_ashley_root(self):
        ashley = unit(mark=1, number=7)
        child = unit(mark=0x06, number=8, parent=7)
        self.assertFalse(
            HUD.unit_uses_r100_slice_texture(child, [ashley, child])
        )

    def test_power_of_two_padding_has_pvr_limits(self):
        self.assertEqual(HUD._next_power_of_two(1), 8)
        self.assertEqual(HUD._next_power_of_two(129), 256)
        with self.assertRaises(ValueError):
            HUD._next_power_of_two(1025)


if __name__ == "__main__":
    unittest.main()
