#!/usr/bin/env python3
"""KFlow — Suite de pruebas unitarias (HU-07).

Cubre:
  - tiling_preview: compute_layout, bsp_split, apply_outer_margins,
    should_create_desktop, should_remove_desktop.
  - profile_manager: CRUD, perfil default inmutable, activo.
  - dbus_service: funciones helpers (kwriteconfig, reconfigure) sin depender
    de PyQt6/QtDBus.
"""

import json
import os
import sys
import tempfile
import unittest

# ---------------------------------------------------------------------------
# Asegurar que control-center/ está en sys.path para importar sus módulos
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CC_DIR = os.path.join(_PROJECT_ROOT, "control-center")
if _CC_DIR not in sys.path:
    sys.path.insert(0, _CC_DIR)

# ---------------------------------------------------------------------------
# Módulos bajo prueba
# ---------------------------------------------------------------------------
from tiling_preview import (
    apply_outer_margins,
    bsp_split,
    compute_layout,
    should_create_desktop,
    should_remove_desktop,
)

from profile_manager import ProfileManager, DEFAULT_PROFILE, PROFILES_PATH

from dbus_service import (
    build_kwriteconfig_command,
    build_reconfigure_command,
    find_qdbus_binary,
)


# ===================================================================
# tiling_preview
# ===================================================================
class TilingPreviewApplyMarginsTest(unittest.TestCase):
    """apply_outer_margins: reduce el área usable según márgenes."""

    def test_no_margins(self):
        area = {"x": 0, "y": 0, "width": 1920, "height": 1080}
        result = apply_outer_margins(area, {})
        self.assertEqual(result, area)

    def test_uniform_margins(self):
        area = {"x": 0, "y": 0, "width": 1920, "height": 1080}
        result = apply_outer_margins(area, {"top": 10, "bottom": 10, "left": 10, "right": 10})
        self.assertEqual(result["x"], 10)
        self.assertEqual(result["y"], 10)
        self.assertEqual(result["width"], 1900)
        self.assertEqual(result["height"], 1060)

    def test_asymmetric_margins(self):
        area = {"x": 100, "y": 100, "width": 1000, "height": 800}
        result = apply_outer_margins(area, {"top": 24, "bottom": 8, "left": 16, "right": 4})
        self.assertEqual(result["x"], 116)
        self.assertEqual(result["y"], 124)
        self.assertEqual(result["width"], 980)
        self.assertEqual(result["height"], 768)

    def test_excessive_margins_clamp_to_zero(self):
        area = {"x": 0, "y": 0, "width": 10, "height": 10}
        result = apply_outer_margins(area, {"top": 0, "bottom": 0, "left": 6, "right": 6})
        self.assertEqual(result["width"], 0)
        self.assertEqual(result["height"], 10)


class TilingPreviewBSPSplitTest(unittest.TestCase):
    """bsp_split: partición recursiva balanceada con gap."""

    def test_zero_count(self):
        self.assertEqual(bsp_split(0, 0, 100, 100, 0, 8), [])

    def test_one_window(self):
        result = bsp_split(10, 20, 200, 300, 1, 8)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], {"x": 10, "y": 20, "width": 200, "height": 300})

    def test_two_windows_horizontal(self):
        """Ancho >= alto → split vertical (izquierda/derecha)."""
        result = bsp_split(0, 0, 800, 600, 2, 0)
        self.assertEqual(len(result), 2)
        # Cada ventana tiene ancho 400, altura 600
        self.assertEqual(result[0]["width"] + result[1]["width"], 800)
        self.assertEqual(result[0]["height"], 600)
        self.assertEqual(result[1]["height"], 600)

    def test_two_windows_vertical(self):
        """Alto > ancho → split horizontal (arriba/abajo)."""
        result = bsp_split(0, 0, 600, 800, 2, 0)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["height"] + result[1]["height"], 800)
        self.assertEqual(result[0]["width"], 600)
        self.assertEqual(result[1]["width"], 600)

    def test_gap_subtracts_space(self):
        """Con gap > 0, la suma de anchos/alto es menor."""
        result = bsp_split(0, 0, 800, 600, 2, 20)
        total_w = result[0]["width"] + result[1]["width"]
        self.assertEqual(total_w, 780)  # 800 - 20

    def test_no_overlap(self):
        """Ningún par de rectángulos se solapa."""
        for n in range(3, 8):
            rects = bsp_split(0, 0, 1920, 1080, n, 8)
            for i, r1 in enumerate(rects):
                for j, r2 in enumerate(rects):
                    if i >= j:
                        continue
                    # r1 a la izquierda o arriba de r2, o viceversa
                    no_overlap_x = (
                        r1["x"] + r1["width"] <= r2["x"]
                        or r2["x"] + r2["width"] <= r1["x"]
                    )
                    no_overlap_y = (
                        r1["y"] + r1["height"] <= r2["y"]
                        or r2["y"] + r2["height"] <= r1["y"]
                    )
                    self.assertTrue(
                        no_overlap_x or no_overlap_y,
                        f"Overlap con n={n}: {r1} vs {r2}",
                    )


