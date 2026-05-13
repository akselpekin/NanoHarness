#!/usr/bin/env bash
set -euo pipefail

APP_NAME="nanoharness"
IDENTIFIER="com.ap.nanoharness"
INSTALL_SHARE_DIR="/usr/local/share/nanoharness"
INSTALL_BIN_PATH="/usr/local/bin/nanoharness"

die() {
  printf 'error: %s\n' "$1" >&2
  exit 1
}

info() {
  printf '%s\n' "$1"
}

confirm() {
  local prompt="$1"
  local answer
  read -r -p "${prompt} [y/N]: " answer
  case "${answer}" in
    y|Y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

console_user_home() {
  local console_user
  console_user="$(stat -f '%Su' /dev/console 2>/dev/null || true)"
  if [[ -z "${console_user}" || "${console_user}" == "root" ]]; then
    return 1
  fi
  dscl . -read "/Users/${console_user}" NFSHomeDirectory 2>/dev/null | awk '{print $2}'
}

main() {
  if [[ "${EUID}" -ne 0 ]]; then
    die "global uninstall requires sudo. Run: sudo $0"
  fi

  info "${APP_NAME} uninstaller"
  info ""
  info "This will remove the global installation:"
  info "  ${INSTALL_BIN_PATH}"
  info "  ${INSTALL_SHARE_DIR}"
  info ""
  info "It will not delete user config, sessions, or prompt history unless you confirm that separately."
  info ""

  if ! confirm "Continue uninstalling ${APP_NAME}?"; then
    info "Cancelled."
    exit 0
  fi

  rm -f "${INSTALL_BIN_PATH}"
  rm -rf "${INSTALL_SHARE_DIR}"
  info "Removed global installation."

  if pkgutil --pkg-info "${IDENTIFIER}" >/dev/null 2>&1; then
    pkgutil --forget "${IDENTIFIER}" >/dev/null
    info "Forgot package receipt: ${IDENTIFIER}"
  fi

  local user_home=""
  local data_dir=""
  user_home="$(console_user_home || true)"
  if [[ -n "${user_home}" ]]; then
    data_dir="${user_home}/.nanoharness"
    if [[ -e "${data_dir}" ]]; then
      [[ -d "${data_dir}" ]] || die "app data path exists but is not a directory: ${data_dir}"
      info ""
      info "User data found:"
      info "  ${data_dir}"
      if confirm "Delete user data? This removes config, sessions, and prompt history."; then
        rm -rf "${data_dir}"
        info "Deleted user data."
      else
        info "Kept user data."
      fi
    else
      info "No user data found at ${data_dir}"
    fi
  else
    info "Could not determine console user home. User data was not checked."
  fi
}

main "$@"
