# Product Backlog — KFlow (KDE Plasma 6)

## Epics & User Stories

### Epic 1: Infraestructura & Packaging (PM / QA - Claude)
- **HU-01:** Crear estructura del repositorio, `Makefile` con objetivos de build/test/install, y `metadata.json` para paquete KWin 6. [Estado: Finalizado] [Responsable: Claude PM]

### Epic 2: Motor KWin & Dynamic AutoTiling (Dev - DeepSeek)
- **HU-02:** Diseñar algoritmo de tiling dinámico con Inner Gaps y Outer Padding (Top, Bottom, Left, Right). [Estado: Finalizado] [Responsable: Claude Dev] — `kwin-script/contents/code/script.js` (BSP recursivo balanceado) + `contents/ui/main.qml`.
- **HU-03:** Implementar AutoVirtualDesktop (creación/eliminación dinámica de escritorios virtuales en KWin 6). [Estado: Finalizado] [Responsable: Claude Dev] — lógica edge-triggered (crea al cruzar el umbral, no en cada evento) en `main.qml::manageDesktops()`.
- **HU-04:** Exponer interfaz D-Bus en KWin Script (`org.kde.KWin.KFlow`) para control remoto de perfiles y estados. [Estado: Finalizado con nota técnica] [Responsable: Claude Dev] — ver `technical_memory.md`: el sandbox de KWin no permite registrar un servicio D-Bus propio; se implementó el bridge real (kwinrc + `org.kde.KWin/KWin.reconfigure`) en `contents/ui/dbus.qml`, listo para que HU-05 (Control Center) posea el servicio D-Bus real.

### Epic 3: Control Center & Visual Profile Editor (PM / Dev)
- **HU-05:** Construir interfaz GUI moderna en PyQt6 con vista previa en vivo, sliders de Gaps y System Tray. [Estado: Finalizado] [Responsable: Claude PM/Dev] — `control-center/main.py`: ventana principal con Dark Mode (Breeze Dark), sliders Inner Gap (0-40 px), Outer Padding independiente (T/B/L/R 0-60 px), toggle AutoVirtualDesktop, selector de perfiles, vista previa interactiva, System Tray, y conexión con `dbus_service.py`.
- **HU-06:** Diseñador y gestor de perfiles visuales guardados en JSON. [Estado: Finalizado] [Responsable: Claude PM/Dev] — Perfiles predefinidos Grid, Master+Stack, 50/50, Columns en `main.py::BUILTIN_PROFILES`; `profile_manager.py` con CRUD completo; semillado automático de builtins en `~/.config/kflow/profiles.json`.

### Epic 4: QA, Testing y Empaquetado (PM / QA - Claude)
- **HU-07:** Implementar suite de pruebas unitarias (`make test`) y script de instalación/desinstalación `install.sh`. [Estado: Finalizado] [Responsable: Claude PM/Dev] — `tests/test_kflow.py` con 20 tests cubriendo tiling_preview, profile_manager, dbus_service helpers y sintaxis JS; `make test` ejecuta `python3 -m unittest discover`.
