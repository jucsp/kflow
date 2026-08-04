# Tablero de Sprint — KFlow

## Sprint 1: Fundamentos y Motor Core

| ID | Tarea / Historia | Responsable | Estado |
|---|---|---|---|
| HU-01 | Estructura de proyecto, `Makefile` y `metadata.json` | Claude (PM) | 🟢 Finalizado |
| HU-02 | Core Engine: Geometría de tiling + Gaps + Márgenes + layout_tree | Claude (Dev) | 🟢 Finalizado |
| HU-03 | Engine: AutoVirtualDesktop dinámico | Claude (Dev) | 🟢 Finalizado |
| HU-04 | Interfaz DBus KWin + bridge kwinrc/reconfigure | Claude (Dev) | 🟢 Finalizado |
| HU-05 | GUI Control Center + Editor Visual Interactivo (System Tray, PyQt6) | Claude (PM/Dev) | 🟢 Finalizado |
| HU-06 | Diseñador y gestor de perfiles visuales (JSON + layout_tree) | Claude (PM/Dev) | 🟢 Finalizado |
| HU-07 | Suite de pruebas unitarias (48 tests) y make test | Claude (PM/Dev) | 🟢 Finalizado |

## Sprint 1 cerrado — v0.2

**Mejoras v0.2:**
- Editor visual interactivo de mosaicos en `preview_widget.py`: clic para seleccionar, dividir ↕/↔, eliminar recuadro, arrastrar divisores, cargar plantillas.
- `layout_tree` serializado a JSON en `kwinrc` sección `[Script-kflow]` via `apply_and_reconfigure`.
- Motor KWin (`script.js` + `main.qml`) aplica `layout_tree` personalizado cuando coincide con el número de ventanas; fallback a BSP automático.
- `dbus.qml` lee `LayoutTree` desde kwinrc vía `KWin.readConfig` + `JSON.parse`.
- 48 tests unitarios en `tests/test_kflow.py`.
