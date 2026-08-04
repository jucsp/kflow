#!/usr/bin/env python3
"""KFlow Control Center — PyQt6 GUI (HU-05/06).

Ventana principal con:
  - Dark Mode integrado (paleta KDE Plasma 6 / Breeze Dark).
  - System Tray Icon con menú contextual (Mostrar / Salir).
  - Sliders dinámicos: Inner Gap (0-40 px) y Outer Padding independiente
    (Top, Bottom, Left, Right 0-60 px).
  - Toggle AutoVirtualDesktop.
  - Selector de perfiles predefinidos: Grid, Master+Stack, 50/50, Columns.
  - Vista previa gráfica interactiva del layout (TilingPreviewWidget).
  - Conexión con dbus_service: escribe kwinrc + reconfigure al cambiar
    cualquier valor; también registra el servicio D-Bus real
    org.kde.KWin.KFlow si QtDBus está disponible.
"""

import json
import os
import sys

# ---------------------------------------------------------------------------
# Resolución de imports locales (el script se ejecuta desde control-center/)
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QIcon, QPalette, QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from ui.preview_widget import TilingPreviewWidget
from profile_manager import ProfileManager
from dbus_service import (
    KFlowDBusService,
    apply_and_reconfigure,
    write_config,
    trigger_reconfigure,
    _HAS_QTDBUS,
)
from tiling_preview import TEMPLATE_TREES

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
APP_TITLE = "KFlow Control Center"
APP_VERSION = "0.1.0"
ORG_NAME = "kflow"

INNER_GAP_MIN, INNER_GAP_MAX = 0, 40
OUTER_MARGIN_MIN, OUTER_MARGIN_MAX = 0, 60
DEFAULT_INNER_GAP = 8
DEFAULT_OUTER_TOP = 24
DEFAULT_OUTER_BOTTOM = 8
DEFAULT_OUTER_LEFT = 8
DEFAULT_OUTER_RIGHT = 8
DEFAULT_AUTO_VDESKTOP = True

# ---------------------------------------------------------------------------
# Perfiles predefinidos (HU-06)
# ---------------------------------------------------------------------------
BUILTIN_PROFILES = {
    "Grid 2×2": {
        "inner_gap": 8,
        "outer_margins": {"top": 8, "bottom": 8, "left": 8, "right": 8},
        "auto_virtual_desktop": True,
        "layout_tree": TEMPLATE_TREES.get("Grid 2×2"),
    },
    "Master+Stack": {
        "inner_gap": 4,
        "outer_margins": {"top": 24, "bottom": 4, "left": 4, "right": 4},
        "auto_virtual_desktop": True,
        "layout_tree": TEMPLATE_TREES.get("Master+Stack"),
    },
    "50/50": {
        "inner_gap": 0,
        "outer_margins": {"top": 0, "bottom": 0, "left": 0, "right": 0},
        "auto_virtual_desktop": False,
        "layout_tree": TEMPLATE_TREES.get("50/50"),
    },
    "Columns": {
        "inner_gap": 12,
        "outer_margins": {"top": 12, "bottom": 12, "left": 12, "right": 12},
        "auto_virtual_desktop": True,
        "layout_tree": TEMPLATE_TREES.get("Columns"),
    },
}


# ---------------------------------------------------------------------------
# Paleta Dark Mode (inspirada en Breeze Dark / KDE Plasma 6)
# ---------------------------------------------------------------------------
def _dark_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor("#2A2E32"))
    p.setColor(QPalette.ColorRole.WindowText, QColor("#EFF0F1"))
    p.setColor(QPalette.ColorRole.Base, QColor("#1B1E20"))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor("#31363B"))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor("#3DAEE9"))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor("#EFF0F1"))
    p.setColor(QPalette.ColorRole.Text, QColor("#EFF0F1"))
    p.setColor(QPalette.ColorRole.Button, QColor("#31363B"))
    p.setColor(QPalette.ColorRole.ButtonText, QColor("#EFF0F1"))
    p.setColor(QPalette.ColorRole.BrightText, QColor("#DA4453"))
    p.setColor(QPalette.ColorRole.Link, QColor("#3DAEE9"))
    p.setColor(QPalette.ColorRole.Highlight, QColor("#3DAEE9"))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#1B1E20"))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#7F8C8D"))
    return p


