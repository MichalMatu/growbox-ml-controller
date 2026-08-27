from pathlib import Path

path = Path("tools/ml/run_dagger_overnight.py")
text = path.read_text(encoding="utf-8")
text = text.replace("import shutil\n", "")
old = '''def _copy_model(src_weights: Path, src_metadata: Path, dst_weights: Path, dst_metadata: Path) -> None:\n    dst_weights.parent.mkdir(parents=True, exist_ok=True)\n    shutil.copy2(src_weights, dst_weights)\n    shutil.copy2(src_metadata, dst_metadata)\n'''
new = '''def _copy_model(src_weights: Path, src_metadata: Path, dst_weights: Path, dst_metadata: Path) -> None:\n    portable = load_portable_model(src_weights, src_metadata)\n    save_portable_model(portable, dst_weights, dst_metadata)\n'''
if old not in text:
    raise SystemExit("expected _copy_model implementation not found")
path.write_text(text.replace(old, new), encoding="utf-8")
print("STAGE10_MODEL_COPY_METADATA_PATCH_APPLIED")
