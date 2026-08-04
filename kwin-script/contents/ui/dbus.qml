/*
    KFlow — Puente de configuración en vivo.

    NOTA TÉCNICA IMPORTANTE (HU-04):
    El sandbox de scripting de KWin (JS/QML, tanto API "javascript" como
    "declarativescript") no expone QDBusConnection ni ningún tipo QML capaz
    de registrar un servicio D-Bus propio: no existe módulo QML "QtDBus" ni
    equivalente, y `busctl --user list` confirma que solo interfaces nativas
    de KWin en C++ (org.kde.KWin.NightLight, HighlightWindow, etc.) aparecen
    en el bus. Por lo tanto este archivo NO registra org.kde.KWin.KFlow.

    El bridge real funciona así:
      1. Un proceso externo sin sandbox (el Control Center en PyQt6, HU-05)
         posee el servicio D-Bus org.kde.KWin.KFlow usando QtDBus.
      2. Al recibir una llamada (setInnerGap, setOuterMargins, setProfile,
         toggleAutoTiling), ese proceso escribe el valor en kwinrc:
           kwriteconfig6 --file kwinrc --group Script-kflow --key InnerGap 8
      3. Luego invoca el método real y ya existente
         `org.kde.KWin /KWin reconfigure` (confirmado activo en este
         sistema), que KWin retransmite como señal Options.configChanged
         a todos los scripts cargados.
      4. Este archivo escucha esa señal y relee la configuración desde
         disco, exponiendo las mismas operaciones (setInnerGap, etc.) para
         quien quiera aplicarlas sin pasar por D-Bus (p. ej. pruebas
         locales o una futura UI de configuración embebida).
*/
import QtQuick
import org.kde.kwin

QtObject {
    id: bridge

    signal configurationChanged()

    property int innerGap: 8
    property var outerMargins: ({ top: 24, bottom: 8, left: 8, right: 8 })
    property bool autoTilingEnabled: true
    property string activeProfile: "default"
    property var layoutTree: null

    function reloadFromDisk() {
        innerGap = parseInt(KWin.readConfig("InnerGap", "8"), 10);
        outerMargins = {
            top: parseInt(KWin.readConfig("OuterMarginTop", "24"), 10),
            bottom: parseInt(KWin.readConfig("OuterMarginBottom", "8"), 10),
            left: parseInt(KWin.readConfig("OuterMarginLeft", "8"), 10),
            right: parseInt(KWin.readConfig("OuterMarginRight", "8"), 10)
        };
        autoTilingEnabled = KWin.readConfig("AutoTilingEnabled", "true") === "true";
        activeProfile = KWin.readConfig("ActiveProfile", "default");

        // layout_tree: JSON serializado en kwinrc
        var raw = KWin.readConfig("LayoutTree", "");
        if (raw !== "") {
            try {
                layoutTree = JSON.parse(raw);
            } catch (e) {
                layoutTree = null;
            }
        } else {
            layoutTree = null;
        }
    }

    function setInnerGap(pixels) {
        innerGap = pixels;
        configurationChanged();
    }

    function setOuterMargins(top, bottom, left, right) {
        outerMargins = { top: top, bottom: bottom, left: left, right: right };
        configurationChanged();
    }

    function setProfile(name) {
        activeProfile = name;
        configurationChanged();
    }

    function toggleAutoTiling(enabled) {
        autoTilingEnabled = enabled;
        configurationChanged();
    }

    property Connections _optionsWatcher: Connections {
        target: Options
        function onConfigChanged() {
            bridge.reloadFromDisk();
            bridge.configurationChanged();
        }
    }
}
