#!/usr/bin/env bash
# Lanzador de la calculadora de link budget (LINK_BUDGET/app.py).
# Pensado para invocarse desde un ícono de escritorio (.desktop) o a mano.
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if ! python3 -c "import streamlit" 2>/dev/null; then
    echo "Primera vez: instalando dependencias (streamlit, matplotlib, pandas)..."
    pip install -r requirements.txt
fi

echo "Iniciando la calculadora de link budget — se abrirá en el navegador..."
echo "Para cerrarla, vuelve a esta ventana y presiona Ctrl+C."
streamlit run app.py
