#!/usr/bin/env python3
from pathlib import Path
root=Path.cwd()
path=root/'.pre-commit-config.yaml'
text=path.read_text(encoding='utf-8')
old='exclude: ^lib/environment_control/src/(generated/|EnvironmentSchema.*\\.h)'
new='exclude: ^lib/environment_control/src/(generated/|EnvironmentSchema.*\\.h|climate/ClimateContract\\.h)'
if old not in text: raise SystemExit('clang-format pre-commit anchor not found')
text=text.replace(old,new)
old='files: ^(tools/schema/|schemas/environment-controller\\.json|lib/environment_control/src/EnvironmentSchema\\.h)'
new='files: ^(tools/schema/|schemas/environment-controller(?:\\.v6)?\\.json|lib/environment_control/src/EnvironmentSchema\\.h|lib/environment_control/src/climate/ClimateContract\\.h)'
if old not in text: raise SystemExit('schema hook trigger anchor not found')
path.write_text(text.replace(old,new),encoding='utf-8')
print('pre-commit climate v6 hygiene rules updated')