def _dark_stylesheet() -> str:
    return """
    QMainWindow { background-color: #2A2E32; }
    QGroupBox {
        border: 1px solid #3DAEE9;
        border-radius: 6px;
        margin-top: 14px;
        font-weight: bold;
        color: #EFF0F1;
        padding-top: 8px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: #3DAEE9;
    }
    QSlider::groove:horizontal {
        background: #1B1E20;
        height: 6px;
        border-radius: 3px;
    }
    QSlider::handle:horizontal {
        background: #3DAEE9;
        width: 16px;
        height: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }
    QSlider::sub-page:horizontal {
        background: #3DAEE9;
        border-radius: 3px;
    }
    QCheckBox { color: #EFF0F1; spacing: 8px; }
    QCheckBox::indicator {
        width: 18px; height: 18px;
        border: 2px solid #3DAEE9;
        border-radius: 3px;
        background: #1B1E20;
    }
    QCheckBox::indicator:checked { background: #3DAEE9; }
    QComboBox {
        background: #31363B;
        color: #EFF0F1;
        border: 1px solid #3DAEE9;
        border-radius: 4px;
        padding: 4px 8px;
    }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView {
        background: #31363B;
        color: #EFF0F1;
        selection-background-color: #3DAEE9;
    }
    QPushButton {
        background: #3DAEE9;
        color: #1B1E20;
        border: none;
        border-radius: 4px;
        padding: 6px 18px;
        font-weight: bold;
    }
    QPushButton:hover { background: #5DC0F0; }
    QLabel { color: #EFF0F1; }
    """


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------
class KFlowMainWindow(QMainWindow):
    def __init__(self, profile_mgr: ProfileManager, dbus_service=None):
        super().__init__()
        self._profile_mgr = profile_mgr
        self._dbus_service = dbus_service
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(150)
        self._debounce_timer.timeout.connect(self._apply_current_settings)
        self._suppress_apply = False

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(560, 640)
        self.resize(600, 700)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # --- Vista previa interactiva ---
        self._preview = TilingPreviewWidget()
        self._preview.setMinimumHeight(220)
        self._preview.layoutChanged.connect(self._on_layout_edited)
        self._preview.selectionChanged.connect(self._on_selection_changed)
        root.addWidget(self._preview, stretch=2)

        # --- Botones de acción del editor visual ---
        editor_row = QHBoxLayout()
        editor_row.setSpacing(6)

        btn_split_v = QPushButton("Dividir ↕")
        btn_split_v.setToolTip("Dividir el recuadro seleccionado en 2 columnas (verticalmente)")
        btn_split_v.clicked.connect(self._preview.split_vertical)
        editor_row.addWidget(btn_split_v)

        btn_split_h = QPushButton("Dividir ↔")
        btn_split_h.setToolTip("Dividir el recuadro seleccionado en 2 filas (horizontalmente)")
        btn_split_h.clicked.connect(self._preview.split_horizontal)
        editor_row.addWidget(btn_split_h)

        btn_delete = QPushButton("Eliminar")
        btn_delete.setToolTip("Eliminar el recuadro seleccionado y expandir su hermano")
        btn_delete.clicked.connect(self._preview.delete_selected)
        editor_row.addWidget(btn_delete)

        editor_row.addStretch()

        # --- Slider de proporción de división ---
        editor_row.addWidget(QLabel("Ratio:"))
        self._ratio_slider = QSlider(Qt.Orientation.Horizontal)
        self._ratio_slider.setRange(5, 95)  # 0.05 a 0.95
        self._ratio_slider.setValue(50)
        self._ratio_slider.setFixedWidth(100)
        self._ratio_slider.setToolTip("Proporción de división del recuadro seleccionado (5%–95%)")
        self._ratio_slider.valueChanged.connect(self._on_ratio_slider_changed)
        self._ratio_slider.sliderReleased.connect(self._schedule_apply)
        self._ratio_slider.setEnabled(False)
        editor_row.addWidget(self._ratio_slider)

        self._ratio_label = QLabel("50%")
        self._ratio_label.setMinimumWidth(32)
        editor_row.addWidget(self._ratio_label)

        root.addLayout(editor_row)

        # --- Controles ---
        controls = QVBoxLayout()
        controls.setSpacing(8)

        controls.addWidget(self._build_gap_group())
        controls.addWidget(self._build_margins_group())
        controls.addWidget(self._build_vdesktop_group())
        controls.addWidget(self._build_profiles_group())

        root.addLayout(controls, stretch=3)

        # --- Botón aplicar explícito (feedback visual) ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        apply_btn = QPushButton("Aplicar ahora")
        apply_btn.clicked.connect(self._apply_current_settings)
        btn_row.addWidget(apply_btn)
        root.addLayout(btn_row)

        # Inicializar desde perfil activo
        self._load_active_profile()

    # ------------------------------------------------------------------
    # Constructores de grupos
    # ------------------------------------------------------------------
    def _build_gap_group(self) -> QGroupBox:
        gb = QGroupBox("Inner Gap (separación entre ventanas)")
        layout = QHBoxLayout(gb)
        self._gap_slider = QSlider(Qt.Orientation.Horizontal)
        self._gap_slider.setRange(INNER_GAP_MIN, INNER_GAP_MAX)
        self._gap_label = QLabel(f"{DEFAULT_INNER_GAP} px")
        self._gap_label.setMinimumWidth(36)
        self._gap_slider.valueChanged.connect(self._on_gap_changed)
        self._gap_slider.sliderReleased.connect(self._schedule_apply)
        layout.addWidget(self._gap_slider)
        layout.addWidget(self._gap_label)
        return gb

    def _build_margins_group(self) -> QGroupBox:
        gb = QGroupBox("Outer Padding (márgenes del escritorio)")
        grid = QGridLayout(gb)
        grid.setSpacing(8)

        self._margin_sliders = {}
        self._margin_labels = {}

        rows = [
            ("Top",    0, DEFAULT_OUTER_TOP),
            ("Bottom", 1, DEFAULT_OUTER_BOTTOM),
            ("Left",   2, DEFAULT_OUTER_LEFT),
            ("Right",  3, DEFAULT_OUTER_RIGHT),
        ]
        for label, row, default in rows:
            lbl = QLabel(label)
            lbl.setMinimumWidth(50)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(OUTER_MARGIN_MIN, OUTER_MARGIN_MAX)
            slider.setValue(default)
            val_lbl = QLabel(f"{default} px")
            val_lbl.setMinimumWidth(36)
            slider.valueChanged.connect(
                lambda v, l=val_lbl: l.setText(f"{v} px")
            )
            slider.sliderReleased.connect(self._schedule_apply)
            grid.addWidget(lbl, row, 0)
            grid.addWidget(slider, row, 1)
            grid.addWidget(val_lbl, row, 2)
            self._margin_sliders[label.lower()] = slider
            self._margin_labels[label.lower()] = val_lbl

        return gb

    def _build_vdesktop_group(self) -> QGroupBox:
        gb = QGroupBox("AutoVirtualDesktop")
        layout = QHBoxLayout(gb)
        self._avd_checkbox = QCheckBox(
            "Crear/eliminar escritorios virtuales automáticamente"
        )
        self._avd_checkbox.setChecked(DEFAULT_AUTO_VDESKTOP)
        self._avd_checkbox.toggled.connect(self._schedule_apply)
        layout.addWidget(self._avd_checkbox)
        return gb

    def _build_profiles_group(self) -> QGroupBox:
        gb = QGroupBox("Perfil de layout")
        outer = QVBoxLayout(gb)

        # --- Fila 1: selección y gestión de perfiles guardados ---
        row1 = QHBoxLayout()
        self._profile_combo = QComboBox()
        self._profile_combo.currentTextChanged.connect(self._on_profile_selected)
        row1.addWidget(QLabel("Perfil:"))
        row1.addWidget(self._profile_combo, stretch=1)

        new_btn = QPushButton("➕ Nuevo Perfil")
        new_btn.setToolTip("Crear un perfil nuevo con la configuración actual")
        new_btn.clicked.connect(self._new_profile)
        row1.addWidget(new_btn)

        save_btn = QPushButton("Guardar")
        save_btn.setToolTip("Guardar la configuración actual en el perfil seleccionado")
        save_btn.clicked.connect(self._save_current_profile)
        row1.addWidget(save_btn)

        delete_btn = QPushButton("Eliminar")
        delete_btn.clicked.connect(self._delete_profile)
        row1.addWidget(delete_btn)

        outer.addLayout(row1)

        # --- Fila 2: cargar un preajuste predefinido en el perfil actual ---
        row2 = QHBoxLayout()
        self._preset_combo = QComboBox()
        self._preset_combo.addItems(list(BUILTIN_PROFILES.keys()))
        self._preset_combo.setToolTip(
            "Preajuste predefinido para volcar en el perfil actualmente seleccionado"
        )
        row2.addWidget(QLabel("Preajuste:"))
        row2.addWidget(self._preset_combo, stretch=1)

        load_preset_btn = QPushButton("Cargar Preajuste")
        load_preset_btn.setToolTip(
            "Aplica el preajuste al perfil actual (gap, márgenes, AVD y layout)"
        )
        load_preset_btn.clicked.connect(self._load_preset)
        row2.addWidget(load_preset_btn)

        outer.addLayout(row2)

        self._refresh_profile_list()
        return gb

    # ------------------------------------------------------------------
    # Lógica de perfiles
    # ------------------------------------------------------------------
    def _refresh_profile_list(self):
        self._suppress_apply = True
        self._profile_combo.clear()
        names = self._profile_mgr.list_names()
        self._profile_combo.addItems(names)
        data = self._profile_mgr.load_all()
        active = data.get("active", "default")
        if active in names:
            self._profile_combo.setCurrentText(active)
        self._suppress_apply = False

    def _on_profile_selected(self, name: str):
        if self._suppress_apply or not name:
            return
        profile = self._profile_mgr.get_profile(name)
        if not profile:
            return
        self._profile_mgr.set_active(name)
        self._apply_profile_to_ui(profile)
        self._apply_current_settings()

    def _apply_profile_to_ui(self, profile: dict):
        """Carga los valores de un perfil en los sliders sin disparar apply."""
        self._suppress_apply = True
        self._gap_slider.setValue(profile.get("inner_gap", DEFAULT_INNER_GAP))
        margins = profile.get("outer_margins", {})
        for side in ("top", "bottom", "left", "right"):
            default = {
                "top": DEFAULT_OUTER_TOP,
                "bottom": DEFAULT_OUTER_BOTTOM,
                "left": DEFAULT_OUTER_LEFT,
                "right": DEFAULT_OUTER_RIGHT,
            }[side]
            self._margin_sliders[side].setValue(margins.get(side, default))
        self._avd_checkbox.setChecked(
            profile.get("auto_virtual_desktop", DEFAULT_AUTO_VDESKTOP)
        )
        # Cargar layout_tree del perfil en el editor visual
        tree = profile.get("layout_tree")
        if tree and isinstance(tree, dict) and "type" in tree:
            self._preview.set_layout_tree(tree)
        else:
            # Si el perfil no trae árbol, mantener el actual del editor
            pass
        self._suppress_apply = False
        self._update_preview()

    def _load_active_profile(self):
        data = self._profile_mgr.load_all()
        active_name = data.get("active", "default")
        profile = data["profiles"].get(active_name, data["profiles"]["default"])
        self._apply_profile_to_ui(profile)
        self._refresh_profile_list()

    def _new_profile(self):
        name, ok = QInputDialog.getText(
            self, "Nuevo perfil", "Nombre del nuevo perfil:"
        )
        name = name.strip()
        if not ok or not name:
            return
        if name == "default":
            QMessageBox.information(
                self, "Nombre no disponible",
                "'default' es un perfil reservado. Elige otro nombre."
            )
            return
        if name in self._profile_mgr.list_names():
            QMessageBox.information(
                self, "Perfil existente",
                f"Ya existe un perfil llamado '{name}'. Elige otro nombre."
            )
            return
        self._profile_mgr.save_profile(
            name=name,
            inner_gap=self._gap_slider.value(),
            outer_margins=self._current_margins(),
            auto_virtual_desktop=self._avd_checkbox.isChecked(),
            layout_tree=self._preview.layout_tree(),
        )
        self._profile_mgr.set_active(name)
        self._refresh_profile_list()
        self._apply_current_settings()

    def _save_current_profile(self):
        name = self._profile_combo.currentText()
        if name == "default":
            QMessageBox.information(
                self, "Perfil de solo lectura",
                "El perfil 'default' es predefinido. Usa '➕ Nuevo Perfil' "
                "para guardar la configuración actual con otro nombre."
            )
            return
        self._profile_mgr.save_profile(
            name=name,
            inner_gap=self._gap_slider.value(),
            outer_margins=self._current_margins(),
            auto_virtual_desktop=self._avd_checkbox.isChecked(),
            layout_tree=self._preview.layout_tree(),
        )
        self._refresh_profile_list()
        self._apply_current_settings()

    def _load_preset(self):
        """Vuelca un preajuste predefinido (BUILTIN_PROFILES) sobre el
        perfil actualmente seleccionado, sin crear un perfil nuevo."""
        name = self._preset_combo.currentText()
        preset = BUILTIN_PROFILES.get(name)
        if not preset:
            return
        self._apply_profile_to_ui(preset)
        self._apply_current_settings()

    def _delete_profile(self):
        name = self._profile_combo.currentText()
        if name == "default":
            QMessageBox.information(
                self, "No eliminable",
                "El perfil 'default' no se puede eliminar."
            )
            return
        confirm = QMessageBox.question(
            self, "Eliminar perfil",
            f"¿Eliminar el perfil '{name}'?\nSe restaurará el perfil 'default'.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self._profile_mgr.delete_profile(name)
            self._load_active_profile()
            self._refresh_profile_list()

    # ------------------------------------------------------------------
    # Callbacks de sliders → preview en tiempo real + debounce para apply
    # ------------------------------------------------------------------
    def _on_gap_changed(self, value: int):
        self._gap_label.setText(f"{value} px")
        self._update_preview()

    def _schedule_apply(self):
        if self._suppress_apply:
            return
        self._debounce_timer.start()

    def _apply_current_settings(self):
        """Vuelca los valores actuales a kwinrc + reconfigure."""
        inner = self._gap_slider.value()
        margins = self._current_margins()
        auto_vd = self._avd_checkbox.isChecked()
        tree = self._preview.layout_tree()

        # Actualizar kwinrc
        # NOTA (v0.2.2): "AutoTilingEnabled" gobierna el motor de tiling en
        # sí (siempre activo mientras el script esté cargado; no hay toggle
        # de UI para desactivarlo) y "AutoVirtualDesktop" gobierna solo la
        # creación/eliminación automática de escritorios. Antes ambos
        # conceptos compartían la misma clave, así que desmarcar
        # "AutoVirtualDesktop" apagaba también el retiling — bug corregido.
        updates = {
            "InnerGap": inner,
            "OuterMarginTop": margins["top"],
            "OuterMarginBottom": margins["bottom"],
            "OuterMarginLeft": margins["left"],
            "OuterMarginRight": margins["right"],
            "AutoTilingEnabled": True,
            "AutoVirtualDesktop": auto_vd,
        }
        # Incluir el perfil activo y el layout_tree (serializado a JSON)
        data = self._profile_mgr.load_all()
        active_name = data.get("active", "default")
        updates["ActiveProfile"] = active_name
        if tree and isinstance(tree, dict) and "type" in tree:
            updates["LayoutTree"] = tree
        else:
            updates["LayoutTree"] = ""

        layout_tree_json = (
            json.dumps(updates["LayoutTree"], separators=(",", ":"))
            if updates["LayoutTree"]
            else ""
        )
        print(
            "[KFLOW-GUI] Botón 'Aplicar ahora' presionado — parámetros recibidos: "
            f"InnerGap={inner}, OuterPadding={margins}, "
            f"AutoVirtualDesktop={auto_vd}, ActiveProfile={active_name}, "
            f"LayoutTreeJson={layout_tree_json!r}",
            flush=True,
        )

        apply_and_reconfigure(updates)
        print("[KFLOW-GUI] apply_and_reconfigure() completado sin excepciones.", flush=True)

        # Persistir en perfil activo
        self._profile_mgr.save_profile(
            name=active_name,
            inner_gap=inner,
            outer_margins=margins,
            auto_virtual_desktop=auto_vd,
            layout_tree=tree,
        )

    def _current_margins(self) -> dict:
        return {
            "top": self._margin_sliders["top"].value(),
            "bottom": self._margin_sliders["bottom"].value(),
            "left": self._margin_sliders["left"].value(),
            "right": self._margin_sliders["right"].value(),
        }

    def _update_preview(self):
        self._preview.set_inner_gap(self._gap_slider.value())
        m = self._current_margins()
        self._preview.set_outer_margins(
            m["top"], m["bottom"], m["left"], m["right"]
        )

    # ------------------------------------------------------------------
    # Callbacks del editor visual
    # ------------------------------------------------------------------
    def _on_layout_edited(self):
        """El usuario modificó el árbol (split/delete/drag/reset)."""
        self._schedule_apply()

    def _on_selection_changed(self):
        """Actualiza el slider de ratio según la selección actual."""
        ratio = self._preview.selected_node_ratio()
        if ratio is not None:
            self._ratio_slider.setEnabled(True)
            pct = int(round(ratio * 100))
            self._suppress_apply = True
            self._ratio_slider.setValue(pct)
            self._ratio_label.setText(f"{pct}%")
            self._suppress_apply = False
        else:
            self._ratio_slider.setEnabled(False)
            self._ratio_label.setText("--")

    def _on_ratio_slider_changed(self, value):
        """El usuario movió el slider de proporción de división."""
        if self._suppress_apply:
            return
        ratio = value / 100.0
        self._ratio_label.setText(f"{value}%")
        self._preview.set_selected_node_ratio(ratio)


# ---------------------------------------------------------------------------
# System Tray
# ---------------------------------------------------------------------------
class KFlowTray(QSystemTrayIcon):
    def __init__(self, main_window: KFlowMainWindow, parent=None):
        icon = QIcon.fromTheme("preferences-system-windows")
        if icon.isNull():
            # Fallback: ícono mínimo programático (16×16)
            from PyQt6.QtGui import QPixmap, QPainter
            pm = QPixmap(16, 16)
            pm.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pm)
            painter.setBrush(QColor("#3DAEE9"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, 0, 16, 16, 4, 4)
            painter.end()
            icon = QIcon(pm)

        super().__init__(icon, parent)
        self._main_window = main_window
        self.setToolTip(APP_TITLE)

        menu = QMenu()
        show_action = QAction("Mostrar", menu)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)

        menu.addSeparator()

        quit_action = QAction("Salir", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _show_window(self):
        self._main_window.show()
        self._main_window.raise_()
        self._main_window.activateWindow()

    def _quit(self):
        QApplication.quit()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_window()


# ---------------------------------------------------------------------------
# Inicialización de perfiles predefinidos (una sola vez)
# ---------------------------------------------------------------------------
def _seed_builtin_profiles(profile_mgr: ProfileManager):
    data = profile_mgr.load_all()
    changed = False
    for name, values in BUILTIN_PROFILES.items():
        if name not in data["profiles"]:
            data["profiles"][name] = {
                "name": name,
                "inner_gap": values["inner_gap"],
                "outer_margins": dict(values["outer_margins"]),
                "auto_virtual_desktop": values["auto_virtual_desktop"],
                "layout_tree": values.get("layout_tree"),
            }
            changed = True
    if changed:
        profile_mgr.save_all(data)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(APP_VERSION)

    # Dark Mode
    app.setPalette(_dark_palette())
    app.setStyleSheet(_dark_stylesheet())

    # Gestor de perfiles
    profile_mgr = ProfileManager()
    _seed_builtin_profiles(profile_mgr)

    # Servicio D-Bus (opcional: si QtDBus no está, igual funciona con kwriteconfig6)
    dbus_svc = None
    if _HAS_QTDBUS:
        try:
            dbus_svc = KFlowDBusService()
            dbus_svc.register()
        except RuntimeError as exc:
            print(f"[KFlow] No se pudo registrar D-Bus: {exc}", file=sys.stderr)
            dbus_svc = None

    # Ventana principal
    window = KFlowMainWindow(profile_mgr, dbus_svc)
    window.show()

    # System Tray
    tray = KFlowTray(window)
    tray.show()

    # Cleanup
    def _on_quit():
        if dbus_svc:
            try:
                dbus_svc.unregister()
            except Exception:
                pass

    app.aboutToQuit.connect(_on_quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
