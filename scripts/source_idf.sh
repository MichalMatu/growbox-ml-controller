# Source ESP-IDF into the current shell:  source scripts/source_idf.sh
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "source scripts/source_idf.sh (do not execute)" >&2
  exit 1
fi

if [[ -n "${IDF_PATH:-}" ]] && command -v idf.py >/dev/null 2>&1; then
  return 0
fi

for candidate in "${IDF_EXPORT_SH:-}" "${HOME}/esp/esp-idf/export.sh" "${HOME}/esp-idf/export.sh"; do
  if [[ -n "${candidate}" && -f "${candidate}" ]]; then
    # shellcheck disable=SC1090
    source "${candidate}"
    return 0
  fi
done

echo "ESP-IDF not found — source export.sh or set IDF_PATH." >&2
return 1
