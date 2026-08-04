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
         sistema), que KWin usa para recargar su configuración global.

    NOTA TÉCNICA (v0.2.2 — auditoría "retiling en vivo no funciona"):
    La versión anterior escuchaba `Options.configChanged` para detectar el
    reconfigure y releer kwinrc. No fue posible confirmar que el singleton
    QML "Options" esté expuesto al sandbox de "declarativescript" (no
    aparece registrado como tipo importable documentado del módulo
    "org.kde.kwin" para scripts, a diferencia de "Workspace" y "KWin", que
    sí están confirmados en uso real en este proyecto y en scripts KDE
    instalados). Si el binding fallaba silenciosamente, el bridge nunca
    releía kwinrc tras "Aplicar ahora", y por lo tanto script.js jamás veía
    los valores nuevos ni retileaba. Para no depender de una señal cuya
    disponibilidad no se pudo verificar, este archivo ahora usa un Timer de
    bajo costo que compara directamente los valores crudos de KWin.readConfig
    en cada tick y solo dispara reloadFromDisk()+configurationChanged() si
    algo cambió. Esto garantiza que cualquier escritura en kwinrc (desde el
    Control Center, o desde kwriteconfig6 manual) se refleje en <=400ms,
    independientemente de si la señal de KWin llega o no.
*/
import QtQuick
import org.kde.kwin

QtObject {
    id: bridge

    signal configurationChanged()

    property int innerGap: 8
    property var outerMargins: ({ top: 24, bottom: 8, left: 8, right: 8 })
    property bool autoTilingEnabled: true
    property bool autoVirtualDesktop: true
    property string activeProfile: "default"
    property var layoutTree: null

    // Última huella cruda de kwinrc vista por el poll (ver Timer más abajo).
    property string _lastRawConfig: ""

    function _rawConfigSnapshot() {
        return [
            KWin.readConfig("InnerGap", "8"),
            KWin.readConfig("OuterMarginTop", "24"),
            KWin.readConfig("OuterMarginBottom", "8"),
            KWin.readConfig("OuterMarginLeft", "8"),
            KWin.readConfig("OuterMarginRight", "8"),
            KWin.readConfig("AutoTilingEnabled", "true"),
            KWin.readConfig("AutoVirtualDesktop", "true"),
            KWin.readConfig("ActiveProfile", "default"),
            KWin.readConfig("LayoutTree", "")
        ].join("");
    }

    function reloadFromDisk() {
        console.log("[KFLOW-KWIN] reloadFromDisk() — releyendo kwinrc (Script-kflow)...");
        innerGap = parseInt(KWin.readConfig("InnerGap", "8"), 10);
        outerMargins = {
            top: parseInt(KWin.readConfig("OuterMarginTop", "24"), 10),
            bottom: parseInt(KWin.readConfig("OuterMarginBottom", "8"), 10),
            left: parseInt(KWin.readConfig("OuterMarginLeft", "8"), 10),
            right: parseInt(KWin.readConfig("OuterMarginRight", "8"), 10)
        };
        autoTilingEnabled = KWin.readConfig("AutoTilingEnabled", "true") === "true";
        autoVirtualDesktop = KWin.readConfig("AutoVirtualDesktop", "true") === "true";
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

        bridge._lastRawConfig = bridge._rawConfigSnapshot();
        console.log("[KFLOW-KWIN] Config cargada: innerGap=" + innerGap
            + " outerMargins=" + JSON.stringify(outerMargins)
            + " autoTilingEnabled=" + autoTilingEnabled
            + " autoVirtualDesktop=" + autoVirtualDesktop
            + " activeProfile=" + activeProfile
            + " layoutTree=" + (layoutTree ? JSON.stringify(layoutTree) : "null"));
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

    // Poll de bajo costo: detecta cambios en kwinrc (escritos por el Control
    // Center vía kwriteconfig6 + reconfigure D-Bus) sin depender de que una
    // señal específica de KWin llegue hasta este script en sandbox.
    property Timer _configPoll: Timer {
        interval: 400
        running: true
        repeat: true
        onTriggered: {
            var snap = bridge._rawConfigSnapshot();
            if (snap !== bridge._lastRawConfig) {
                console.log("[KFLOW-KWIN] Cambio detectado en kwinrc (poll de 400ms) — disparando reloadFromDisk()");
                bridge.reloadFromDisk();
                bridge.configurationChanged();
            }
        }
    }
}
