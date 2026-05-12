#!/usr/bin/env bash
set -euo pipefail

APP_NAME="nanoharness"
COMMAND_NAME="nanoharness"
CANARY_COMMAND_NAME="nanoharness_dev"
LOCAL_INSTALL_DIR="${HOME}/.local/bin"
GLOBAL_INSTALL_DIR="/usr/local/bin"
APP_DATA_DIR="${NANOHARNESS_HOME:-${HOME}/.nanoharness}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

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

find_included_binary() {
  local candidates=(
    "${SCRIPT_DIR}/${COMMAND_NAME}"
    "${SCRIPT_DIR}/nanoharness"
    "${SCRIPT_DIR}/${CANARY_COMMAND_NAME}"
    "${SCRIPT_DIR}/dist/${COMMAND_NAME}"
    "${SCRIPT_DIR}/dist/nanoharness"
    "${SCRIPT_DIR}/dist/${CANARY_COMMAND_NAME}"
    "${LOCAL_INSTALL_DIR}/${CANARY_COMMAND_NAME}"
    "${GLOBAL_INSTALL_DIR}/${CANARY_COMMAND_NAME}"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -f "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  return 1
}

find_recoverable_temp_binary() {
  local candidate
  for candidate in "${LOCAL_INSTALL_DIR}/.${COMMAND_NAME}.tmp."* "${GLOBAL_INSTALL_DIR}/.${COMMAND_NAME}.tmp."*; do
    if [[ -f "${candidate}" && -s "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  return 1
}

download_binary() {
  local url="$1"
  local destination="$2"

  if command -v curl >/dev/null 2>&1; then
    curl --fail --location --silent --show-error --output "${destination}" "${url}"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "${destination}" "${url}"
  else
    die "curl or wget is required to download ${APP_NAME}"
  fi
}

install_or_update() {
  local install_dir
  local install_path

  install_dir="$(choose_install_dir)"
  install_path="${install_dir}/${COMMAND_NAME}"

  info "Installing to ${install_path}"
  mkdir -p "${install_dir}"
  [[ -d "${install_dir}" ]] || die "install path parent is not a directory: ${install_dir}"
  [[ ! -e "${install_path}" || -f "${install_path}" ]] || die "target exists but is not a file: ${install_path}"

  local tmp_path
  tmp_path="$(mktemp "${install_dir}/.${COMMAND_NAME}.tmp.XXXXXX")"
  trap 'rm -f "${tmp_path}"' RETURN

  if [[ -n "${NANOHARNESS_BINARY_URL:-}" ]]; then
    info "Downloading ${APP_NAME} from ${NANOHARNESS_BINARY_URL}"
    download_binary "${NANOHARNESS_BINARY_URL}" "${tmp_path}"
  else
    local source_path="${NANOHARNESS_BINARY_PATH:-}"
    if [[ -z "${source_path}" ]]; then
      source_path="$(find_included_binary || true)"
    fi
    if [[ -z "${source_path}" ]]; then
      source_path="$(find_recoverable_temp_binary || true)"
      if [[ -n "${source_path}" ]]; then
        info "Recovering install from temporary binary: ${source_path}"
      fi
    fi
    if [[ -z "${source_path}" && -f "${install_path}" ]]; then
      chmod 755 "${install_path}"
      info "${APP_NAME} is already installed at ${install_path}"
      info "No bundled update binary was found next to the installer."
      info "To update, run this installer from a release folder containing the binary, or set NANOHARNESS_BINARY_PATH or NANOHARNESS_BINARY_URL."
      warn_path "${install_dir}"
      return 0
    fi
    [[ -n "${source_path}" ]] || die "binary not found next to installer or at ${install_path}. Set NANOHARNESS_BINARY_PATH=/path/to/binary or NANOHARNESS_BINARY_URL=https://..."
    [[ -f "${source_path}" ]] || die "binary does not exist: ${source_path}"

    if [[ "$(cd -- "$(dirname -- "${source_path}")" && pwd)/$(basename -- "${source_path}")" == "${install_path}" ]]; then
      chmod 755 "${install_path}"
      info "${APP_NAME} is already installed at ${install_path}"
      warn_path "${install_dir}"
      return 0
    fi

    cp "${source_path}" "${tmp_path}"
  fi

  [[ -s "${tmp_path}" ]] || die "binary is empty or download failed"
  chmod 755 "${tmp_path}"
  mv -f "${tmp_path}" "${install_path}"
  trap - RETURN

  info "Installed ${APP_NAME} to ${install_path}"
  warn_path "${install_dir}"
}

warn_path() {
  local install_dir="$1"
  case ":${PATH}:" in
    *":${install_dir}:"*) ;;
    *)
      info ""
      info "${install_dir} is not currently in PATH. Add this to your shell config:"
      info "  export PATH=\"${install_dir}:\$PATH\""
      ;;
  esac
}

choose_install_dir() {
  local choice
  printf 'Choose install location:\n' >&2
  printf '1) Local user install: %s\n' "${LOCAL_INSTALL_DIR}/${COMMAND_NAME}" >&2
  printf '2) Global install: %s\n' "${GLOBAL_INSTALL_DIR}/${COMMAND_NAME}" >&2
  printf '   Global install may require admin permissions depending on your machine.\n' >&2
  read -r -p "Choose 1 or 2: " choice

  case "${choice}" in
    1) printf '%s\n' "${LOCAL_INSTALL_DIR}" ;;
    2) printf '%s\n' "${GLOBAL_INSTALL_DIR}" ;;
    *) die "invalid install location: ${choice}" ;;
  esac
}

