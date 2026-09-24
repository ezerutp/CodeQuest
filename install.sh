#!/usr/bin/env bash
# Instala CodeQuest para el usuario actual, sin tener que activar ningún entorno virtual.
#
#   ./install.sh               instala o actualiza (vuelve a ejecutarlo después de un git pull)
#   ./install.sh --ai          incluye el SDK de Anthropic para las funciones con IA
#   ./install.sh --editable    enlaza al código de este repositorio (para desarrollar)
#   ./install.sh --uninstall   quita el programa (tu progreso y tus conceptos se conservan)
#
# El programa vive en un entorno propio (~/.local/lib/codequest) y el comando en ~/.local/bin.
# Se pueden cambiar con CODEQUEST_HOME y CODEQUEST_BIN_DIR. Linux y macOS.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${CODEQUEST_HOME:-$HOME/.local/lib/codequest}"
BIN_DIR="${CODEQUEST_BIN_DIR:-$HOME/.local/bin}"
LAUNCHER="$BIN_DIR/codequest"
MIN_PYTHON="3.12"

with_ai=false
editable=false
uninstall=false
for arg in "$@"; do
    case "$arg" in
        --ai) with_ai=true ;;
        --editable) editable=true ;;
        --uninstall) uninstall=true ;;
        -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Opción desconocida: $arg (usa --help)" >&2; exit 2 ;;
    esac
done

info() { printf '\033[1;35m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

if $uninstall; then
    # Solo se borra lo que instaló este script: el enlace y su entorno. Nunca los datos del usuario.
    if [[ -L "$LAUNCHER" && "$(readlink "$LAUNCHER")" == "$APP_DIR/"* ]]; then
        rm "$LAUNCHER"
    fi
    if [[ -f "$APP_DIR/.codequest-install" ]]; then
        rm -rf "$APP_DIR"
    elif [[ -e "$APP_DIR" ]]; then
        fail "$APP_DIR no parece una instalación de CodeQuest; no lo borro."
    fi
    info "CodeQuest desinstalado. Tu progreso y tus conceptos siguen en su carpeta de datos."
    exit 0
fi

# Python 3.12 o superior: el primero que se encuentre.
python=""
for candidate in "${PYTHON:-}" python3.14 python3.13 python3.12 python3; do
    [[ -n "$candidate" ]] && command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" -c "import sys; sys.exit(sys.version_info < (${MIN_PYTHON/./, }))" 2>/dev/null; then
        python="$candidate"
        break
    fi
done
[[ -n "$python" ]] || fail "Necesito Python $MIN_PYTHON o superior. Instálalo (p. ej. 'sudo dnf install python3') y vuelve a probar."
"$python" -c "import venv, ensurepip" 2>/dev/null \
    || fail "Falta el módulo venv de Python (en Debian/Ubuntu: sudo apt install python3-venv)."

if [[ -e "$APP_DIR" && ! -f "$APP_DIR/.codequest-install" ]]; then
    fail "$APP_DIR ya existe y no es una instalación de CodeQuest. Usa CODEQUEST_HOME para elegir otra ruta."
fi

info "Usando $("$python" --version) ($(command -v "$python"))"
if [[ ! -x "$APP_DIR/bin/python" ]]; then
    info "Creando el entorno en $APP_DIR"
    "$python" -m venv "$APP_DIR"
    touch "$APP_DIR/.codequest-install"
fi

target="$REPO_DIR"
$with_ai && target="$REPO_DIR[ai]"
info "Instalando CodeQuest y sus dependencias (puede tardar la primera vez)…"
"$APP_DIR/bin/python" -m pip install --quiet --upgrade pip
if $editable; then
    "$APP_DIR/bin/python" -m pip install --quiet --editable "$target"
else
    "$APP_DIR/bin/python" -m pip install --quiet --upgrade "$target"
    # Tras un git pull la versión puede ser la misma: sin esto pip no copiaría el código nuevo.
    "$APP_DIR/bin/python" -m pip install --quiet --no-deps --force-reinstall "$REPO_DIR"
fi

mkdir -p "$BIN_DIR"
ln -sfn "$APP_DIR/bin/codequest" "$LAUNCHER"
version="$("$APP_DIR/bin/python" -c 'import codequest; print(codequest.__version__)')"
info "CodeQuest $version instalado: $LAUNCHER"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        echo
        echo "  $BIN_DIR no está en tu PATH. Añádelo a tu ~/.bashrc o ~/.zshrc:"
        echo "      export PATH=\"$BIN_DIR:\$PATH\""
        ;;
esac
echo
echo "  Úsalo desde cualquier proyecto:   cd mi-proyecto-spring && codequest"
$with_ai || echo "  Para las funciones con IA:       ./install.sh --ai   (y define ANTHROPIC_API_KEY)"
