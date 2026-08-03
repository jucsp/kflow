/*
    KFlow — Motor de AutoTiling dinámico + AutoVirtualDesktop para KWin 6.
    Entry point del paquete (X-Plasma-API: declarativescript).
*/
import QtQuick
import org.kde.kwin

import "script.js" as Engine
Item {
    id: kflow

    readonly property int desktopThreshold: 4
    // Recuerda el último conteo de ventanas por escritorio para disparar la
    // creación de un escritorio nuevo solo al CRUZAR el umbral (flanco de
    // subida), no en cada evento mientras el escritorio siga por encima.
    property var lastDesktopCounts: new Map()

    // Ventanas gestionadas: se excluyen las que no son "normales" (paneles,
    // diálogos, desktops especiales) o que el usuario sacó del tiling.
    function isTileable(window) {
        return window.normalWindow
            && !window.minimized
            && !window.fullScreen
            && !window.keepAbove
            && !window.keepBelow;
    }

    function windowsOnDesktopAndScreen(desktop, screen) {
        var result = [];
        var all = Workspace.windows;
        for (var i = 0; i < all.length; ++i) {
            var w = all[i];
            if (!isTileable(w)) continue;
            if (w.output !== screen) continue;
            if (w.onAllDesktops || w.desktops.indexOf(desktop) !== -1) {
                result.push(w);
            }
        }
        return result;
    }

    // Recalcula y aplica el layout de tiling dinámico para un escritorio/pantalla.
    function retile(desktop, screen) {
        var bridge = dbusLoader.item;
        if (!bridge || !bridge.autoTilingEnabled) {
            return;
        }
        var windows = windowsOnDesktopAndScreen(desktop, screen);
        if (windows.length === 0) {
            return;
        }
        var area = Workspace.clientArea(KWin.PlacementArea, screen, desktop);
        var rects = Engine.computeLayout(area, bridge.innerGap, bridge.outerMargins, windows.length);
        for (var i = 0; i < windows.length; ++i) {
            windows[i].frameGeometry = Qt.rect(rects[i].x, rects[i].y, rects[i].width, rects[i].height);
        }
    }

    function retileCurrent() {
        retile(Workspace.currentDesktop, Workspace.activeScreen);
    }

    // AutoVirtualDesktop: crea un escritorio nuevo si el actual llegó al umbral
    // y elimina escritorios vacíos (nunca el único restante).
    function manageDesktops() {
        var desktops = Workspace.desktops;
        for (var d = desktops.length - 1; d >= 0; --d) {
            var desktop = desktops[d];
            var count = 0;
            var all = Workspace.windows;
            for (var i = 0; i < all.length; ++i) {
                if (!isTileable(all[i])) continue;
                if (all[i].onAllDesktops || all[i].desktops.indexOf(desktop) !== -1) {
                    count++;
                }
            }
            if (Engine.shouldRemoveDesktop(count, Workspace.desktops.length)) {
                Workspace.removeDesktop(desktop);
                kflow.lastDesktopCounts.delete(desktop);
            }
        }

        var current = Workspace.currentDesktop;
        var currentCount = windowsOnDesktopAndScreen(current, Workspace.activeScreen).length;
        var previousCount = kflow.lastDesktopCounts.has(current) ? kflow.lastDesktopCounts.get(current) : 0;
        kflow.lastDesktopCounts.set(current, currentCount);

        var crossedThreshold = previousCount < kflow.desktopThreshold
            && Engine.shouldCreateDesktop(currentCount, kflow.desktopThreshold);
        if (crossedThreshold) {
            var position = Workspace.desktops.indexOf(current) + 1;
            Workspace.createDesktop(position, "KFlow " + (position + 1));
        }
    }

    function onWorkspaceChanged() {
        manageDesktops();
        retileCurrent();
    }

    Connections {
        target: Workspace
        function onWindowAdded(window) {
            window.desktopsChanged.connect(kflow.onWorkspaceChanged);
            window.outputChanged.connect(kflow.onWorkspaceChanged);
            kflow.onWorkspaceChanged();
        }
        function onWindowRemoved(window) {
            kflow.onWorkspaceChanged();
        }
        function onCurrentDesktopChanged() {
            kflow.retileCurrent();
        }
        function onScreensChanged() {
            kflow.retileCurrent();
        }
    }

    // Puente de configuración en vivo (gaps, márgenes, perfiles, toggle).
    // Se carga vía Loader porque QML solo permite instanciar un componente
    // como etiqueta si el nombre de archivo coincide con el tipo (p. ej.
    // "DBusBridge.qml"); como el paquete requiere el nombre "dbus.qml", se
    // carga por ruta, igual que hace KWin con osd.qml en scripts nativos.
    // Ver dbus.qml para el detalle de por qué es un puente de configuración
    // y no un servicio D-Bus propio.
    Loader {
        id: dbusLoader
        source: "dbus.qml"
        onLoaded: {
            item.reloadFromDisk();
            item.configurationChanged.connect(kflow.onWorkspaceChanged);
            kflow.onWorkspaceChanged();
        }
    }
}
