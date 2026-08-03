# Memoria Técnica Persistente — KFlow

- **Entorno Objetivo:** Fedora Linux con KDE Plasma 6 (Wayland/X11, KWin 6.x API).
- **Nombre de Paquete KWin:** `kflow` (`metadata.json`, API `declarativescript`, KWin 3.0/QML 2.15).
- **Servicio D-Bus:** `org.kde.KWin.KFlow`
- **Ubicación de Configuración:** `~/.config/kflow/profiles.json`
- **Estructura del Proyecto:**
  - `kwin-script/`: Motor de KWin en JavaScript/QML para KDE Plasma 6.
  - `control-center/`: Aplicación GUI moderna en PyQt6 para control visual y ajustes de Gaps.

## Arquitectura del motor (HU-02/03), verificada contra scripts reales instalados en este sistema

- **Entry point real:** con `X-Plasma-API: declarativescript`, KWin carga `contents/ui/main.qml` (NO `contents/code/main.js`). Confirmado inspeccionando `/usr/share/kwin-wayland/scripts/desktopchangeosd` (mismo API, mismo layout).
- `kwin-script/contents/code/script.js` es una librería JS pura (`.pragma library`) importada desde `main.qml` con `import "script.js" as Engine`. Contiene solo funciones deterministas (cálculo de layout BSP recursivo balanceado, decisiones de creación/eliminación de escritorio) sin tocar la API de KWin — facilita testear la lógica en aislamiento en el futuro.
- El singleton QML `Workspace` (módulo `org.kde.kwin`) es el mismo `WorkspaceWrapper` de C++ que la API `javascript` expone como `workspace` (minúscula) — mismas propiedades/métodos (`windows`, `desktops`, `createDesktop(pos, name)`, `removeDesktop(desktop)`, `clientArea(...)`, señales `windowAdded`/`windowRemoved`/`currentDesktopChanged`).
- **AutoVirtualDesktop es edge-triggered:** se guarda el último conteo de ventanas por escritorio (`Map`) y solo se crea un escritorio nuevo al CRUZAR el umbral (4), no en cada evento mientras el escritorio siga por encima — evita spam de escritorios.

## HU-04 — Por qué NO existe un `dbus.qml` que registre `org.kde.KWin.KFlow` como servicio D-Bus real

Verificado en este sistema (`busctl --user list`, inspección de `/usr/lib64/qt6/qml/org/kde/kwin`): el sandbox de scripting de KWin (JS y QML) **no expone `QDBusConnection` ni ningún módulo QML de D-Bus**. Los servicios `org.kde.KWin.NightLight`, `HighlightWindow`, etc. son features nativas en C++ del propio KWin, no algo que un script en sandbox pueda registrar.

**Arquitectura real implementada (`kwin-script/contents/ui/dbus.qml`):**
1. El futuro Control Center (PyQt6, HU-05) debe ser quien posea el servicio D-Bus real `org.kde.KWin.KFlow` (usando `QtDBus`, sin sandbox).
2. Al recibir una llamada remota (setInnerGap, setOuterMargins, setProfile, toggleAutoTiling), el Control Center escribe en `kwinrc`: `kwriteconfig6 --file kwinrc --group Script-kflow --key InnerGap 8`.
3. Luego invoca `org.kde.KWin /KWin reconfigure` (método real, ya existente y confirmado activo en este sistema) para que KWin retransmita `Options.configChanged` a todos los scripts cargados.
4. `dbus.qml` escucha esa señal, relee la config desde disco (`KWin.readConfig`) y reaplica el tiling.

**Importante para HU-05:** el Control Center debe escribir en el grupo `Script-kflow` de `~/.config/kwinrc` (no en `~/.config/kflow/profiles.json` directamente para el motor en vivo) y llamar a `reconfigure` tras cada cambio. `profiles.json` puede seguir usándose como almacén de perfiles con nombre en el Control Center, pero al "aplicar" un perfil debe volcarse a `kwinrc`.