class TilingPreviewComputeLayoutTest(unittest.TestCase):
    """compute_layout: integración de apply_outer_margins + bsp_split."""

    def test_basic(self):
        area = {"x": 0, "y": 0, "width": 1920, "height": 1080}
        rects = compute_layout(area, 8, {"top": 24, "bottom": 8, "left": 8, "right": 8}, 3)
        self.assertEqual(len(rects), 3)
        for r in rects:
            self.assertGreaterEqual(r["width"], 0)
            self.assertGreaterEqual(r["height"], 0)

    def test_no_windows(self):
        area = {"x": 0, "y": 0, "width": 100, "height": 100}
        self.assertEqual(compute_layout(area, 0, {}, 0), [])

    def test_outer_margins_respected(self):
        area = {"x": 0, "y": 0, "width": 1000, "height": 1000}
        margins = {"top": 100, "bottom": 0, "left": 0, "right": 0}
        rects = compute_layout(area, 0, margins, 1)
        self.assertEqual(rects[0]["y"], 100)
        self.assertEqual(rects[0]["height"], 900)


class TilingPreviewDesktopRulesTest(unittest.TestCase):
    """should_create_desktop / should_remove_desktop."""

    def test_create_below_threshold(self):
        self.assertFalse(should_create_desktop(3))
        self.assertFalse(should_create_desktop(0))

    def test_create_at_threshold(self):
        self.assertTrue(should_create_desktop(4))
        self.assertTrue(should_create_desktop(5))
        self.assertTrue(should_create_desktop(10))

    def test_custom_threshold(self):
        self.assertFalse(should_create_desktop(2, threshold=3))
        self.assertTrue(should_create_desktop(3, threshold=3))

    def test_remove_only_if_empty_and_not_last(self):
        self.assertTrue(should_remove_desktop(0, 2))
        self.assertFalse(should_remove_desktop(0, 1))
        self.assertFalse(should_remove_desktop(1, 2))
        self.assertFalse(should_remove_desktop(2, 5))


