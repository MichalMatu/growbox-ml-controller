#!/usr/bin/env bash
# Shallow-clone greenhouse research sources into third_party/.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
TP="${ROOT}/third_party"
mkdir -p "${TP}/papers"

clone_or_update() {
  local url="$1"
  local dest="$2"
  if [[ -d "${dest}/.git" ]]; then
    echo "==> update ${dest}"
    git -C "${dest}" pull --ff-only || true
  else
    echo "==> clone ${url} -> ${dest}"
    rm -rf "${dest}"
    git clone --depth 1 "${url}" "${dest}"
  fi
}

# Greenhouse / horticulture physics
clone_or_update "https://github.com/SamuelMallick/mpcrl-greenhouse.git" \
  "${TP}/mpcrl-greenhouse"
clone_or_update "https://github.com/EECi/GES.git" \
  "${TP}/GES"

# Thermal modeling (buildings / LPTN / neural) — methods transferable to growbox
clone_or_update "https://github.com/steffenschroe/Thermca.git" \
  "${TP}/Thermca"
clone_or_update "https://github.com/wkirgsn/thermal-nn.git" \
  "${TP}/thermal-nn"
clone_or_update "https://github.com/NatLabRockies/OCHRE.git" \
  "${TP}/OCHRE"
clone_or_update "https://github.com/EURAC-EEBgroup/pyBuildingEnergy.git" \
  "${TP}/pyBuildingEnergy"

PDF="${TP}/papers/igrow-2107.05464.pdf"
if [[ ! -f "${PDF}" ]]; then
  echo "==> download iGrow arXiv PDF"
  curl -fsSL "https://arxiv.org/pdf/2107.05464.pdf" -o "${PDF}"
else
  echo "==> keep existing ${PDF}"
fi

echo "done. trees:"
du -sh \
  "${TP}/mpcrl-greenhouse" "${TP}/GES" \
  "${TP}/Thermca" "${TP}/thermal-nn" "${TP}/OCHRE" "${TP}/pyBuildingEnergy" \
  "${TP}/papers" 2>/dev/null || true