delete_install() {
  local targets=()
  local path

  for path in \
    "${LOCAL_INSTALL_DIR}/${COMMAND_NAME}" \
    "${LOCAL_INSTALL_DIR}/${CANARY_COMMAND_NAME}" \
    "${GLOBAL_INSTALL_DIR}/${COMMAND_NAME}" \
    "${GLOBAL_INSTALL_DIR}/${CANARY_COMMAND_NAME}"; do
    if [[ -e "${path}" ]]; then
      [[ -f "${path}" ]] || die "install target exists but is not a file: ${path}"
      targets+=("${path}")
    fi
  done

  if [[ ${#targets[@]} -eq 0 ]]; then
    info "No installed stable or canary binary found in local or global paths."
  else
    info "The following installed binaries will be deleted:"
    for path in "${targets[@]}"; do
      info "  ${path}"
    done
    if confirm "Delete these binaries?"; then
      for path in "${targets[@]}"; do
        rm -f "${path}"
        info "Deleted ${path}"
      done
    else
      info "Kept installed binaries."
    fi
  fi

  if [[ -e "${APP_DATA_DIR}" ]]; then
    [[ -d "${APP_DATA_DIR}" ]] || die "app data path exists but is not a directory: ${APP_DATA_DIR}"
    if confirm "Delete app data at ${APP_DATA_DIR}? This removes config, sessions, and prompt history."; then
      rm -rf "${APP_DATA_DIR}"
      info "Deleted ${APP_DATA_DIR}"
    else
      info "Kept ${APP_DATA_DIR}"
    fi
  else
    info "No app data found at ${APP_DATA_DIR}"
  fi
}

print_menu() {
  info "${APP_NAME} installer"
  info ""
  info "1) Install or update ${COMMAND_NAME}"
  info "2) Delete ${COMMAND_NAME}/${CANARY_COMMAND_NAME} from local/global paths and optionally delete ${APP_DATA_DIR}"
  info ""
}

main() {
  local choice
  print_menu
  read -r -p "Choose 1 or 2: " choice

  case "${choice}" in
    1) install_or_update ;;
    2) delete_install ;;
    *) die "invalid choice: ${choice}" ;;
  esac
}

main "$@"
