#!/usr/bin/env bash
set -euo pipefail

APP_NAME="nanoharness"
APP_TITLE="nanoharness"
IDENTIFIER="com.ap.nanoharness"
VERSION="${VERSION:-0.0.0}"
BUILD_DIR="${BUILD_DIR:-dist/${APP_NAME}}"
PACKAGE_PROCESS_DIR="${PACKAGE_PROCESS_DIR:-package_process}"
OUT_DIR="${OUT_DIR:-${PACKAGE_PROCESS_DIR}/packages}"
PKGROOT="${PKGROOT:-${PACKAGE_PROCESS_DIR}/pkgroot}"
SCRIPTS_DIR="${SCRIPTS_DIR:-${PACKAGE_PROCESS_DIR}/pkg-scripts}"
INSTALL_SHARE_DIR="/usr/local/share/${APP_NAME}"
INSTALL_BIN_DIR="/usr/local/bin"
LAUNCHER_NAME="${LAUNCHER_NAME:-nanoharness}"
EXECUTABLE_NAME="${EXECUTABLE_NAME:-nanoharness}"

die() {
  printf 'error: %s\n' "$1" >&2
  exit 1
}

info() {
  printf '%s\n' "$1"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

main() {
  require_command pkgbuild

  [[ -d "${BUILD_DIR}" ]] || die "onedir build not found: ${BUILD_DIR}"
  [[ -x "${BUILD_DIR}/${EXECUTABLE_NAME}" ]] || die "executable not found or not executable: ${BUILD_DIR}/${EXECUTABLE_NAME}"

  rm -rf "${PKGROOT}" "${OUT_DIR}" "${SCRIPTS_DIR}"
  mkdir -p "${PKGROOT}${INSTALL_SHARE_DIR}" "${PKGROOT}${INSTALL_BIN_DIR}" "${OUT_DIR}" "${SCRIPTS_DIR}"

  info "Staging ${BUILD_DIR} into ${PKGROOT}${INSTALL_SHARE_DIR}"
  ditto "${BUILD_DIR}" "${PKGROOT}${INSTALL_SHARE_DIR}"

  info "Creating launcher at ${PKGROOT}${INSTALL_BIN_DIR}/${LAUNCHER_NAME}"
  cat > "${PKGROOT}${INSTALL_BIN_DIR}/${LAUNCHER_NAME}" <<EOF
#!/usr/bin/env bash
exec "${INSTALL_SHARE_DIR}/${EXECUTABLE_NAME}" "\$@"
EOF
  chmod 755 "${PKGROOT}${INSTALL_BIN_DIR}/${LAUNCHER_NAME}"

  info "Adding uninstaller to ${PKGROOT}${INSTALL_SHARE_DIR}/uninstall.sh"
  cp uninstall-nanoharness.sh "${PKGROOT}${INSTALL_SHARE_DIR}/uninstall.sh"
  chmod 755 "${PKGROOT}${INSTALL_SHARE_DIR}/uninstall.sh"

  info "Creating package install scripts"
  cat > "${SCRIPTS_DIR}/preinstall" <<EOF
#!/usr/bin/env bash
set -euo pipefail

rm -rf "${INSTALL_SHARE_DIR}"
rm -f "${INSTALL_BIN_DIR}/${LAUNCHER_NAME}"
EOF

  cat > "${SCRIPTS_DIR}/postinstall" <<EOF
#!/usr/bin/env bash
set -euo pipefail

chmod -R go+rX "${INSTALL_SHARE_DIR}"
chmod 755 "${INSTALL_SHARE_DIR}/${EXECUTABLE_NAME}"
chmod 755 "${INSTALL_SHARE_DIR}/uninstall.sh"
chmod 755 "${INSTALL_BIN_DIR}/${LAUNCHER_NAME}"
EOF

  chmod 755 "${SCRIPTS_DIR}/preinstall" "${SCRIPTS_DIR}/postinstall"

  local component_pkg="${OUT_DIR}/${APP_NAME}-${VERSION}-component.pkg"
  local unsigned_pkg="${OUT_DIR}/${APP_NAME}-${VERSION}.pkg"
  local final_pkg="${unsigned_pkg}"

  info "Building component package: ${component_pkg}"
  pkgbuild \
    --root "${PKGROOT}" \
    --scripts "${SCRIPTS_DIR}" \
    --identifier "${IDENTIFIER}" \
    --version "${VERSION}" \
    --install-location / \
    "${component_pkg}"

  if [[ -n "${INSTALLER_IDENTITY:-}" ]]; then
    require_command productbuild
    final_pkg="${OUT_DIR}/${APP_NAME}-${VERSION}-signed.pkg"
    info "Signing product package: ${final_pkg}"
    productbuild \
      --package "${component_pkg}" \
      --sign "${INSTALLER_IDENTITY}" \
      "${final_pkg}"
  else
    info "Creating unsigned product package: ${unsigned_pkg}"
    productbuild \
      --package "${component_pkg}" \
      "${unsigned_pkg}"
  fi

  if [[ -n "${NOTARY_PROFILE:-}" ]]; then
    require_command xcrun
    info "Submitting package for notarization with profile: ${NOTARY_PROFILE}"
    xcrun notarytool submit "${final_pkg}" \
      --keychain-profile "${NOTARY_PROFILE}" \
      --wait

    info "Stapling notarization ticket"
    xcrun stapler staple "${final_pkg}"
    xcrun stapler validate "${final_pkg}"
  else
    info "Skipping notarization because NOTARY_PROFILE is not set."
  fi

  info "Verifying package install assessment"
  spctl -a -vv -t install "${final_pkg}" || true

  info "Package ready: ${final_pkg}"
  info "Install test command: sudo installer -pkg '${final_pkg}' -target /"
  info "Uninstall command after install: sudo ${INSTALL_SHARE_DIR}/uninstall.sh"
}

main "$@"
