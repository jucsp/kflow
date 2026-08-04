"""KFlow — Servicio D-Bus real 'org.kde.KWin.KFlow' del Control Center (HU-05).

El sandbox de scripting de KWin no puede registrar D-Bus (ver
technical_memory.md, HU-04). Este proceso SIN sandbox (el Control Center en
PyQt6) sí puede, vía QtDBus, y es quien posee el servicio real. Al recibir
una llamada (setInnerGap, setOuterMargins, setProfile, toggleAutoTiling):
  1. Escribe el valor en kwinrc con `kwriteconfig6 --file kwinrc --group
     Script-kflow --key <K> <V>`.
  2. Dispara `qdbus org.kde.KWin /KWin org.kde.KWin.reconfigure`, que KWin
     retransmite como Options.configChanged a kwin-script/contents/ui/dbus.qml.
"""
import shutil
import subprocess

try:
    from PyQt6.QtCore import QObject, pyqtSlot
    from PyQt6.QtDBus import QDBusAbstractAdaptor, QDBusConnection
    _HAS_QTDBUS = True
except ImportError:  # pragma: no cover - entorno sin PyQt6/QtDBus instalado
    _HAS_QTDBUS = False
    QObject = object

SERVICE_NAME = "org.kde.KWin.KFlow"
OBJECT_PATH = "/KFlow"
INTERFACE_NAME = "org.kde.KWin.KFlow"
KWINRC_GROUP = "Script-kflow"

_QDBUS_CANDIDATES = ("qdbus-qt6", "qdbus6", "qdbus")


def find_qdbus_binary():
    for name in _QDBUS_CANDIDATES:
        path = shutil.which(name)
        if path:
            return path
    return None


def build_kwriteconfig_command(key, value):
    return ["kwriteconfig6", "--file", "kwinrc", "--group", KWINRC_GROUP, "--key", key, str(value)]


def build_reconfigure_command(qdbus_bin=None):
    qdbus_bin = qdbus_bin or find_qdbus_binary() or "qdbus"
    return [qdbus_bin, "org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure"]


def run_command(cmd):
    subprocess.run(cmd, check=True)


def write_config(key, value):
    run_command(build_kwriteconfig_command(key, value))


def trigger_reconfigure():
    run_command(build_reconfigure_command())


def apply_and_reconfigure(updates):
    """Escribe varias claves en kwinrc y dispara UN solo reconfigure al final.
    
    `updates` es un dict clave → valor. Los valores pueden ser str, int, bool,
    o dict (se serializan a JSON para claves como LayoutTree)."""
    for key, value in updates.items():
        if isinstance(value, (dict, list)):
            import json
            value = json.dumps(value, separators=(",", ":"))
        elif isinstance(value, bool):
            value = "true" if value else "false"
        write_config(key, value)
    trigger_reconfigure()


if _HAS_QTDBUS:

    class KFlowAdaptor(QDBusAbstractAdaptor):
        """Adaptor D-Bus expuesto en /KFlow bajo la interfaz org.kde.KWin.KFlow."""

        def __init__(self, service):
            super().__init__(service)
            self.setAutoRelaySignals(True)
            self._service = service

        @pyqtSlot(int)
        def setInnerGap(self, pixels):
            self._service.set_inner_gap(pixels)

        @pyqtSlot(int, int, int, int)
        def setOuterMargins(self, top, bottom, left, right):
            self._service.set_outer_margins(top, bottom, left, right)

        @pyqtSlot(str)
        def setProfile(self, name):
            self._service.set_profile(name)

        @pyqtSlot(bool)
        def toggleAutoTiling(self, enabled):
            self._service.toggle_auto_tiling(enabled)

    class KFlowDBusService(QObject):
        """Posee y registra org.kde.KWin.KFlow en el bus de sesión."""

        def __init__(self, on_change=None, parent=None):
            super().__init__(parent)
            self._adaptor = KFlowAdaptor(self)
            self._on_change = on_change
            self._connection = QDBusConnection.sessionBus()

        def register(self):
            if not self._connection.registerObject(OBJECT_PATH, self):
                raise RuntimeError(f"No se pudo registrar el objeto D-Bus en {OBJECT_PATH}")
            if not self._connection.registerService(SERVICE_NAME):
                raise RuntimeError(
                    f"No se pudo registrar el servicio D-Bus {SERVICE_NAME} (¿ya está en uso?)"
                )
            return True

        def unregister(self):
            self._connection.unregisterService(SERVICE_NAME)
            self._connection.unregisterObject(OBJECT_PATH)

        def set_inner_gap(self, pixels):
            write_config("InnerGap", pixels)
            trigger_reconfigure()
            self._notify()

        def set_outer_margins(self, top, bottom, left, right):
            apply_and_reconfigure({
                "OuterMarginTop": top,
                "OuterMarginBottom": bottom,
                "OuterMarginLeft": left,
                "OuterMarginRight": right,
            })
            self._notify()

        def set_profile(self, name):
            write_config("ActiveProfile", name)
            trigger_reconfigure()
            self._notify()

        def toggle_auto_tiling(self, enabled):
            write_config("AutoTilingEnabled", "true" if enabled else "false")
            trigger_reconfigure()
            self._notify()

        def _notify(self):
            if self._on_change:
                self._on_change()
