"""KFlow — Puerto en Python del motor de layout (HU-05).

Réplica en paridad de `kwin-script/contents/code/script.js` (bspSplit /
applyOuterMargins / computeLayout). Se usa SOLO para pintar la vista previa
interactiva del Control Center; el motor real que mueve ventanas vive en
KWin (JS). Si cambia el algoritmo en script.js, este archivo debe actualizarse
igual para no desincronizar la vista previa del comportamiento real.
"""
import math

DEFAULT_DESKTOP_THRESHOLD = 4


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


def should_create_desktop(window_count, threshold=None):
    limit = threshold or DEFAULT_DESKTOP_THRESHOLD
    return window_count >= limit


def should_remove_desktop(window_count, total_desktops):
    return window_count == 0 and total_desktops > 1
