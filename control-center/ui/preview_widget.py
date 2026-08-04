"""KFlow — Widget de vista previa interactiva convertido en editor visual de
mosaicos (HU-05). Permite hacer clic para seleccionar recuadros, dividirlos,
eliminarlos, arrastrar divisores y cargar plantillas predefinidas. El árbol
de layout resultante se persiste en profiles.json como 'layout_tree'.
"""
import copy
import json
import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QCursor
from PyQt6.QtWidgets import QWidget

from tiling_preview import (
    DEFAULT_LAYOUT_TREE,
    TEMPLATE_TREES,
    compute_layout_from_tree,
    tree_to_rects,
    count_leaves,
)

ACCENT_COLORS = [
    "#3DAEE9", "#27AE60", "#E67E22", "#9B59B6",
    "#E74C3C", "#1ABC9C", "#F1C40F", "#95A5A6",
    "#EC407A", "#7F8C8D", "#2ECC71", "#5DADE2",
]

VIRTUAL_SCREEN_SIZE = (1920, 1080)

# Umbral en píxeles para considerar "cerca de un divisor" (arrastre)
DIVIDER_GRAB = 10


class TilingPreviewWidget(QWidget):
    """Editor visual interactivo de layout_tree.

    Señales:
      layoutChanged(): emitida cada vez que el árbol se modifica (split,
                       delete, reset, drag).
    """

    layoutChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 200)
        self.setMouseTracking(True)

        self._inner_gap = 8
        self._outer_margins = {"top": 24, "bottom": 8, "left": 8, "right": 8}

        # Árbol de layout actual
        self._layout_tree = copy.deepcopy(DEFAULT_LAYOUT_TREE)

        # Ruta hasta el nodo seleccionado (lista de "first"|"second")
        self._selected_path = []

        # Ruta hasta el nodo bajo el cursor (None = ninguno)
        self._hover_path = None

        # --- Arrastre de divisores ---
        self._dragging = False
        self._drag_node_path = None   # ruta al nodo PADRE cuyo ratio se ajusta
        self._drag_axis = None         # "v" o "h"
        self._drag_start_ratio = 0.5
        self._drag_start_pos = 0

        # Cache de la última geometría pintada (rects + paths) para hit testing
        self._cached_rects = []
        self._cached_paths = []

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def set_inner_gap(self, value):
        self._inner_gap = value
        self.update()

    def set_outer_margins(self, top, bottom, left, right):
        self._outer_margins = {"top": top, "bottom": bottom, "left": left, "right": right}
        self.update()

    def layout_tree(self):
        """Devuelve una copia profunda del árbol actual (para serializar)."""
        return copy.deepcopy(self._layout_tree)

    def set_layout_tree(self, tree):
        """Carga un árbol externo (p.ej. desde un perfil)."""
        if tree and isinstance(tree, dict) and "type" in tree:
            self._layout_tree = copy.deepcopy(tree)
        else:
            self._layout_tree = copy.deepcopy(DEFAULT_LAYOUT_TREE)
        self._selected_path = []
        self._hover_path = None
        self.update()
        self.layoutChanged.emit()

    def leaf_count(self):
        return count_leaves(self._layout_tree)

    # --- Acciones del editor ---

    def split_vertical(self):
        """Divide el recuadro seleccionado en 2 columnas (vsplit)."""
        self._split_selected("vsplit")

    def split_horizontal(self):
        """Divide el recuadro seleccionado en 2 filas (hsplit)."""
        self._split_selected("hsplit")

    def _split_selected(self, split_type):
        node, _ = self._resolve_path(self._selected_path)
        if node is None or node.get("type") != "leaf":
            return
        node["type"] = split_type
        node["ratio"] = 0.5
        node["first"] = {"type": "leaf"}
        node["second"] = {"type": "leaf"}
        # Seleccionar la primera mitad
        self._selected_path = self._selected_path + ["first"]
        self.update()
        self.layoutChanged.emit()

    def delete_selected(self):
        """Elimina el recuadro seleccionado y expande su hermano. No permite
        eliminar el último recuadro (debe quedar al menos una hoja)."""
        if count_leaves(self._layout_tree) <= 1:
            return
        if not self._selected_path:
            return
        # El padre es la ruta sin el último elemento
        parent_path = self._selected_path[:-1]
        sibling_key = "second" if self._selected_path[-1] == "first" else "first"
        sibling_path = parent_path + [sibling_key]

        parent, _ = self._resolve_path(parent_path)
        sibling_node, _ = self._resolve_path(sibling_path)
        if parent is None or sibling_node is None:
            return

        # Reemplazar el padre con el hermano (colapsar el split)
        if parent_path:
            grandparent, last_key = self._resolve_path(parent_path[:-1])
            grandparent[last_key] = sibling_node
        else:
            # El padre es la raíz
            self._layout_tree = sibling_node

        self._selected_path = parent_path[:-1] if parent_path else []
        self.update()
        self.layoutChanged.emit()

    def reset_to_template(self, template_name):
        """Carga una plantilla predefinida por nombre (Grid 2x2, Master+Stack,
        50/50, Columns)."""
        tree = TEMPLATE_TREES.get(template_name)
        if tree:
            self._layout_tree = copy.deepcopy(tree)
            self._selected_path = []
            self._hover_path = None
            self.update()
            self.layoutChanged.emit()

    # ------------------------------------------------------------------
    # Navegación del árbol
    # ------------------------------------------------------------------
    def _resolve_path(self, path):
        """Devuelve (nodo, clave_en_padre) para una ruta. path=[] = raíz."""
        if not path:
            return self._layout_tree, None
        node = self._layout_tree
        for i, key in enumerate(path):
            if not isinstance(node, dict) or key not in node:
                return None, None
            if i == len(path) - 1:
                return node, key
            node = node[key]
        return node, None

    # ------------------------------------------------------------------
    # Geometría → píxeles
    # ------------------------------------------------------------------
    def _screen_to_widget_scale(self):
        """Factores de escala y offsets para mapear coord virtuales → widget."""
        virtual_w, virtual_h = VIRTUAL_SCREEN_SIZE
        scale = min(self.width() / virtual_w, self.height() / virtual_h)
        offset_x = (self.width() - virtual_w * scale) / 2
        offset_y = (self.height() - virtual_h * scale) / 2
        return scale, offset_x, offset_y

    def _compute_rects_and_paths(self):
        """Devuelve (rects_en_píxeles, paths) para cada hoja en el árbol."""
        scale, ox, oy = self._screen_to_widget_scale()
        screen_area = {"x": 0, "y": 0, "width": VIRTUAL_SCREEN_SIZE[0], "height": VIRTUAL_SCREEN_SIZE[1]}
        rects = compute_layout_from_tree(
            self._layout_tree, screen_area, self._inner_gap, self._outer_margins
        )

        # Obtener paths de hojas en orden DFS
        leaf_paths = self._leaf_paths(self._layout_tree, [])

        pixel_rects = []
        for r in rects:
            pixel_rects.append({
                "x": ox + r["x"] * scale,
                "y": oy + r["y"] * scale,
                "width": max(0, r["width"] * scale - 1),
                "height": max(0, r["height"] * scale - 1),
            })
        return pixel_rects, leaf_paths[:len(pixel_rects)]

    def _leaf_paths(self, node, base_path):
        """Lista de rutas a cada hoja en orden DFS."""
        if node is None or node.get("type") == "leaf":
            return [list(base_path)]
        result = []
        result.extend(self._leaf_paths(node.get("first"), base_path + ["first"]))
        result.extend(self._leaf_paths(node.get("second"), base_path + ["second"]))
        return result

    def _dividers_from_tree(self, node, area, base_path):
        """Genera los divisores (rectas) entre hermanos para arrastre.

        Cada divisor es un dict:
          {"x1", "y1", "x2", "y2", "path": ruta_al_padre, "axis": "v"|"h"}
        """
        if node is None or node.get("type") == "leaf":
            return []
        dividers = []
        ratio = node.get("ratio", 0.5)
        if node.get("type") == "vsplit":
            # Línea vertical en x = area.x + area.width * ratio
            div_x = area["x"] + area["width"] * ratio
            dividers.append({
                "x1": div_x, "y1": area["y"],
                "x2": div_x, "y2": area["y"] + area["height"],
                "path": list(base_path),
                "axis": "v",
            })
            first_area = dict(area, width=area["width"] * ratio)
            second_area = dict(area, x=area["x"] + area["width"] * ratio,
                               width=area["width"] * (1 - ratio))
        else:
            div_y = area["y"] + area["height"] * ratio
            dividers.append({
                "x1": area["x"], "y1": div_y,
                "x2": area["x"] + area["width"], "y2": div_y,
                "path": list(base_path),
                "axis": "h",
            })
            first_area = dict(area, height=area["height"] * ratio)
            second_area = dict(area, y=area["y"] + area["height"] * ratio,
                               height=area["height"] * (1 - ratio))

        dividers.extend(self._dividers_from_tree(node.get("first"), first_area,
                                                  base_path + ["first"]))
        dividers.extend(self._dividers_from_tree(node.get("second"), second_area,
                                                  base_path + ["second"]))
        return dividers

    def _compute_dividers(self):
        """Dividers mapeados a coordenadas de widget."""
        scale, ox, oy = self._screen_to_widget_scale()
        screen_area = {"x": 0, "y": 0, "width": VIRTUAL_SCREEN_SIZE[0], "height": VIRTUAL_SCREEN_SIZE[1]}
        raw = self._dividers_from_tree(self._layout_tree, screen_area, [])
        result = []
        for d in raw:
            result.append({
                "x1": ox + d["x1"] * scale,
                "y1": oy + d["y1"] * scale,
                "x2": ox + d["x2"] * scale,
                "y2": oy + d["y2"] * scale,
                "path": d["path"],
                "axis": d["axis"],
            })
        return result

    # ------------------------------------------------------------------
    # Hit testing
    # ------------------------------------------------------------------
    def _tile_at(self, wx, wy):
        """Devuelve la ruta a la hoja bajo (wx, wy) o None."""
        for i, r in enumerate(self._cached_rects):
            if (r["x"] <= wx <= r["x"] + r["width"] and
                    r["y"] <= wy <= r["y"] + r["height"]):
                if i < len(self._cached_paths):
                    return list(self._cached_paths[i])
        return None

    def _divider_near(self, wx, wy):
        """Devuelve el divisor más cercano si está a <= DIVIDER_GRAB px, o None."""
        best = None
        best_dist = DIVIDER_GRAB + 1
        for d in self._compute_dividers():
            # Distancia punto → segmento (simplificada: bounding box + perpendicular)
            # Para divisores verticales: |wx - d.x1| < DIVIDER_GRAB y wy entre y1,y2
            if d["axis"] == "v":
                if d["y1"] <= wy <= d["y2"]:
                    dist = abs(wx - d["x1"])
                    if dist < best_dist:
                        best_dist = dist
                        best = d
            else:
                if d["x1"] <= wx <= d["x2"]:
                    dist = abs(wy - d["y1"])
                    if dist < best_dist:
                        best_dist = dist
                        best = d
        return best

    # ------------------------------------------------------------------
    # Eventos del mouse
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        wx, wy = event.position().x(), event.position().y()

        # ¿Cerca de un divisor?
        divider = self._divider_near(wx, wy)
        if divider:
            self._dragging = True
            self._drag_node_path = divider["path"]
            self._drag_axis = divider["axis"]
            node, _ = self._resolve_path(divider["path"])
            self._drag_start_ratio = node.get("ratio", 0.5) if node else 0.5
            self._drag_start_pos = wx if divider["axis"] == "v" else wy
            self.setCursor(
                Qt.CursorShape.SizeHorCursor if divider["axis"] == "v"
                else Qt.CursorShape.SizeVerCursor
            )
            return

        # Seleccionar recuadro
        path = self._tile_at(wx, wy)
        if path is not None:
            self._selected_path = path
            self.update()

    def mouseMoveEvent(self, event):
        wx, wy = event.position().x(), event.position().y()

        if self._dragging:
            self._update_drag(wx, wy)
            return

        # Actualizar cursor y hover
        divider = self._divider_near(wx, wy)
        if divider:
            self.setCursor(
                Qt.CursorShape.SizeHorCursor if divider["axis"] == "v"
                else Qt.CursorShape.SizeVerCursor
            )
            self._hover_path = None
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            path = self._tile_at(wx, wy)
            if path != self._hover_path:
                self._hover_path = path
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._drag_node_path = None
            self._drag_axis = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()
            self.layoutChanged.emit()

    def leaveEvent(self, event):
        self._hover_path = None
        self.update()

    def _update_drag(self, wx, wy):
        """Ajusta el ratio del nodo padre durante el arrastre."""
        if not self._drag_node_path:
            return
        node, _ = self._resolve_path(self._drag_node_path)
        if not node:
            return

        scale, ox, oy = self._screen_to_widget_scale()
        virtual_w, virtual_h = VIRTUAL_SCREEN_SIZE

        if self._drag_axis == "v":
            # Convertir wx a coordenada virtual y calcular ratio
            virt_x = (wx - ox) / scale if scale > 0 else 0
            # Clamp al área virtual
            total_w = virtual_w
            ratio = max(0.05, min(0.95, virt_x / total_w if total_w > 0 else 0.5))
        else:
            virt_y = (wy - oy) / scale if scale > 0 else 0
            total_h = virtual_h
            ratio = max(0.05, min(0.95, virt_y / total_h if total_h > 0 else 0.5))

        node["ratio"] = round(ratio, 4)
        self.update()

    # ------------------------------------------------------------------
    # Pintado
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1B1E20"))

        # Recalcular geometría
        self._cached_rects, self._cached_paths = self._compute_rects_and_paths()

        for i, r in enumerate(self._cached_rects):
            path = self._cached_paths[i] if i < len(self._cached_paths) else []
            is_selected = path == self._selected_path
            is_hovered = path == self._hover_path

            color = QColor(ACCENT_COLORS[i % len(ACCENT_COLORS)])

            if is_selected:
                # Borde brillante + glow
                pen = QPen(QColor("#FFFFFF"), 3)
                brush = QBrush(color.darker(180))
            elif is_hovered:
                pen = QPen(color.lighter(160), 2)
                brush = QBrush(color.darker(200))
            else:
                pen = QPen(color.darker(140), 2)
                brush = QBrush(color.darker(220))

            painter.setPen(pen)
            painter.setBrush(brush)
            painter.drawRoundedRect(
                int(r["x"]), int(r["y"]),
                int(r["width"]), int(r["height"]),
                6, 6
            )

            # Dibujar número de índice en el centro (sutil)
            if r["width"] > 40 and r["height"] > 24:
                painter.setPen(QColor(255, 255, 255, 80))
                font = QFont("sans-serif", 11)
                painter.setFont(font)
                cx = r["x"] + r["width"] / 2 - 8
                cy = r["y"] + r["height"] / 2 + 5
                painter.drawText(int(cx), int(cy), str(i + 1))

        # Dibujar divisores como líneas semi-transparentes
        for d in self._compute_dividers():
            painter.setPen(QPen(QColor(255, 255, 255, 40), 1, Qt.PenStyle.DashLine))
            painter.drawLine(
                int(d["x1"]), int(d["y1"]),
                int(d["x2"]), int(d["y2"])
            )

        painter.end()
