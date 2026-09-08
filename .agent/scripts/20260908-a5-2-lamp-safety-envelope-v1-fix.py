from pathlib import Path

path = Path('test/test_stage28d_lamp_safety/test_main.cpp')
text = path.read_text()
old = '#include "climate/Stage28dLampSafety.h"\n'
new = '#include "climate/Stage28dLampSafety.h"\n#include "climate/Stage28dOutputBindings.h"\n'
assert old in text
path.write_text(text.replace(old, new, 1))
