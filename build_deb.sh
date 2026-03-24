#!/bin/bash
# build_deb.sh — Construit le paquet Debian de PDF-EPUBOR
set -e

VERSION="1.3.0"
PKG_NAME="pdf-epubor_${VERSION}_all"
BUILD_DIR="/tmp/${PKG_NAME}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Nettoyage du répertoire de build..."
rm -rf "${BUILD_DIR}"

echo "==> Copie de la structure packaging/..."
cp -r "${SCRIPT_DIR}/packaging" "${BUILD_DIR}"

echo "==> Copie des fichiers de l'application..."
APP_DEST="${BUILD_DIR}/usr/lib/pdf-epubor"
mkdir -p "${APP_DEST}"
cp "${SCRIPT_DIR}/main.py"          "${APP_DEST}/"
cp "${SCRIPT_DIR}/requirements.txt" "${APP_DEST}/"
cp -r "${SCRIPT_DIR}/core"          "${APP_DEST}/"
cp -r "${SCRIPT_DIR}/ui"            "${APP_DEST}/"

echo "==> Suppression des fichiers bytecode Python..."
find "${APP_DEST}" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "${APP_DEST}" -name "*.pyc" -delete

echo "==> Application des permissions..."
chmod 755 "${BUILD_DIR}/DEBIAN/postinst"
chmod 755 "${BUILD_DIR}/DEBIAN/prerm"
chmod 755 "${BUILD_DIR}/usr/bin/pdf-epubor"
find "${BUILD_DIR}/usr/lib/pdf-epubor" -name "*.py" -exec chmod 644 {} \;

echo "==> Construction du paquet .deb..."
mkdir -p "${SCRIPT_DIR}/dist"
dpkg-deb --build --root-owner-group "${BUILD_DIR}" \
    "${SCRIPT_DIR}/dist/${PKG_NAME}.deb"

SIZE=$(du -sh "${SCRIPT_DIR}/dist/${PKG_NAME}.deb" | cut -f1)
echo ""
echo "✅ Paquet construit : dist/${PKG_NAME}.deb (${SIZE})"
