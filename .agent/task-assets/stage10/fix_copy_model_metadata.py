from pathlib import Path

path = Path("tools/ml/run_dagger_overnight.py")
text = path.read_text(encoding="utf-8")
old = '''def _copy_model(src_weights: Path, src_metadata: Path, dst_weights: Path, dst_metadata: Path) -> None:
    dst_weights.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_weights, dst_weights)
    shutil.copy2(src_metadata, dst_metadata)
'''
new = '''def _copy_model(src_weights: Path, src_metadata: Path, dst_weights: Path, dst_metadata: Path) -> None:
    dst_weights.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_weights, dst_weights)
    payload = json.loads(src_metadata.read_text(encoding="utf-8"))
    payload["weights_file"] = dst_weights.name
    dst_metadata.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\\n",
        encoding="utf-8",
    )
'''
if old not in text:
    raise SystemExit("copy-model block not found")
path.write_text(text.replace(old, new), encoding="utf-8")
print("STAGE10_COPY_MODEL_METADATA_FIX_APPLIED")
