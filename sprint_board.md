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
| HU-07 | Suite de pruebas unitarias (64 tests) y make test | Claude (PM/Dev) | 🟢 Finalizado |

## Sprint 1 cerrado — v0.2.1

**Mejoras v0.2.1 (bugfixes críticos):**
- **BUGFIX #1 — Botón "Aplicar ahora"**: Creado `kwin-script/contents/config/main.xml` requerido por KWin 6 para `KWin.readConfig()`. Las 8 claves (InnerGap, OuterMarginTop/Bottom/Left/Right, AutoTilingEnabled, ActiveProfile, LayoutTree) ahora se leen correctamente desde `[Script-kflow]` en `kwinrc`. `qdbus-qt6` priorizado en `find_qdbus_binary()`.
- **BUGFIX #2 — Hit-testing recursivo**: Corregido `_resolve_path()` en `preview_widget.py` — antes devolvía `(padre, key)` pero los callers (`_split_selected`, `delete_selected`, `_update_drag`) lo usaban como si devolviera el nodo real. Agregado `_get_node()` que sí devuelve el nodo real. División recursiva ilimitada verificada.
- **BUGFIX #3 — Eliminación de mosaicos**: `delete_selected()` reescrito usando `_get_node()` para obtener el hermano real y colapsar la división correctamente (reemplaza el padre por el hermano superviviente en el abuelo). Nuevas pruebas unitarias (`LayoutTreeDeleteLeafTest`, 6 tests).
- **BUGFIX #4 — Redimensionamiento con slider**: Agregado slider "Ratio" (5%–95%) en la GUI del Control Center, conectado a `preview_widget.selectionChanged` y `set_selected_node_ratio()`. El arrastre de divisores con mouse ya funcionaba (cursor `SizeHorCursor`/`SizeVerCursor`), ahora complementado con control numérico preciso.
- **Tests**: 64 tests unitarios (48 originales + 16 nuevos para `get_node_at`, `set_node_at`, `delete_leaf_at`).

**Mejoras v0.2:**
- Editor visual interactivo de mosaicos en `preview_widget.py`: clic para seleccionar, dividir ↕/↔, eliminar recuadro, arrastrar divisores, cargar plantillas.
- `layout_tree` serializado a JSON en `kwinrc` sección `[Script-kflow]` via `apply_and_reconfigure`.
- Motor KWin (`script.js` + `main.qml`) aplica `layout_tree` personalizado cuando coincide con el número de ventanas; fallback a BSP automático.
- `dbus.qml` lee `LayoutTree` desde kwinrc vía `KWin.readConfig` + `JSON.parse`.
