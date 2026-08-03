## KFlow — Makefile
## Motor de tiling dinámico (KWin Script) + Control Center (PyQt6) para KDE Plasma 6

PKG_ID       := kflow
KWIN_SRC_DIR := kwin-script
CC_SRC_DIR   := control-center
KPACKAGETOOL := kpackagetool6
PYTHON       := python3

.PHONY: all test install uninstall clean help

all: help

help:
	@echo "Targets disponibles:"
	@echo "  make test      - Ejecuta pruebas unitarias del proyecto"
	@echo "  make install   - Instala el KWin Script en el sistema (kpackagetool6)"
	@echo "  make uninstall - Desinstala el KWin Script del sistema"
	@echo "  make clean     - Limpia artefactos temporales y de compilación"

test:
	@echo "==> Ejecutando suite de pruebas KFlow"
	@if [ -d tests ]; then \
		$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v; \
	else \
		echo "No se encontró el directorio 'tests/' todavía (pendiente en HU-07)."; \
	fi

install:
	@echo "==> Instalando KWin Script '$(PKG_ID)'"
	@if $(KPACKAGETOOL) --type KWin/Script -l 2>/dev/null | grep -q "$(PKG_ID)"; then \
		$(KPACKAGETOOL) --type KWin/Script -u $(KWIN_SRC_DIR); \
	else \
		$(KPACKAGETOOL) --type KWin/Script -i $(KWIN_SRC_DIR); \
	fi
	@echo "==> Instalación completada. Habilita 'KFlow' en Configuración del Sistema > Ventanas > Script de KWin"

uninstall:
	@echo "==> Desinstalando KWin Script '$(PKG_ID)'"
	@$(KPACKAGETOOL) --type KWin/Script -r $(PKG_ID) || true

clean:
	@echo "==> Limpiando artefactos temporales"
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@rm -rf build/ dist/ *.egg-info
	@echo "Limpieza completada."
