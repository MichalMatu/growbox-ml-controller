from pathlib import Path

path = Path('test/host/CMakeLists.txt')
text = path.read_text()
old = '''add_executable(
  stage27_schedule_profile_tests
  "${PROJECT_ROOT}/test/test_stage27_schedule_profile/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/Stage27ScheduleProfile.cpp"
)
'''
new = '''add_executable(
  stage27_schedule_profile_tests
  "${PROJECT_ROOT}/test/test_stage27_schedule_profile/test_main.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/Stage27ScheduleProfile.cpp"
  "${PROJECT_ROOT}/src/climate/runtime/EuropeWarsawTime.cpp"
)
'''
if old not in text:
    raise SystemExit('stage27_schedule_profile_tests block not found')
path.write_text(text.replace(old, new, 1))
