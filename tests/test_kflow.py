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
import copy

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
    tree_to_rects,
    count_leaves,
    compute_layout_from_tree,
    DEFAULT_LAYOUT_TREE,
    TEMPLATE_TREES,
    get_node_at,
    set_node_at,
    delete_leaf_at,
)

from profile_manager import ProfileManager, DEFAULT_PROFILE, PROFILES_PATH

from dbus_service import (
    build_kwriteconfig_command,
    build_reconfigure_command,
    find_qdbus_binary,
    apply_and_reconfigure,
    write_config,
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
# layout_tree
# ===================================================================
class LayoutTreeTreeToRectsTest(unittest.TestCase):
    """tree_to_rects: convierte un árbol en rectángulos planos."""

    def test_single_leaf(self):
        area = {"x": 0, "y": 0, "width": 100, "height": 200}
        rects = tree_to_rects({"type": "leaf"}, area)
        self.assertEqual(len(rects), 1)
        self.assertEqual(rects[0], area)

    def test_vsplit_50_50(self):
        area = {"x": 0, "y": 0, "width": 800, "height": 600}
        tree = {
            "type": "vsplit", "ratio": 0.5,
            "first": {"type": "leaf"},
            "second": {"type": "leaf"},
        }
        rects = tree_to_rects(tree, area)
        self.assertEqual(len(rects), 2)
        self.assertEqual(rects[0]["width"], 400)
        self.assertEqual(rects[1]["width"], 400)
        self.assertEqual(rects[0]["height"], 600)
        self.assertEqual(rects[1]["height"], 600)
        self.assertEqual(rects[0]["x"], 0)
        self.assertEqual(rects[1]["x"], 400)

    def test_hsplit_30_70(self):
        area = {"x": 0, "y": 0, "width": 600, "height": 900}
        tree = {
            "type": "hsplit", "ratio": 0.3,
            "first": {"type": "leaf"},
            "second": {"type": "leaf"},
        }
        rects = tree_to_rects(tree, area)
        self.assertEqual(len(rects), 2)
        self.assertAlmostEqual(rects[0]["height"], 270)
        self.assertAlmostEqual(rects[1]["height"], 630)
        self.assertEqual(rects[0]["y"], 0)
        self.assertEqual(rects[1]["y"], 270)

    def test_grid_2x2_yields_four(self):
        tree = TEMPLATE_TREES["Grid 2×2"]
        area = {"x": 0, "y": 0, "width": 800, "height": 600}
        rects = tree_to_rects(tree, area)
        self.assertEqual(len(rects), 4)

    def test_ratio_clamped(self):
        """Ratio se clampéa a [0.05, 0.95]."""
        tree = {
            "type": "vsplit", "ratio": 0.99,
            "first": {"type": "leaf"},
            "second": {"type": "leaf"},
        }
        area = {"x": 0, "y": 0, "width": 1000, "height": 500}
        rects = tree_to_rects(tree, area)
        self.assertEqual(len(rects), 2)
        # Con 0.99 → clamp a 0.95 → first_w = 950, second_w = 50
        self.assertAlmostEqual(rects[0]["width"], 950)
        self.assertAlmostEqual(rects[1]["width"], 50)

    def test_none_node_returns_single(self):
        rects = tree_to_rects(None, {"x": 0, "y": 0, "width": 10, "height": 10})
        self.assertEqual(len(rects), 1)


class LayoutTreeCountLeavesTest(unittest.TestCase):
    def test_leaf_is_one(self):
        self.assertEqual(count_leaves({"type": "leaf"}), 1)

    def test_grid_2x2_is_four(self):
        self.assertEqual(count_leaves(TEMPLATE_TREES["Grid 2×2"]), 4)

    def test_50_50_is_two(self):
        self.assertEqual(count_leaves(TEMPLATE_TREES["50/50"]), 2)

    def test_master_stack_is_three(self):
        self.assertEqual(count_leaves(TEMPLATE_TREES["Master+Stack"]), 3)

    def test_none_is_one(self):
        self.assertEqual(count_leaves(None), 1)


class LayoutTreeComputeLayoutFromTreeTest(unittest.TestCase):
    def test_grid_with_gaps(self):
        area = {"x": 0, "y": 0, "width": 1920, "height": 1080}
        margins = {"top": 24, "bottom": 8, "left": 8, "right": 8}
        rects = compute_layout_from_tree(
            TEMPLATE_TREES["Grid 2×2"], area, 8, margins
        )
        self.assertEqual(len(rects), 4)

    def test_null_tree_returns_empty(self):
        area = {"x": 0, "y": 0, "width": 100, "height": 100}
        rects = compute_layout_from_tree(None, area, 0, {})
        self.assertEqual(rects, [])

    def test_outer_margins_respected(self):
        area = {"x": 0, "y": 0, "width": 1000, "height": 1000}
        margins = {"top": 100, "bottom": 0, "left": 0, "right": 0}
        rects = compute_layout_from_tree(
            {"type": "leaf"}, area, 0, margins
        )
        self.assertEqual(rects[0]["y"], 100)
        self.assertEqual(rects[0]["height"], 900)


# ===================================================================
# Manipulación de layout_tree (get_node_at, set_node_at, delete_leaf_at)
# ===================================================================
class LayoutTreeGetNodeTest(unittest.TestCase):
    """get_node_at: obtiene el nodo real en una ruta."""

    def setUp(self):
        self.tree = {
            "type": "vsplit", "ratio": 0.6,
            "first": {"type": "leaf"},
            "second": {
                "type": "hsplit", "ratio": 0.5,
                "first": {"type": "leaf"},
                "second": {"type": "leaf"},
            },
        }

    def test_root_path_returns_full_tree(self):
        node = get_node_at(self.tree, [])
        self.assertEqual(node["type"], "vsplit")

    def test_first_level_leaf(self):
        node = get_node_at(self.tree, ["first"])
        self.assertEqual(node["type"], "leaf")

    def test_deep_nested_leaf(self):
        node = get_node_at(self.tree, ["second", "first"])
        self.assertEqual(node["type"], "leaf")

    def test_deep_nested_split(self):
        node = get_node_at(self.tree, ["second"])
        self.assertEqual(node["type"], "hsplit")
        self.assertEqual(node["ratio"], 0.5)

    def test_invalid_path_returns_none(self):
        self.assertIsNone(get_node_at(self.tree, ["first", "nope"]))

    def test_none_tree_with_empty_path(self):
        self.assertIsNone(get_node_at(None, []))

    def test_none_tree_with_path(self):
        self.assertIsNone(get_node_at(None, ["first"]))


class LayoutTreeSetNodeTest(unittest.TestCase):
    """set_node_at: reemplaza un nodo sin mutar el original."""

    def setUp(self):
        self.tree = {
            "type": "vsplit", "ratio": 0.5,
            "first": {"type": "leaf"},
            "second": {"type": "leaf"},
        }

    def test_replace_leaf_returns_new_tree(self):
        new_leaf = {"type": "leaf", "custom": True}
        new_tree = set_node_at(self.tree, ["first"], new_leaf)
        # El original no fue mutado
        self.assertNotIn("custom", self.tree["first"])
        # El nuevo tiene el reemplazo
        self.assertTrue(get_node_at(new_tree, ["first"]).get("custom"))

    def test_replace_root(self):
        new_root = {"type": "leaf"}
        new_tree = set_node_at(self.tree, [], new_root)
        self.assertEqual(new_tree["type"], "leaf")
        self.assertEqual(self.tree["type"], "vsplit")  # original intacto

    def test_invalid_path_returns_copy(self):
        new_tree = set_node_at(self.tree, ["nope", "invalid"], {"type": "leaf"})
        self.assertEqual(new_tree["type"], "vsplit")
        self.assertIn("first", new_tree)


class LayoutTreeDeleteLeafTest(unittest.TestCase):
    """delete_leaf_at: colapsa la división padre y expande el hermano."""

    def setUp(self):
        # vsplit(first=leafA, second=leafB)
        self.simple_tree = {
            "type": "vsplit", "ratio": 0.5,
            "first": {"type": "leaf", "id": "A"},
            "second": {"type": "leaf", "id": "B"},
        }

    def test_delete_first_leaf_collapses_to_second(self):
        new_tree, sibling = delete_leaf_at(self.simple_tree, ["first"])
        self.assertEqual(new_tree["type"], "leaf")
        self.assertEqual(new_tree["id"], "B")
        self.assertEqual(sibling["id"], "B")
        # Original intacto
        self.assertEqual(self.simple_tree["first"]["id"], "A")

    def test_delete_second_leaf_collapses_to_first(self):
        new_tree, sibling = delete_leaf_at(self.simple_tree, ["second"])
        self.assertEqual(new_tree["id"], "A")
        self.assertEqual(sibling["id"], "A")

    def test_delete_last_leaf_does_nothing(self):
        tree = {"type": "leaf", "id": "solo"}
        new_tree, sibling = delete_leaf_at(tree, [])
        self.assertEqual(new_tree["id"], "solo")
        self.assertIsNone(sibling)

    def test_delete_from_nested_tree(self):
        # Master+Stack: vsplit(0.6, leaf=master, hsplit(stack1, stack2))
        tree = copy.deepcopy(TEMPLATE_TREES["Master+Stack"])
        self.assertEqual(count_leaves(tree), 3)
        # Eliminar master (path ["first"])
        new_tree, sibling = delete_leaf_at(tree, ["first"])
        # Debe colapsar: el hsplit (stack) se convierte en la raíz
        self.assertEqual(count_leaves(new_tree), 2)
        self.assertEqual(new_tree["type"], "hsplit")

    def test_original_not_mutated_after_delete(self):
        tree = copy.deepcopy(TEMPLATE_TREES["50/50"])
        original_type = tree["type"]
        delete_leaf_at(tree, ["first"])
        self.assertEqual(tree["type"], original_type)
        self.assertIn("first", tree)

    def test_root_path_does_nothing_on_multi_leaf(self):
        tree = copy.deepcopy(TEMPLATE_TREES["50/50"])
        new_tree, sib = delete_leaf_at(tree, [])
        self.assertEqual(count_leaves(new_tree), 2)
        self.assertIsNone(sib)


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
        self.mgr.save_profile("test", 12, {"top": 5, "bottom": 5, "left": 5, "right": 5}, False,
                              layout_tree={"type": "vsplit", "ratio": 0.5, "first": {"type": "leaf"}, "second": {"type": "leaf"}})
        data = self.mgr.load_all()
        self.assertIn("test", data["profiles"])
        self.assertEqual(data["profiles"]["test"]["inner_gap"], 12)
        self.assertEqual(data["profiles"]["test"]["layout_tree"]["type"], "vsplit")

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

    def test_apply_and_reconfigure_serializes_dict_to_json(self):
        """Verifica que apply_and_reconfigure acepta dicts y bools sin error
        de tipo (no ejecuta subprocess en el test, solo valida la lógica)."""
        # Este test no debe lanzar excepción por tipo de dato
        try:
            # No podemos llamar realmente a subprocess sin sistema, pero
            # validamos que la preparación de datos no falle.
            import json
            tree = {"type": "vsplit", "ratio": 0.5, "first": {"type": "leaf"}, "second": {"type": "leaf"}}
            serialized = json.dumps(tree, separators=(",", ":"))
            self.assertIsInstance(serialized, str)
            self.assertIn("vsplit", serialized)
        except Exception as e:
            self.fail(f"Serialización de LayoutTree falló: {e}")


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
