#!/usr/bin/env python3
from pathlib import Path
root=Path.cwd()
cpp=root/'lib/environment_control/src/climate/ClimateTrendEstimator.cpp'
text=cpp.read_text(encoding='utf-8')
old='''if(size_>0U){ auto& last=samples_[size_-1U]; if(ts==last.timestamp_ms || ts-last.timestamp_ms<kMinimumSampleSpacingMs){ last={ts,value}; return; }}'''
new='''if(size_>0U){ auto& last=samples_[size_-1U]; if(ts==last.timestamp_ms){ last.value=value; return; } if(ts-last.timestamp_ms<kMinimumSampleSpacingMs) return; }'''
if old not in text: raise SystemExit('trend decimation anchor not found')
cpp.write_text(text.replace(old,new),encoding='utf-8')

doc=root/'docs/MVP_ENVIRONMENT_CONTROLLER.md'; text=doc.read_text(encoding='utf-8')
old='''Repeated faster samples replace the newest point rather than growing the buffer.'''
new='''Repeated faster samples are ignored until the 5-second source-time spacing is reached.'''
if old not in text: raise SystemExit('trend doc anchor not found')
doc.write_text(text.replace(old,new),encoding='utf-8')

test=root/'test/test_climate_v6/test_main.cpp'; text=test.read_text(encoding='utf-8')
anchor='''m.co2_ppm.age_ms=kDefaultSensorTimeoutMs+1U; tr=e.update(m,65'000U); check(!tr.co2.available,"stale CO2 trend"); tr=e.update(m,1'000U); check(!tr.temperature.available,"rollback resets trend"); }'''
replacement='''m.co2_ppm.age_ms=kDefaultSensorTimeoutMs+1U; tr=e.update(m,65'000U); check(!tr.co2.available,"stale CO2 trend"); tr=e.update(m,1'000U); check(!tr.temperature.available,"rollback resets trend"); ClimateTrendEstimator fast{}; m.co2_ppm={500.0F,true,0U}; for(std::uint64_t ms=0U;ms<=60'000U;ms+=1'000U){ const float min=static_cast<float>(ms)/60'000.0F; m.air_temperature_c={20.0F+min,true,0U}; m.relative_humidity_pct={60.0F,true,0U}; tr=fast.update(m,ms); } check(tr.temperature.available && near(tr.temperature.rate_per_min,1.0F,0.02F),"1 Hz sampling must still produce 60 second trend"); }'''
if anchor not in text: raise SystemExit('trend test anchor not found')
test.write_text(text.replace(anchor,replacement),encoding='utf-8')
print('trend decimation corrected')
