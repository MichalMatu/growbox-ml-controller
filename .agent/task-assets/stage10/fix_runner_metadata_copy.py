from pathlib import Path

path = Path("tools/ml/run_dagger_overnight.py")
text = path.read_text(encoding="utf-8")
old = '''def _copy_model(src_weights: Path, src_metadata: Path, dst_weights: Path, dst_metadata: Path) -> None:\n    dst_weights.parent.mkdir(parents=True, exist_ok=True)\n    shutil.copy2(src_weights, dst_weights)\n    shutil.copy2(src_metadata, dst_metadata)\n'''
new = '''def _copy_model(src_weights: Path, src_metadata: Path, dst_weights: Path, dst_metadata: Path) -> None:\n    dst_weights.parent.mkdir(parents=True, exist_ok=True)\n    shutil.copy2(src_weights, dst_weights)\n    metadata = json.loads(src_metadata.read_text(encoding="utf-8"))\n    metadata["weights_file"] = dst_weights.name\n    dst_metadata.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\\n", encoding="utf-8")\n'''
if old not in text:
    raise SystemExit("expected _copy_model block not found")
path.write_text(text.replace(old, new), encoding="utf-8")
print("STAGE10_METADATA_COPY_FIX_APPLIED")
