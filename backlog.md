# Product Backlog — KFlow (KDE Plasma 6)

> ⚠️ **ESTADO DEL PROYECTO:** DESARROLLO ABANDONADO HASTA NUEVO AVISO.

## Epics & User Stories

### Epic 1: Infraestructura & Packaging (PM / QA - Claude)
- **HU-01:** Crear estructura del repositorio, `Makefile` con objetivos de build/test/install, y `metadata.json` para paquete KWin 6. [Estado: Finalizado] [Responsable: Claude PM]

### Epic 2: Motor KWin & Dynamic AutoTiling (Dev - DeepSeek)
- **HU-02:** Diseñar algoritmo de tiling dinámico con Inner Gaps y Outer Padding (Top, Bottom, Left, Right). [Estado: Finalizado] [Responsable: Claude Dev] — `kwin-script/contents/code/script.js` (BSP recursivo balanceado) + `contents/ui/main.qml`.
- **HU-03:** Implementar AutoVirtualDesktop (creación/eliminación dinámica de escritorios virtuales en KWin 6). [Estado: Finalizado] [Responsable: Claude Dev] — lógica edge-triggered (crea al cruzar el umbral, no en cada evento) en `main.qml::manageDesktops()`.
- **HU-04:** Exponer interfaz D-Bus en KWin Script (`org.kde.KWin.KFlow`) para control remoto de perfiles y estados. [Estado: Finalizado con nota técnica] [Responsable: Claude Dev] — ver `technical_memory.md`: el sandbox de KWin no permite registrar un servicio D-Bus propio; se implementó el bridge real (kwinrc + `org.kde.KWin/KWin.reconfigure`) en `contents/ui/dbus.qml`, listo para que HU-05 (Control Center) posea el servicio D-Bus real.

### Epic 3: Control Center & Visual Profile Editor (PM / Dev)
- **HU-05:** Construir interfaz GUI moderna en PyQt6 con vista previa en vivo, sliders de Gaps y System Tray. [Estado: Finalizado] [Responsable: Claude PM/Dev] — `control-center/main.py`: Dark Mode, sliders, toggle AVD, System Tray. **v0.2: Editor visual interactivo** en `control-center/ui/preview_widget.py` con clic para seleccionar, dividir vertical/horizontal, eliminar recuadro, arrastrar divisores, y cargar plantillas predefinidas (Grid 2x2, Master+Stack, 50/50, Columns). Botones de acción integrados debajo del preview.
- **HU-06:** Diseñador y gestor de perfiles visuales guardados en JSON. [Estado: Finalizado] [Responsable: Claude PM/Dev] — Perfiles predefinidos con `layout_tree`; `profile_manager.py` con CRUD + soporte de árbol de layout; `apply_and_reconfigure` serializa `LayoutTree` a JSON en `kwinrc` sección `[Script-kflow]`.

### Epic 4: QA, Testing y Empaquetado (PM / QA - Claude)
- **HU-07:** Implementar suite de pruebas unitarias (`make test`) y script de instalación/desinstalación `install.sh`. [Estado: Finalizado] [Responsable: Claude PM/Dev] — `tests/test_kflow.py` con **64 tests**: tiling_preview (17), layout_tree (14), tree_manipulation (16), profile_manager (11), dbus_service (5), sintaxis JS (1).

## v0.2.1 — Bugfixes críticos (2025)
- **BUGFIX #1 (Aplicar ahora):** Creado `kwin-script/contents/config/main.xml` para KWin 6. `qdbus-qt6` priorizado en `find_qdbus_binary()`.
- **BUGFIX #2 (Hit-testing recursivo):** `_resolve_path()` vs `_get_node()` corregido en `preview_widget.py`. División recursiva ilimitada.
- **BUGFIX #3 (Eliminar mosaicos):** `delete_selected()` reescrito con `_get_node()`. Colapso correcto del split.
- **BUGFIX #4 (Slider ratio):** Slider "Ratio" (5%–95%) en GUI + `set_selected_node_ratio()` en preview_widget. Tests: `LayoutTreeGetNodeTest` (7), `LayoutTreeSetNodeTest` (3), `LayoutTreeDeleteLeafTest` (6).
