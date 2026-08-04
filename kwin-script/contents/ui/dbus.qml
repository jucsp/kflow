/*
    KFlow — Puente de configuración en vivo para KDE Plasma 6.
*/
import QtQuick
import org.kde.kwin

Item {
    id: bridge

    signal configurationChanged()

    property int innerGap: 8
    property var outerMargins: ({ top: 24, bottom: 8, left: 8, right: 8 })
    property bool autoTilingEnabled: true
    property bool autoVirtualDesktop: true
    property string activeProfile: "default"
    property var layoutTree: null

    // Última huella cruda de kwinrc vista por el poll
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
        ].join(" ");
    }

    function reloadFromDisk() {
        console.warn("[KFLOW-KWIN] reloadFromDisk() — releyendo kwinrc (Script-kflow)...");
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
                console.warn("[KFLOW-KWIN] Error al parsear LayoutTree: " + e);
                layoutTree = null;
            }
        } else {
            layoutTree = null;
        }

        bridge._lastRawConfig = bridge._rawConfigSnapshot();
        console.warn("[KFLOW-KWIN] Config cargada exitosamente: innerGap=" + innerGap
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

    // Timer child válido dentro de Item QML
    Timer {
        id: configPoll
        interval: 300
        running: true
        repeat: true
        onTriggered: {
            var snap = bridge._rawConfigSnapshot();
            if (snap !== bridge._lastRawConfig) {
                console.warn("[KFLOW-KWIN] Cambio detectado en kwinrc (poll 300ms) — disparando reloadFromDisk()");
                bridge.reloadFromDisk();
                bridge.configurationChanged();
            }
        }
    }
}