# ===================================================================
# profile_manager
# ===================================================================
class ProfileManagerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.tmp.close()
        self.mgr = ProfileManager(path=self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_load_empty_creates_default(self):
        data = self.mgr.load_all()
        self.assertIn("profiles", data)
        self.assertIn("default", data["profiles"])
        self.assertEqual(data["active"], "default")
        self.assertEqual(data["profiles"]["default"]["inner_gap"], 8)

    def test_save_and_reload(self):
        self.mgr.save_profile("test", 12, {"top": 5, "bottom": 5, "left": 5, "right": 5}, False)
        data = self.mgr.load_all()
        self.assertIn("test", data["profiles"])
        self.assertEqual(data["profiles"]["test"]["inner_gap"], 12)

    def test_list_names(self):
        self.mgr.save_profile("a", 1, {}, True)
        self.mgr.save_profile("b", 2, {}, False)
        names = self.mgr.list_names()
        self.assertIn("default", names)
        self.assertIn("a", names)
        self.assertIn("b", names)

    def test_delete_profile(self):
        self.mgr.save_profile("x", 5, {}, True)
        self.mgr.delete_profile("x")
        self.assertNotIn("x", self.mgr.list_names())

    def test_delete_default_raises(self):
        with self.assertRaises(ValueError):
            self.mgr.delete_profile("default")

    def test_delete_active_falls_back_to_default(self):
        self.mgr.save_profile("active1", 10, {}, True)
        self.mgr.set_active("active1")
        self.mgr.delete_profile("active1")
        data = self.mgr.load_all()
        self.assertEqual(data["active"], "default")

    def test_set_active(self):
        self.mgr.save_profile("p1", 3, {}, True)
        self.mgr.set_active("p1")
        self.assertEqual(self.mgr.load_all()["active"], "p1")

    def test_get_profile(self):
        self.mgr.save_profile("getme", 7, {"top": 1, "bottom": 2, "left": 3, "right": 4}, True)
        p = self.mgr.get_profile("getme")
        self.assertEqual(p["inner_gap"], 7)
        self.assertEqual(p["outer_margins"]["left"], 3)

    def test_get_nonexistent_profile(self):
        self.assertIsNone(self.mgr.get_profile("no_existe"))

    def test_load_corrupt_file_returns_default(self):
        """Archivo JSON inválido → estructura default sin lanzar excepción."""
        with open(self.tmp.name, "w", encoding="utf-8") as f:
            f.write("esto no es json{{{")
        data = self.mgr.load_all()
        self.assertEqual(data["active"], "default")
        self.assertIn("default", data["profiles"])
        self.assertEqual(data["profiles"]["default"]["inner_gap"], 8)

    def test_load_empty_file_returns_default(self):
        """Archivo vacío → estructura default sin lanzar excepción."""
        with open(self.tmp.name, "w", encoding="utf-8") as f:
            f.write("")
        data = self.mgr.load_all()
        self.assertEqual(data["active"], "default")
        self.assertIn("default", data["profiles"])


# ===================================================================
# dbus_service helpers (no requieren PyQt6)
# ===================================================================
class DBusServiceHelpersTest(unittest.TestCase):
    def test_build_kwriteconfig_command(self):
        cmd = build_kwriteconfig_command("InnerGap", 12)
        self.assertEqual(cmd[0], "kwriteconfig6")
        self.assertIn("--file", cmd)
        self.assertIn("kwinrc", cmd)
        self.assertIn("--group", cmd)
        self.assertIn("Script-kflow", cmd)
        self.assertIn("--key", cmd)
        self.assertIn("InnerGap", cmd)
        self.assertIn("12", cmd)

    def test_build_kwriteconfig_boolean_value(self):
        cmd = build_kwriteconfig_command("AutoTilingEnabled", "true")
        self.assertIn("true", cmd)

    def test_build_reconfigure_command(self):
        cmd = build_reconfigure_command(qdbus_bin="qdbus")
        self.assertEqual(cmd[0], "qdbus")
        self.assertEqual(cmd[1], "org.kde.KWin")
        self.assertEqual(cmd[2], "/KWin")
        self.assertEqual(cmd[3], "org.kde.KWin.reconfigure")

    def test_find_qdbus_binary_returns_string_or_none(self):
        result = find_qdbus_binary()
        self.assertTrue(result is None or isinstance(result, str))


# ===================================================================
# Sintaxis JS del motor KWin (verificación de que script.js es válido)
# ===================================================================
class KWinScriptSyntaxTest(unittest.TestCase):
    def test_script_js_exists_and_non_empty(self):
        script_path = os.path.join(
            _PROJECT_ROOT, "kwin-script", "contents", "code", "script.js"
        )
        self.assertTrue(os.path.isfile(script_path), f"No existe {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn(".pragma library", content)
        self.assertGreater(len(content), 100)


if __name__ == "__main__":
    unittest.main()
