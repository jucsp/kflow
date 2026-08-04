# 🌊 KFlow — Smart Dynamic Tiling & Auto-Desktop Engine for KDE Plasma 6

<p align="center">
  <img src="https://img.shields.io/badge/KDE_Plasma-6.0+-3B8EEA?style=for-the-badge&logo=kde&logoColor=white" alt="KDE Plasma 6">
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge" alt="License MIT">
  <img src="https://img.shields.io/badge/Platform-Fedora_%7C_Arch_%7C_Linux-blue?style=for-the-badge&logo=linux" alt="Linux">
  <img src="https://img.shields.io/badge/Python-3.11+-yellow?style=for-the-badge&logo=python&logoColor=white" alt="Python">
</p>

**KFlow** es un motor de gestión de ventanas en mosaico (Dynamic Tiling Window Manager) y creador de escritorios virtuales inteligentes diseñado desde cero para **KDE Plasma 6**. Combina la automatización de un tiling manager técnico (tipo i3/bspwm) con una experiencia de usuario (UX) visual, intuitiva y moderna.

---

## ✨ Características Principales (Key Features)

- 📐 **AutoTiling Dinámico en Vivo:** Posiciona y ajusta automáticamente las ventanas al abrir, cerrar o mover aplicaciones mediante un motor BSP balanceado de alto rendimiento.
- 🔄 **AutoVirtualDesktop:** Crea un nuevo escritorio virtual automáticamente cuando el activo alcanza su capacidad máxima y elimina escritorios vacíos sin dejar espacio desperdiciado.
- 🎨 **Gestor de Perfiles Visuales:** Diseña y guarda múltiples plantillas de mosaico (*Grid*, *Master + Stack*, *Columns*, *Ultrawide*) desde una app de control con vista previa gráfica.
- 🔲 **Gaps & Márgenes Independientes:** Controla dinámicamente la distancia entre ventanas (*Inner Gap*) y los márgenes de pantalla (*Top, Bottom, Left, Right Padding*) mediante sliders en tiempo real.
- 🎛️ **Centro de Control e Ícono en Tray:** App flotante en PyQt6 integrada con el tema oscuro de KDE, selector de perfiles OSD rápido y atajos de teclado sin conflictos.
- 📡 **Integración D-Bus & CLI:** Controla el estado, perfil y configuraciones de KFlow por línea de comandos o scripts personalizados (`kflow-cli`).

---

## 🛠️ Instalación Rápida

```bash
# Clonar el repositorio
git clone git@github.com:jucsp/kflow.git
cd kflow

# Compilar e instalar el paquete en KWin 6
make install
```

---

## 🩺 Diagnóstico y Logs en Vivo

KFlow imprime logs verbosos con prefijo `[KFLOW-GUI]` (Control Center) y `[KFLOW-KWIN]` (motor KWin) para diagnosticar problemas como "Aplicar ahora no aplica el retiling".

**Control Center** — ejecuta `main.py` desde una terminal y observa el stdout directamente:

```bash
python3 control-center/main.py
```

**Motor KWin** — sus logs (`console.log`) van al journal de systemd del proceso de KWin. Para verlos en vivo:

```bash
# Plasma Wayland
journalctl -f --user-unit=plasma-kwin_wayland | grep KFLOW

# Plasma X11
journalctl -f --user-unit=plasma-kwin_x11 | grep KFLOW

# Alternativa genérica si no se conoce la unidad exacta
journalctl -f | grep KFLOW
```

---

## 📄 Licencia
Este proyecto está distribuido bajo la licencia **MIT**. Consulta el archivo `LICENSE` para más detalles.
