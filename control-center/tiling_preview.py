"""KFlow — Puerto en Python del motor de layout (HU-05).

Réplica en paridad de `kwin-script/contents/code/script.js` (bspSplit /
applyOuterMargins / computeLayout / applyLayoutTree). Se usa SOLO para pintar
la vista previa interactiva del Control Center; el motor real que mueve
ventanas vive en KWin (JS). Si cambia el algoritmo en script.js, este archivo
debe actualizarse igual para no desincronizar la vista previa del
comportamiento real.
"""
import math

DEFAULT_DESKTOP_THRESHOLD = 4

# ---------------------------------------------------------------------------
# Plantillas predefinidas de layout_tree (HU-05 editor visual)
# Cada template es un árbol binario que el preview y el motor KWin saben
# interpretar:
#   {"type": "leaf"}
#   {"type": "vsplit"|"hsplit", "ratio": 0.5, "first": <node>, "second": <node>}
# ---------------------------------------------------------------------------
DEFAULT_LAYOUT_TREE = {"type": "leaf"}

TEMPLATE_TREES = {
    "Grid 2×2": {
        "type": "hsplit",
        "ratio": 0.5,
        "first": {
            "type": "vsplit",
            "ratio": 0.5,
            "first": {"type": "leaf"},
            "second": {"type": "leaf"},
        },
        "second": {
            "type": "vsplit",
            "ratio": 0.5,
            "first": {"type": "leaf"},
            "second": {"type": "leaf"},
        },
    },
    "Master+Stack": {
        "type": "vsplit",
        "ratio": 0.6,
        "first": {"type": "leaf"},
        "second": {
            "type": "hsplit",
            "ratio": 0.5,
            "first": {"type": "leaf"},
            "second": {"type": "leaf"},
        },
    },
    "50/50": {
        "type": "vsplit",
        "ratio": 0.5,
        "first": {"type": "leaf"},
        "second": {"type": "leaf"},
    },
    "Columns": {
        "type": "hsplit",
        "ratio": 1.0 / 3.0,
        "first": {"type": "leaf"},
        "second": {
            "type": "hsplit",
            "ratio": 0.5,
            "first": {"type": "leaf"},
            "second": {"type": "leaf"},
        },
    },
}


def apply_outer_margins(area, margins):
    top = margins.get("top", 0)
    bottom = margins.get("bottom", 0)
    left = margins.get("left", 0)
    right = margins.get("right", 0)

    width = area["width"] - left - right
    height = area["height"] - top - bottom

    return {
        "x": area["x"] + left,
        "y": area["y"] + top,
        "width": max(width, 0),
        "height": max(height, 0),
    }


def bsp_split(x, y, w, h, count, gap):
    if count <= 0:
        return []
    if count == 1:
        return [{"x": x, "y": y, "width": w, "height": h}]

    first_count = math.ceil(count / 2)
    second_count = count - first_count
    split_ratio = first_count / count

    if w >= h:
        first_width = max(0, math.floor((w - gap) * split_ratio))
        second_width = max(0, w - gap - first_width)
        left = bsp_split(x, y, first_width, h, first_count, gap)
        right = bsp_split(x + first_width + gap, y, second_width, h, second_count, gap)
        return left + right

    first_height = max(0, math.floor((h - gap) * split_ratio))
    second_height = max(0, h - gap - first_height)
    top = bsp_split(x, y, w, first_height, first_count, gap)
    bottom = bsp_split(x, y + first_height + gap, w, second_height, second_count, gap)
    return top + bottom


def compute_layout(screen_area, inner_gap, outer_margins, window_count):
    usable = apply_outer_margins(screen_area, outer_margins)
    if window_count <= 0:
        return []
    return bsp_split(usable["x"], usable["y"], usable["width"], usable["height"], window_count, inner_gap or 0)


def tree_to_rects(node, area):
    """Convierte un layout_tree en una lista plana de rectángulos (orden de
    lectura en profundidad, izquierda/arriba primero). Las hojas producen un
    solo rect; los nodos internos particionan recursivamente."""
    if node is None or node.get("type") == "leaf":
        return [dict(area)]

    split_type = node.get("type", "vsplit")
    ratio = max(0.05, min(0.95, node.get("ratio", 0.5)))

    if split_type == "vsplit":
        first_w = area["width"] * ratio
        second_w = area["width"] - first_w
        first_area = dict(area, width=first_w)
        second_area = dict(area, x=area["x"] + first_w, width=second_w)
    else:  # hsplit
        first_h = area["height"] * ratio
        second_h = area["height"] - first_h
        first_area = dict(area, height=first_h)
        second_area = dict(area, y=area["y"] + first_h, height=second_h)

    return tree_to_rects(node.get("first"), first_area) + tree_to_rects(
        node.get("second"), second_area
    )


def count_leaves(node):
    """Devuelve el número de hojas (ventanas) en un layout_tree."""
    if node is None or node.get("type") == "leaf":
        return 1
    return count_leaves(node.get("first")) + count_leaves(node.get("second"))


def compute_layout_from_tree(node, screen_area, inner_gap, outer_margins):
    """Aplica un layout_tree personalizado sobre el área usable, con márgenes
    y gap interno entre las celdas. Si el nodo es None o no tiene 'type',
    retorna [] para que el caller caiga en BSP automático."""
    if node is None or not isinstance(node, dict) or "type" not in node:
        return []
    usable = apply_outer_margins(screen_area, outer_margins)
    rects = tree_to_rects(node, usable)

    # Aplicar inner_gap encogiendo cada rect (sin desplazar — el gap se
    # descuenta del tamaño, igual que en bsp_split).
    gap = inner_gap or 0
    if gap > 0 and len(rects) > 1:
        # Estrategia: encogemos desde los bordes internos. La más sencilla y
        # consistente con BSP es reducir cada rect en gap/2 en cada eje.
        half = gap / 2.0
        for r in rects:
            r["x"] += half
            r["y"] += half
            r["width"] = max(0, r["width"] - gap)
            r["height"] = max(0, r["height"] - gap)

    return rects


def should_create_desktop(window_count, threshold=None):
    limit = threshold or DEFAULT_DESKTOP_THRESHOLD
    return window_count >= limit


def should_remove_desktop(window_count, total_desktops):
    return window_count == 0 and total_desktops > 1
