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
    property var lastDesktopCounts: new Map()

    // Valores de respaldo usados cuando dbusLoader.item aún no ha cargado
    // (o el bridge es null) para no abortar el retiling en el arranque.
    readonly property var fallbackDefaults: ({
        autoTilingEnabled: true,
        innerGap: 12,
        outerMargins: { top: 12, bottom: 12, left: 12, right: 12 }
    })

    function isTileable(window) {
        var isSpecial = window.desktopWindow || window.dock || window.splash || window.notification;
        var isBusy = window.minimized || window.fullScreen;
        // En KWin 6 / Wayland, normalWindow puede venir undefined/false para
        // apps como Ghostty, Alacritty, Konsole, Firefox o Chrome. Se acepta
        // la ventana si es normalWindow, o si no es special/utility.
        var result = !isSpecial && !isBusy
            && (!!window.normalWindow || (!window.specialWindow && !window.utility));
        console.log("[KFLOW-KWIN] isTileable(\"" + window.caption + "\") = " + result
            + " [normalWindow=" + window.normalWindow
            + " specialWindow=" + window.specialWindow
            + " utility=" + window.utility
            + " desktopWindow=" + window.desktopWindow
            + " dock=" + window.dock
            + " splash=" + window.splash
            + " notification=" + window.notification
            + " minimized=" + window.minimized
            + " fullScreen=" + window.fullScreen + "]");
        return result;
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
        console.log("[KFLOW-KWIN] Pantalla " + screen + ", escritorio " + desktop
            + ": " + result.length + " ventana(s) tileable(s) detectada(s) de " + all.length + " total(es)");
        return result;
    }

    function retile(desktop, screen) {
        var bridge = dbusLoader.item;
        var usingFallback = !bridge;
        var autoTilingEnabled = usingFallback ? kflow.fallbackDefaults.autoTilingEnabled : bridge.autoTilingEnabled;
        var innerGap = usingFallback ? kflow.fallbackDefaults.innerGap : bridge.innerGap;
        var outerMargins = usingFallback ? kflow.fallbackDefaults.outerMargins : bridge.outerMargins;
        var layoutTree = usingFallback ? null : bridge.layoutTree;

        if (usingFallback) {
            console.log("[KFLOW-KWIN] retile() — bridge aún no cargado, usando valores por defecto seguros"
                + " (pantalla=" + screen + ", escritorio=" + desktop + ")");
        }
        if (!autoTilingEnabled) {
            console.log("[KFLOW-KWIN] retile() abortado — autoTilingEnabled=false"
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

        var rects;
        var tree = layoutTree;
        if (tree && tree.type && Engine.countLeaves(tree) === windows.length) {
            console.log("[KFLOW-KWIN] retile() usando layout_tree personalizado ("
                + Engine.countLeaves(tree) + " hojas)");
            rects = Engine.computeLayoutFromTree(tree, area, innerGap, outerMargins);
            if (!rects || rects.length === 0) {
                console.log("[KFLOW-KWIN] computeLayoutFromTree() devolvió vacío — fallback a BSP automático");
                rects = Engine.computeLayout(area, innerGap, outerMargins, windows.length);
            }
        } else {
            console.log("[KFLOW-KWIN] retile() usando BSP automático (sin layout_tree o no coincide el número de hojas)");
            rects = Engine.computeLayout(area, innerGap, outerMargins, windows.length);
        }

        var count = Math.min(windows.length, rects.length);
        console.log("[KFLOW-KWIN] Aplicando retiling en pantalla=" + screen + ", escritorio=" + desktop
            + ": " + count + " ventana(s), área=" + JSON.stringify(area)
            + ", innerGap=" + innerGap + ", outerMargins=" + JSON.stringify(outerMargins));
        for (var i = 0; i < count; ++i) {
            console.log("[KFLOW-KWIN]   ventana \"" + windows[i].caption + "\" -> geometry="
                + JSON.stringify(rects[i]));
            windows[i].frameGeometry = Qt.rect(rects[i].x, rects[i].y, rects[i].width, rects[i].height);
        }
    }

    function retileAllScreens() {
        var screens = Workspace.screens;
        var desktop = Workspace.currentDesktop;
        for (var i = 0; i < screens.length; ++i) {
            retile(desktop, screens[i]);
        }
    }

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

    function hookWindow(w) {
        if (!w) return;
        try {
            w.desktopsChanged.connect(kflow.onWorkspaceChanged);
            w.outputChanged.connect(kflow.onWorkspaceChanged);
            w.minimizedChanged.connect(kflow.onWorkspaceChanged);
        } catch (e) {}
    }

    Component.onCompleted: {
        console.log("[KFLOW-KWIN] Component.onCompleted — inicializando hooks de ventanas existentes...");
        var all = Workspace.windows;
        for (var i = 0; i < all.length; ++i) {
            hookWindow(all[i]);
        }
        kflow.onWorkspaceChanged();
        initialRetileTimer.start();
    }

    // Reacomoda las ventanas ya abiertas 100ms después del arranque (o al
    // recargar el script vía "Aplicar ahora"), una vez que dbusLoader.item
    // ya tuvo tiempo de cargar y el workspace está estable.
    Timer {
        id: initialRetileTimer
        interval: 100
        repeat: false
        onTriggered: {
            console.log("[KFLOW-KWIN] initialRetileTimer disparado — forzando retileAllScreens() inicial");
            kflow.retileAllScreens();
        }
    }

    Connections {
        target: Workspace
        function onWindowAdded(window) {
            kflow.hookWindow(window);
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
