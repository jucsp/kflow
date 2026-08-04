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
            if (!isTileable(w)) {
                console.log("[KFLOW-KWIN] Ventana ignorada (\"" + w.caption + "\"): "
                    + "normalWindow=" + w.normalWindow
                    + " minimized=" + w.minimized
                    + " fullScreen=" + w.fullScreen
                    + " keepAbove=" + w.keepAbove
                    + " keepBelow=" + w.keepBelow);
                continue;
            }
            if (w.output !== screen) continue;
            if (w.onAllDesktops || w.desktops.indexOf(desktop) !== -1) {
                result.push(w);
            }
        }
        console.log("[KFLOW-KWIN] Pantalla " + screen + ", escritorio " + desktop
            + ": " + result.length + " ventana(s) tileable(s) detectada(s) de " + all.length + " total(es)");
        return result;
    }

    // Recalcula y aplica el layout de tiling dinámico para un escritorio/pantalla.
    function retile(desktop, screen) {
        var bridge = dbusLoader.item;
        if (!bridge || !bridge.autoTilingEnabled) {
            console.log("[KFLOW-KWIN] retile() abortado — bridge no cargado o autoTilingEnabled=false"
                + " (pantalla=" + screen + ", escritorio=" + desktop + ")");
            return;
        }
        var windows = windowsOnDesktopAndScreen(desktop, screen);
        if (windows.length === 0) {
            console.log("[KFLOW-KWIN] retile() sin ventanas que tilear en pantalla=" + screen
                + ", escritorio=" + desktop + " — nada que hacer");
            return;
        }
        var area = Workspace.clientArea(KWin.PlacementArea, screen, desktop);

        // Si hay un layout_tree personalizado Y su número de hojas coincide
        // con la cantidad de ventanas, úsalo; si no, cae en BSP automático.
        var rects;
        var tree = bridge.layoutTree;
        if (tree && tree.type && Engine.countLeaves(tree) === windows.length) {
            console.log("[KFLOW-KWIN] retile() usando layout_tree personalizado ("
                + Engine.countLeaves(tree) + " hojas)");
            rects = Engine.computeLayoutFromTree(tree, area, bridge.innerGap, bridge.outerMargins);
            // Fallback: si computeLayoutFromTree devuelve vacío, usar BSP
            if (!rects || rects.length === 0) {
                console.log("[KFLOW-KWIN] computeLayoutFromTree() devolvió vacío — fallback a BSP automático");
                rects = Engine.computeLayout(area, bridge.innerGap, bridge.outerMargins, windows.length);
            }
        } else {
            console.log("[KFLOW-KWIN] retile() usando BSP automático (sin layout_tree o no coincide el número de hojas)");
            rects = Engine.computeLayout(area, bridge.innerGap, bridge.outerMargins, windows.length);
        }

        var count = Math.min(windows.length, rects.length);
        console.log("[KFLOW-KWIN] Aplicando retiling en pantalla=" + screen + ", escritorio=" + desktop
            + ": " + count + " ventana(s), área=" + JSON.stringify(area)
            + ", innerGap=" + bridge.innerGap + ", outerMargins=" + JSON.stringify(bridge.outerMargins));
        for (var i = 0; i < count; ++i) {
            console.log("[KFLOW-KWIN]   ventana \"" + windows[i].caption + "\" -> geometry="
                + JSON.stringify(rects[i]));
            windows[i].frameGeometry = Qt.rect(rects[i].x, rects[i].y, rects[i].width, rects[i].height);
        }
    }

    // Soporte multi-monitor: retilea el escritorio actual en TODAS las
    // pantallas, no solo en la activa. windowsOnDesktopAndScreen() ya
    // filtra por w.output === screen, así que cada pantalla se calcula de
    // forma independiente y las ventanas de un monitor nunca invaden el
    // área de otro.
    function retileAllScreens() {
        var screens = Workspace.screens;
        var desktop = Workspace.currentDesktop;
        for (var i = 0; i < screens.length; ++i) {
            retile(desktop, screens[i]);
        }
    }

    // AutoVirtualDesktop: crea un escritorio nuevo si el actual llegó al umbral
    // y elimina escritorios vacíos (nunca el único restante). Los escritorios
    // virtuales son globales a todos los monitores en KWin, así que el
    // conteo (creación Y eliminación) se hace sobre TODAS las pantallas, no
    // solo la activa — si no, un monitor secundario saturado nunca dispara
    // la creación de un escritorio nuevo mientras el usuario mira el primario.
    function manageDesktops() {
        var bridge = dbusLoader.item;
        if (!bridge || !bridge.autoVirtualDesktop) {
            return;
        }
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
        var currentCount = 0;
        var allWindows = Workspace.windows;
        for (var j = 0; j < allWindows.length; ++j) {
            if (!isTileable(allWindows[j])) continue;
            if (allWindows[j].onAllDesktops || allWindows[j].desktops.indexOf(current) !== -1) {
                currentCount++;
            }
        }
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
        retileAllScreens();
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
            kflow.retileAllScreens();
        }
        function onScreensChanged() {
            kflow.retileAllScreens();
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
