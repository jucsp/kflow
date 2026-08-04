"""KFlow — Widget de vista previa interactiva convertido en editor visual de
mosaicos (HU-05). Permite hacer clic para seleccionar recuadros, dividirlos,
eliminarlos, arrastrar divisores y cargar plantillas predefinidas. El árbol
de layout resultante se persiste en profiles.json como 'layout_tree'.
"""
import copy
import json
import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPen, QBrush, QFont, QCursor
from PyQt6.QtWidgets import QWidget

from tiling_preview import (
    DEFAULT_LAYOUT_TREE,
    TEMPLATE_TREES,
    apply_outer_margins,
    compute_layout_from_tree,
    tree_to_rects,
    count_leaves,
)

ACCENT_COLORS = [
    "#3DAEE9", "#27AE60", "#E67E22", "#9B59B6",
    "#E74C3C", "#1ABC9C", "#F1C40F", "#95A5A6",
    "#EC407A", "#7F8C8D", "#2ECC71", "#5DADE2",
]

DEFAULT_VIRTUAL_SCREEN_SIZE = (1920, 1080)

# Umbral en píxeles para considerar "cerca de un divisor" (arrastre)
DIVIDER_GRAB = 10


class TilingPreviewWidget(QWidget):
    """Editor visual interactivo de layout_tree.

    Señales:
      layoutChanged(): emitida cada vez que el árbol se modifica (split,
                       delete, reset, drag).
      selectionChanged(): emitida cuando cambia la selección (para que la GUI
                          pueda actualizar el slider de ratio).
    """

    layoutChanged = pyqtSignal()
    selectionChanged = pyqtSignal()

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
        self.selectionChanged.emit()

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
        """Divide el nodo seleccionado SI es una hoja. Usa _get_node para
        obtener el nodo real (no el padre)."""
        node = self._get_node(self._selected_path)
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
        self.selectionChanged.emit()

    def delete_selected(self):
        """Elimina el recuadro seleccionado y expande su hermano, colapsando
        la división. No permite eliminar el último recuadro.
        
        Lógica corregida (v0.2.1): usa _get_node para obtener el nodo hermano
        real, no el padre-del-hermano como hacía _resolve_path antes.
        """
        if count_leaves(self._layout_tree) <= 1:
            return
        if not self._selected_path:
            return

        # Ruta al padre y al hermano
        parent_path = self._selected_path[:-1]
        sibling_key = "second" if self._selected_path[-1] == "first" else "first"
        sibling_path = parent_path + [sibling_key]

        # Obtener el nodo hermano REAL (no el padre)
        sibling_node = self._get_node(sibling_path)
        if sibling_node is None:
            return

        # Colapsar: reemplazar el padre con el hermano superviviente
        if parent_path:
            # Hay un abuelo: reemplazar el hijo correspondiente
            grandparent = self._get_node(parent_path[:-1])
            if grandparent is None:
                return
            grandparent[parent_path[-1]] = sibling_node
        else:
            # El padre es la raíz: el hermano se convierte en la nueva raíz
            self._layout_tree = sibling_node

        # Nueva selección: la posición donde estaba el padre (si existe)
        self._selected_path = parent_path[:-1] if parent_path else []
        self.update()
        self.layoutChanged.emit()
        self.selectionChanged.emit()

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
            self.selectionChanged.emit()

    # ------------------------------------------------------------------
    # Navegación del árbol
    # ------------------------------------------------------------------
    def _get_node(self, path):
        """Devuelve el nodo REAL en la ruta dada. path=[] = raíz.
        
        A diferencia de _resolve_path (que devuelve padre+key para poder
        reemplazar hijos), este método devuelve el nodo mismo. Usar cuando
        se necesita inspeccionar/modificar el contenido del nodo.
        """
        if not path:
            return self._layout_tree
        node = self._layout_tree
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return None
            node = node[key]
        return node

    def _resolve_path(self, path):
        """Devuelve (padre, clave_en_padre) para una ruta. path=[] = raíz.
        
        Útil para operaciones que necesitan reemplazar un hijo en el padre:
            parent, key = self._resolve_path(path)
            parent[key] = new_child
        """
        if not path:
            return None, None  # la raíz no tiene padre
        node = self._layout_tree
        for i, key in enumerate(path):
            if not isinstance(node, dict) or key not in node:
                return None, None
            if i == len(path) - 1:
                return node, key
            node = node[key]
        return None, None

    # --- Ratio del nodo seleccionado (para slider en GUI) ---

    def selected_node_ratio(self):
        """Ratio del padre del nodo seleccionado, o None si no aplica."""
        if not self._selected_path:
            return None
        parent_path = self._selected_path[:-1]
        parent = self._get_node(parent_path)
        if parent and isinstance(parent, dict) and parent.get("type") in ("vsplit", "hsplit"):
            return parent.get("ratio", 0.5)
        return None

    def set_selected_node_ratio(self, ratio):
        """Establece el ratio del padre del nodo seleccionado (0.05–0.95)."""
        if not self._selected_path:
            return
        parent_path = self._selected_path[:-1]
        parent = self._get_node(parent_path)
        if parent and isinstance(parent, dict) and parent.get("type") in ("vsplit", "hsplit"):
            parent["ratio"] = max(0.05, min(0.95, ratio))
            self.update()
            self.layoutChanged.emit()

    # ------------------------------------------------------------------
    # Geometría → píxeles
    # ------------------------------------------------------------------
    def _virtual_screen_size(self):
        """Tamaño de referencia para el cálculo de proporciones, tomado de la
        geometría real de la pantalla primaria del usuario (16:9, 21:9,
        16:10, etc.). Cae a 1920×1080 si no hay pantalla disponible (p.ej.
        entorno de pruebas headless)."""
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.geometry()
            if geo.width() > 0 and geo.height() > 0:
                return geo.width(), geo.height()
        return DEFAULT_VIRTUAL_SCREEN_SIZE

    def _screen_to_widget_scale(self):
        """Factores de escala y offsets para mapear coord virtuales → widget."""
        virtual_w, virtual_h = self._virtual_screen_size()
        scale = min(self.width() / virtual_w, self.height() / virtual_h)
        offset_x = (self.width() - virtual_w * scale) / 2
        offset_y = (self.height() - virtual_h * scale) / 2
        return scale, offset_x, offset_y

    def _compute_rects_and_paths(self):
        """Devuelve (rects_en_píxeles, paths) para cada hoja en el árbol."""
        scale, ox, oy = self._screen_to_widget_scale()
        virtual_w, virtual_h = self._virtual_screen_size()
        screen_area = {"x": 0, "y": 0, "width": virtual_w, "height": virtual_h}
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

    def _compute_screen_and_usable_px(self):
        """Devuelve (rect_pantalla_px, rect_usable_px) para dibujar el borde
        del monitor y la zona de Outer Padding (Top/Bottom/Left/Right)."""
        scale, ox, oy = self._screen_to_widget_scale()
        virtual_w, virtual_h = self._virtual_screen_size()
        screen_area = {"x": 0, "y": 0, "width": virtual_w, "height": virtual_h}
        usable = apply_outer_margins(screen_area, self._outer_margins)

        def to_px(area):
            return {
                "x": ox + area["x"] * scale,
                "y": oy + area["y"] * scale,
                "width": area["width"] * scale,
                "height": area["height"] * scale,
            }

        return to_px(screen_area), to_px(usable)

    def _compute_dividers(self):
        """Dividers mapeados a coordenadas de widget."""
        scale, ox, oy = self._screen_to_widget_scale()
        virtual_w, virtual_h = self._virtual_screen_size()
        screen_area = {"x": 0, "y": 0, "width": virtual_w, "height": virtual_h}
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
            node = self._get_node(divider["path"])
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
            self.selectionChanged.emit()

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
        node = self._get_node(self._drag_node_path)
        if not node:
            return

        scale, ox, oy = self._screen_to_widget_scale()
        virtual_w, virtual_h = self._virtual_screen_size()

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

        # --- Borde de pantalla + zona de Outer Padding (Top/Bottom/Left/Right) ---
        screen_px, usable_px = self._compute_screen_and_usable_px()
        painter.fillRect(
            int(screen_px["x"]), int(screen_px["y"]),
            int(screen_px["width"]), int(screen_px["height"]),
            QColor(255, 255, 255, 14),  # zona de margen: tenue, distinta del fondo
        )
        painter.fillRect(
            int(usable_px["x"]), int(usable_px["y"]),
            int(usable_px["width"]), int(usable_px["height"]),
            QColor("#1B1E20"),  # área usable: mismo tono que el fondo, "recorta" el margen
        )
        painter.setPen(QPen(QColor("#5C6166"), 1, Qt.PenStyle.SolidLine))
        painter.drawRect(
            int(screen_px["x"]), int(screen_px["y"]),
            int(screen_px["width"]), int(screen_px["height"]),
        )
        painter.setPen(QPen(QColor("#3DAEE9"), 1, Qt.PenStyle.DashLine))
        painter.drawRect(
            int(usable_px["x"]), int(usable_px["y"]),
            int(usable_px["width"]), int(usable_px["height"]),
        )

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
