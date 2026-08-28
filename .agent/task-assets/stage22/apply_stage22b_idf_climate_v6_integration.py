from pathlib import Path

path = Path("lib/environment_control/CMakeLists.txt")
text = path.read_text(encoding="utf-8")
old = '''  SRCS
    "src/EnvironmentController.cpp"
    "src/EnvironmentTypes.cpp"
    "src/FeatureEncoder.cpp"
    "src/ModelRuntime.cpp"
    "src/SafetySupervisor.cpp"
'''
new = '''  SRCS
    "src/EnvironmentController.cpp"
    "src/EnvironmentTypes.cpp"
    "src/FeatureEncoder.cpp"
    "src/ModelRuntime.cpp"
    "src/SafetySupervisor.cpp"
    "src/climate/ClimateControlLoop.cpp"
    "src/climate/ClimateFeatureEncoder.cpp"
    "src/climate/ClimateRuntimeController.cpp"
    "src/climate/ClimateTrendEstimator.cpp"
'''
if old not in text:
    raise SystemExit("expected environment_control SRCS block not found")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
