from __future__ import annotations

import base64
import binascii
import json
import math
import re
import statistics
import time
import urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import serial

from tools.output_supervisor_h import QualificationContractError, replay_qualification

PORT = "/dev/cu.usbserial-1130"
FORBIDDEN_PORT = "/dev/cu.usbserial-10"
QUALIFIED_SHA = "02208d23f403bca3540dbbd652eb55703a044833"
TOOLING_SHA = "2a19cd43646fe284a7ab41828178b2b8f17edea1"
SHELLY_HOST = "192.168.0.16"

STARTUP_TIMEOUT_S = 900.0
NATURAL_WAIT_TIMEOUT_S = 3600.0
BASELINE_S = 180.0
POST_IGNORE_S = 30.0
POST_MAX_S = 600.0
POST_MIN_OBSERVATION_S = 60.0
SHELLY_CADENCE_S = 2.0
SHELLY_SAMPLES = 8
POWER_DELTA_MIN_W = 1.0
TEMP_RESPONSE_MIN_C = 0.20
AH_RESPONSE_MIN_G_M3 = 0.30
TEMP_GUARD_C = 27.5
QUERY_CADENCE_S = 10.0

MODE_AUTOMATIC = 2
MODE_DISABLED = 4
SOURCE_CLIMATE = 1
REASON_CLIMATE = 1
TRANSPORT_COMPLETED = 1
STATE_OFF = 0
STATE_ON = 1


@dataclass
class EnvSample:
    uptime_ms: int
    tp_t: float
    tp_rh: float
    xiaomi_t: float
    xiaomi_rh: float
    rtc_unix_s: int


@dataclass
class ShellySample:
    monotonic_s: float
    power_w: float
    lamp_state: int | None
    fan_state: int | None
    humidifier_state: int | None


class HFailure(RuntimeError):
    pass


def parse_prefix_ms(line: str) -> int | None:
    match = re.match(r"I \((\d+)\)", line)
    return int(match.group(1)) if match else None


def parse_fields(fragment: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in fragment.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        result[key] = value.rstrip(",")
    return result


def slash(value: str, count: int) -> list[str]:
    parts = value.split("/")
    if len(parts) != count:
        raise HFailure(f"malformed slash field {value!r}, expected {count} parts")
    return parts


def ah_g_m3(temp_c: float, rh_pct: float) -> float:
    svp_hpa = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
    vapor_hpa = svp_hpa * (rh_pct / 100.0)
    return 2.1674 * vapor_hpa / (273.15 + temp_c) * 100.0


def shelly_get(path: str) -> dict[str, object]:
    url = f"http://{SHELLY_HOST}{path}"
    with urllib.request.urlopen(url, timeout=2.0) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise HFailure(f"Shelly returned non-object for {path}")
    return payload


def shelly_sample() -> tuple[bool, float]:
    meter = shelly_get("/meter/0")
    relay = shelly_get("/relay/0")
    if "power" not in meter or "ison" not in relay:
        raise HFailure("Shelly Gen1 meter/relay fields are missing")
    return bool(relay["ison"]), float(meter["power"])


class Observer:
    def __init__(self, ser: serial.Serial) -> None:
        self.ser = ser
        self.identity_ok = False
        self.boot_id: str | None = None
        self.output_mode_ok = False
        self.rf_ready = False
        self.automation_mode: str | None = None
        self.automation_requested: str | None = None
        self.sd_mounted = False
        self.env: list[EnvSample] = []
        self.snapshots: list[dict[str, object]] = []
        self.pending: dict[str, object] | None = None
        self.latest_snapshot: dict[str, object] | None = None
        self.transport_failure_seen = False
        self.fault_locked_seen = False
        self.maintenance_locked_seen = False
        self.latest_tp_t: float | None = None
        self.last_progress_print = 0.0

    def send(self, command: str) -> None:
        self.ser.write((command + "\n").encode())
        self.ser.flush()

    def process(self, line: str) -> None:
        if not line:
            return

        if line.startswith("status firmware_sha="):
            fields = parse_fields(line)
            sha = fields.get("firmware_sha")
            boot_id = fields.get("boot_id")
            outputs = fields.get("outputs")
            rf_ready = fields.get("rf_ready")
            if sha != QUALIFIED_SHA:
                raise HFailure(f"wrong firmware SHA {sha!r}")
            if self.boot_id is None:
                self.boot_id = boot_id
            elif boot_id != self.boot_id:
                raise HFailure(f"unexpected ESP32 restart {self.boot_id!r}->{boot_id!r}")
            self.identity_ok = True
            self.output_mode_ok = outputs == "real-bounded"
            self.rf_ready = rf_ready == "1"
            if not self.output_mode_ok or not self.rf_ready:
                raise HFailure(f"real output transport not ready outputs={outputs!r} rf_ready={rf_ready!r}")
            return

        if line.startswith("automation mode="):
            fields = parse_fields(line)
            self.automation_mode = fields.get("mode")
            self.automation_requested = fields.get("requested")
            if self.automation_mode == "fault-locked":
                self.fault_locked_seen = True
                raise HFailure("supervisor entered FaultLocked")
            if self.automation_mode == "maintenance-locked":
                self.maintenance_locked_seen = True
                raise HFailure("supervisor entered MaintenanceLocked")
            return

        if line.startswith("sdlog_status "):
            fields = parse_fields(line)
            self.sd_mounted = fields.get("available") == "1" and fields.get("sd_mounted") == "1"
            if fields.get("write_errors", "0") != "0" or fields.get("queue_drops", "0") != "0":
                raise HFailure(f"SD logger is not clean: {line}")
            return

        if "climate_stage27: soak_v=3 " in line:
            fields = parse_fields(line.split("climate_stage27: ", 1)[1])
            if fields.get("firmware_sha") != QUALIFIED_SHA:
                raise HFailure("soak telemetry firmware identity mismatch")
            if fields.get("tp_sample") == "1" and fields.get("xiaomi_sample") == "1":
                sample = EnvSample(
                    uptime_ms=int(fields["uptime_ms"]),
                    tp_t=float(fields["tp_t"]),
                    tp_rh=float(fields["tp_rh"]),
                    xiaomi_t=float(fields["xiaomi_t"]),
                    xiaomi_rh=float(fields["xiaomi_rh"]),
                    rtc_unix_s=int(fields["rtc_unix_time_s"]),
                )
                self.env.append(sample)
                self.latest_tp_t = sample.tp_t
                if sample.tp_t >= TEMP_GUARD_C:
                    raise HFailure(f"operator thermal guard reached TP357={sample.tp_t:.2f}C")
            if fields.get("storage_sd_mounted") == "1":
                self.sd_mounted = True
            if int(fields.get("storage_write_errors", "0")) != 0 or int(
                fields.get("storage_queue_drops", "0")
            ) != 0:
                raise HFailure("storage error in soak telemetry")
            return

        if "climate_stage27: output_exec_v=2 " in line:
            fields = parse_fields(line.split("climate_stage27: ", 1)[1])
            mode = int(fields["supervisor_mode"])
            if mode == 5:
                self.fault_locked_seen = True
                raise HFailure("output telemetry entered FaultLocked")
            if mode == 6:
                self.maintenance_locked_seen = True
                raise HFailure("output telemetry entered MaintenanceLocked")
            if int(fields.get("tx_errors", "0")) != 0:
                self.transport_failure_seen = True
                raise HFailure(f"RF transport tx_errors={fields.get('tx_errors')}")
            uptime = parse_prefix_ms(line)
            if uptime is None:
                raise HFailure("output telemetry missing monotonic prefix")
            self.pending = {
                "t": "s",
                "v": 3,
                "u": uptime,
                "out": {
                    "v": 2,
                    "m": mode,
                    "ta": int(fields["transport_active"]),
                    "la": int(fields["lifecycle_active"]),
                    "le": int(fields["lifecycle_event"]),
                    "ae": int(fields["automation_requested"]),
                    "sl": int(fields["safety_latched"]),
                    "sr": int(fields["safety_reason"]),
                    "ep": [],
                },
            }
            return

        if "climate_stage27: output_endpoint " in line and self.pending is not None:
            fields = parse_fields(line.split("climate_stage27: ", 1)[1])
            control = slash(fields["control"], 2)
            schedule = slash(fields["schedule"], 2)
            manual = slash(fields["manual"], 2)
            safety = slash(fields["safety"], 3)
            selected = slash(fields["selected"], 4)
            resolved = slash(fields["resolved"], 2)
            last_command = slash(fields["last_command"], 4)
            endpoint = [
                int(fields["endpoint"]),
                int(control[0]),
                float(control[1]),
                int(schedule[0]),
                float(schedule[1]),
                int(manual[0]),
                float(manual[1]),
                int(safety[0]),
                int(safety[1]),
                int(safety[2]),
                int(selected[0]),
                float(selected[1]),
                int(selected[2]),
                int(selected[3]),
                int(resolved[0]),
                int(resolved[1]),
                int(fields["dwell"]),
                int(fields["override"]),
                int(fields["inhibited"]),
                int(fields["attempt"]),
                int(fields["current"]),
                int(fields["state"]),
                int(fields["source"]),
                int(fields["reason"]),
                int(fields["transport"]),
                int(fields["error"]),
                int(last_command[0]),
                int(last_command[1]),
                int(last_command[2]),
                int(last_command[3]),
                int(fields["physical_state"]),
                int(fields["independent"]),
            ]
            if endpoint[25] != 0 or endpoint[24] == 2:
                self.transport_failure_seen = True
                raise HFailure(f"endpoint {endpoint[0]} transport failure")
            out = self.pending["out"]
            assert isinstance(out, dict)
            eps = out["ep"]
            assert isinstance(eps, list)
            eps.append(endpoint)
            if len(eps) == 3:
                eps.sort(key=lambda item: int(item[0]))
                completed = self.pending
                self.snapshots.append(completed)
                self.latest_snapshot = completed
                self.pending = None
            return

    def read_once(self) -> str:
        raw = self.ser.readline()
        if not raw:
            return ""
        line = raw.decode(errors="replace").strip()
        self.process(line)
        return line

    def query(self) -> None:
        self.send("status")
        self.send("automation status")
        self.send("sensors")
        self.send("sdlog status")


def endpoint(record: dict[str, object], endpoint_id: int) -> list[object]:
    out = record["out"]
    assert isinstance(out, dict)
    eps = out["ep"]
    assert isinstance(eps, list)
    for item in eps:
        if int(item[0]) == endpoint_id:
            return item
    raise HFailure(f"snapshot missing endpoint {endpoint_id}")


def state_from_endpoint(ep: list[object]) -> int | None:
    if int(ep[26]) == 1:
        return int(ep[27])
    if int(ep[14]) == 1:
        return int(ep[15])
    return None


def global_clean(record: dict[str, object]) -> bool:
    out = record["out"]
    assert isinstance(out, dict)
    if int(out["m"]) != MODE_AUTOMATIC or int(out["ae"]) != 1 or int(out["la"]) != 0:
        return False
    for ep in out["ep"]:
        if int(ep[25]) != 0 or int(ep[24]) == 2:
            return False
    return True


def clean_fan_off(record: dict[str, object]) -> bool:
    if not global_clean(record):
        return False
    out = record["out"]
    assert isinstance(out, dict)
    fan = endpoint(record, 1)
    return (
        int(out["sl"]) == 0
        and int(fan[5]) == 0
        and int(fan[7]) == 0
        and int(fan[17]) == 0
        and int(fan[18]) == 0
        and int(fan[14]) == 1
        and int(fan[15]) == STATE_OFF
        and int(fan[26]) == 1
        and int(fan[27]) == STATE_OFF
    )


def natural_fan_on(record: dict[str, object]) -> bool:
    if not global_clean(record):
        return False
    out = record["out"]
    assert isinstance(out, dict)
    fan = endpoint(record, 1)
    return (
        int(out["sl"]) == 0
        and int(fan[5]) == 0
        and int(fan[7]) == 0
        and int(fan[17]) == 0
        and int(fan[18]) == 0
        and int(fan[1]) == 1
        and float(fan[2]) > 0.0
        and int(fan[10]) == 1
        and int(fan[12]) == SOURCE_CLIMATE
        and int(fan[13]) == REASON_CLIMATE
        and int(fan[14]) == 1
        and int(fan[15]) == STATE_ON
        and int(fan[16]) == 0
        and int(fan[19]) == 1
        and int(fan[21]) == STATE_ON
        and int(fan[22]) == SOURCE_CLIMATE
        and int(fan[23]) == REASON_CLIMATE
        and int(fan[24]) == TRANSPORT_COMPLETED
        and int(fan[25]) == 0
        and int(fan[26]) == 1
        and int(fan[27]) == STATE_ON
        and int(fan[28]) == SOURCE_CLIMATE
        and int(fan[29]) == REASON_CLIMATE
        and int(out["ta"]) == 1
    )


def load_states(record: dict[str, object]) -> tuple[int | None, int | None, int | None]:
    return (
        state_from_endpoint(endpoint(record, 2)),
        state_from_endpoint(endpoint(record, 1)),
        state_from_endpoint(endpoint(record, 3)),
    )


def schedule_targets(unix_s: int) -> tuple[float, float, bool]:
    local = datetime.fromtimestamp(unix_s, tz=ZoneInfo("Europe/Warsaw"))
    minute = local.hour * 60 + local.minute
    distance = min(abs(minute - 360), abs(minute - 1320))
    if distance < 10:
        return 0.0, 0.0, False
    if 360 <= minute < 1320:
        return 24.5, 58.0, True
    return 21.5, 65.0, True


def classify_trigger(sample: EnvSample) -> tuple[bool, bool, float, float]:
    target_t, target_rh, boundary_safe = schedule_targets(sample.rtc_unix_s)
    if not boundary_safe:
        raise HFailure("candidate occurred too close to 06:00/22:00 schedule boundary")
    mixed_t = 0.8 * sample.tp_t + 0.2 * sample.xiaomi_t
    temp_improvement = abs(sample.tp_t - target_t) - abs(mixed_t - target_t)
    inside_ah = ah_g_m3(sample.tp_t, sample.tp_rh)
    outside_ah = ah_g_m3(sample.xiaomi_t, sample.xiaomi_rh)
    ah_gap = inside_ah - outside_ah
    humidity_excess = sample.tp_rh - target_rh
    temp_active = temp_improvement > 0.4
    humidity_active = humidity_excess >= 3.8 and ah_gap >= 0.8
    return temp_active, humidity_active, temp_improvement, ah_gap


def median_metrics(samples: list[EnvSample]) -> tuple[float, float]:
    temp_gap = statistics.median(abs(s.tp_t - s.xiaomi_t) for s in samples)
    ah_gap = statistics.median(
        ah_g_m3(s.tp_t, s.tp_rh) - ah_g_m3(s.xiaomi_t, s.xiaomi_rh) for s in samples
    )
    return float(temp_gap), float(ah_gap)


def sd_list(observer: Observer, timeout_s: float = 8.0) -> dict[str, int]:
    observer.send("sdlog list")
    result: dict[str, int] = {}
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        line = observer.read_once()
        if line.startswith("sdlog_file "):
            fields = parse_fields(line)
            result[fields["name"]] = int(fields["size"])
        elif line.startswith("sdlog_list_end "):
            return result
        elif line.startswith("sdlog_error "):
            raise HFailure(line)
    raise HFailure("sdlog list timed out")


def sd_read(observer: Observer, name: str, offset: int, length: int) -> bytes:
    observer.send(f"sdlog read {name} {offset} {length}")
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        line = observer.read_once()
        if line.startswith("sdlog_chunk "):
            fields = parse_fields(line)
            if fields.get("name") != name or int(fields.get("offset", "-1")) != offset:
                continue
            payload = base64.b64decode(fields["b64"], validate=True)
            expected_crc = int(fields["crc32"], 16)
            if (binascii.crc32(payload) & 0xFFFFFFFF) != expected_crc:
                raise HFailure("sdlog chunk CRC mismatch")
            return payload
        if line.startswith("sdlog_error "):
            raise HFailure(line)
    raise HFailure(f"sdlog read timed out offset={offset}")


def discover_session(observer: Observer) -> dict[str, object]:
    first = sd_list(observer)
    for _ in range(3):
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            observer.read_once()
        second = sd_list(observer)
        growing = [name for name, size in second.items() if size > first.get(name, -1)]
        if len(growing) == 1:
            name = growing[0]
            data = sd_read(observer, name, 0, min(384, second[name]))
            first_line = data.splitlines()[0] if data.splitlines() else b""
            try:
                record = json.loads(first_line)
            except Exception as exc:
                raise HFailure(f"cannot parse active session record: {exc}") from exc
            if not isinstance(record, dict):
                raise HFailure("active session header is not an object")
            if (
                record.get("t") != "session"
                or record.get("schema") != "growbox-log-v3"
                or int(record.get("out_v", -1)) != 2
                or record.get("fw") != QUALIFIED_SHA
            ):
                raise HFailure(f"active SD session identity mismatch: {record!r}")
            print(f"H_SD_SESSION_PASS file={name} schema=growbox-log-v3 out_v=2", flush=True)
            return record
        first = second
    raise HFailure("could not uniquely identify the growing current SD log")


def wait_until_ready(observer: Observer) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    next_query = 0.0
    automation_on_sent = False
    while time.monotonic() < deadline:
        now = time.monotonic()
        observer.read_once()
        if now >= next_query:
            observer.query()
            next_query = now + QUERY_CADENCE_S
        latest = observer.latest_snapshot
        env_ok = bool(observer.env)
        if latest is None:
            continue
        out = latest["out"]
        assert isinstance(out, dict)
        safety_clear = int(out["sl"]) == 0
        if observer.identity_ok and observer.sd_mounted and env_ok and safety_clear:
            if not automation_on_sent and int(out["ae"]) == 0 and int(out["m"]) in {
                MODE_AUTOMATIC,
                MODE_DISABLED,
            }:
                observer.send("automation on")
                automation_on_sent = True
                print("H_AUTOMATION_ON_REQUESTED supervisor_owned=1", flush=True)
            if int(out["m"]) == MODE_AUTOMATIC and int(out["ae"]) == 1 and int(out["la"]) == 0:
                print(
                    f"H_READY_PASS uptime_ms={latest['u']} safety_latched=0 mode=automatic automation_requested=1",
                    flush=True,
                )
                return
    raise HFailure("startup/safety recovery did not reach ready Automatic state")


def sample_shelly(observer: Observer) -> ShellySample:
    master_on, power = shelly_sample()
    if not master_on:
        raise HFailure("Shelly master relay is OFF")
    latest = observer.latest_snapshot
    lamp = fan = humidifier = None
    if latest is not None:
        lamp, fan, humidifier = load_states(latest)
    return ShellySample(time.monotonic(), power, lamp, fan, humidifier)


def final_automation_off(observer: Observer) -> bool:
    if not observer.identity_ok:
        return False
    print("H_FINAL_AUTOMATION_OFF_REQUESTED supervisor_owned=1", flush=True)
    observer.send("automation off")
    deadline = time.monotonic() + 120.0
    next_query = 0.0
    while time.monotonic() < deadline:
        now = time.monotonic()
        try:
            observer.read_once()
        except HFailure as exc:
            print(f"H_FINAL_OBSERVER_WARNING error={exc}", flush=True)
        if now >= next_query:
            observer.send("automation status")
            observer.send("status")
            next_query = now + 5.0
        latest = observer.latest_snapshot
        if latest is None:
            continue
        out = latest["out"]
        assert isinstance(out, dict)
        if int(out["m"]) != MODE_DISABLED or int(out["la"]) != 0 or int(out["ae"]) != 0:
            continue
        fan = endpoint(latest, 1)
        humidifier = endpoint(latest, 3)
        if (
            state_from_endpoint(fan) == STATE_OFF
            and state_from_endpoint(humidifier) == STATE_OFF
            and all(int(ep[25]) == 0 and int(ep[24]) != 2 for ep in out["ep"])
        ):
            print("H_FINAL_SAFE_STATE_PASS mode=disabled fan=off humidifier=off transport=clean", flush=True)
            return True
    print("H_FINAL_SAFE_STATE_FAIL", flush=True)
    return False


def run_h(observer: Observer, session_record: dict[str, object]) -> None:
    clean_start_u: int | None = None
    baseline_start_u: int | None = None
    candidate: dict[str, object] | None = None
    candidate_wall: float | None = None
    candidate_env: EnvSample | None = None
    candidate_loads: tuple[int | None, int | None, int | None] | None = None
    pre_power: list[float] | None = None
    shelly_history: deque[ShellySample] = deque(maxlen=120)
    next_shelly = 0.0
    next_query = 0.0
    snapshot_index = len(observer.snapshots)
    wait_deadline = time.monotonic() + NATURAL_WAIT_TIMEOUT_S

    while time.monotonic() < wait_deadline and candidate is None:
        now = time.monotonic()
        observer.read_once()
        if now >= next_query:
            observer.query()
            next_query = now + QUERY_CADENCE_S
        if now >= next_shelly and observer.latest_snapshot is not None:
            sample = sample_shelly(observer)
            shelly_history.append(sample)
            next_shelly = now + SHELLY_CADENCE_S

        while snapshot_index < len(observer.snapshots):
            record = observer.snapshots[snapshot_index]
            snapshot_index += 1
            u = int(record["u"])
            if clean_fan_off(record):
                if clean_start_u is None:
                    clean_start_u = u
                    print(f"H_CLEAN_OFF_STARTED uptime_ms={u}", flush=True)
                continue

            if natural_fan_on(record):
                if clean_start_u is None or u - clean_start_u < int(BASELINE_S * 1000):
                    clean_start_u = None
                    continue
                pre_env = [
                    s for s in observer.env if u - int(BASELINE_S * 1000) <= s.uptime_ms < u
                ]
                if len(pre_env) < 12:
                    clean_start_u = None
                    continue
                near = min(pre_env, key=lambda s: abs(s.uptime_ms - u))
                if abs(near.uptime_ms - u) > 20_000:
                    clean_start_u = None
                    continue
                temp_active, humidity_active, temp_improvement, ah_gap = classify_trigger(near)
                if not temp_active and not humidity_active:
                    raise HFailure(
                        "natural fan ON observed but temperature/humidity trigger mechanism is not conservatively proven"
                    )
                loads = load_states(record)
                eligible_pre = [
                    s
                    for s in shelly_history
                    if s.monotonic_s < now
                    and s.fan_state == STATE_OFF
                    and (s.lamp_state, s.humidifier_state) == (loads[0], loads[2])
                ]
                if len(eligible_pre) < SHELLY_SAMPLES:
                    clean_start_u = None
                    continue
                chosen = eligible_pre[-SHELLY_SAMPLES:]
                if chosen[-1].monotonic_s - chosen[0].monotonic_s < 12.0:
                    clean_start_u = None
                    continue
                candidate = record
                candidate_wall = now
                candidate_env = near
                candidate_loads = loads
                pre_power = [s.power_w for s in chosen]
                baseline_start_u = clean_start_u
                print(
                    "H_NATURAL_TRANSITION_CAPTURED "
                    f"uptime_ms={u} requested_level={float(endpoint(record, 1)[2]):.3f} "
                    f"temp_trigger={int(temp_active)} humidity_trigger={int(humidity_active)} "
                    f"temp_improvement_c={temp_improvement:.3f} ah_gap_gm3={ah_gap:.3f}",
                    flush=True,
                )
                break

            clean_start_u = None

        if now - observer.last_progress_print >= 60.0:
            observer.last_progress_print = now
            baseline_age = 0.0
            if clean_start_u is not None and observer.latest_snapshot is not None:
                baseline_age = (int(observer.latest_snapshot["u"]) - clean_start_u) / 1000.0
            print(
                f"H_WAITING_NATURAL baseline_s={baseline_age:.0f} tp357_c={observer.latest_tp_t}",
                flush=True,
            )

    if candidate is None or candidate_wall is None or candidate_env is None or candidate_loads is None:
        raise HFailure("no qualifying natural fan OFF->ON transition within bounded wait")
    assert pre_power is not None and baseline_start_u is not None

    post_power: list[float] = []
    while len(post_power) < SHELLY_SAMPLES:
        observer.read_once()
        now = time.monotonic()
        if now < next_shelly:
            continue
        sample = sample_shelly(observer)
        next_shelly = now + SHELLY_CADENCE_S
        if (sample.lamp_state, sample.humidifier_state) != (candidate_loads[0], candidate_loads[2]):
            raise HFailure("Shelly proof confounded by lamp/humidifier state change")
        if sample.fan_state != STATE_ON:
            raise HFailure("fan command state left ON before eight post-transition Shelly samples completed")
        post_power.append(sample.power_w)

    pre_median = float(statistics.median(pre_power))
    post_median = float(statistics.median(post_power))
    power_delta = post_median - pre_median
    if power_delta < POWER_DELTA_MIN_W:
        raise HFailure(
            f"Shelly fan power delta {power_delta:.3f}W below frozen {POWER_DELTA_MIN_W:.3f}W"
        )
    print(
        f"H_SHELLY_PASS samples_before=8 samples_after=8 pre_w={pre_median:.3f} post_w={post_median:.3f} delta_w={power_delta:.3f}",
        flush=True,
    )

    candidate_u = int(candidate["u"])
    pre_env = [s for s in observer.env if candidate_u - 180_000 <= s.uptime_ms < candidate_u]
    pre_temp_gap, pre_ah_gap = median_metrics(pre_env)
    temp_active, humidity_active, _, _ = classify_trigger(candidate_env)
    environmental_kind: str | None = None
    temp_delta = 0.0
    ah_delta = 0.0
    post_deadline = candidate_wall + POST_MAX_S
    while time.monotonic() < post_deadline:
        now = time.monotonic()
        observer.read_once()
        if now >= next_query:
            observer.query()
            next_query = now + QUERY_CADENCE_S
        latest = observer.latest_snapshot
        if latest is not None:
            lamp, _, humidifier = load_states(latest)
            if lamp != candidate_loads[0]:
                raise HFailure("lamp changed during environmental proof window")
            if humidity_active and humidifier != candidate_loads[2]:
                raise HFailure("humidifier changed during humidity environmental proof window")
        elapsed = now - candidate_wall
        if elapsed < POST_IGNORE_S + POST_MIN_OBSERVATION_S:
            continue
        post_env = [
            s
            for s in observer.env
            if candidate_u + int(POST_IGNORE_S * 1000) <= s.uptime_ms
        ]
        if len(post_env) < 6:
            continue
        post_temp_gap, post_ah_gap = median_metrics(post_env)
        temp_delta = pre_temp_gap - post_temp_gap
        ah_delta = pre_ah_gap - post_ah_gap
        if temp_active and temp_delta >= TEMP_RESPONSE_MIN_C:
            environmental_kind = "temperature"
            break
        if humidity_active and ah_delta >= AH_RESPONSE_MIN_G_M3:
            environmental_kind = "humidity"
            break

    if environmental_kind is None:
        raise HFailure(
            "environmental response did not meet frozen active-trigger threshold "
            f"temp_gap_delta_c={temp_delta:.3f} ah_gap_delta_gm3={ah_delta:.3f}"
        )
    print(
        f"H_ENVIRONMENT_PASS mechanism={environmental_kind} temp_gap_delta_c={temp_delta:.3f} ah_gap_delta_gm3={ah_delta:.3f}",
        flush=True,
    )

    proof_records = [session_record]
    proof_records.extend(
        record
        for record in observer.snapshots
        if baseline_start_u <= int(record["u"]) <= candidate_u + 20_000
    )
    evidence = {
        "shelly_master_on": True,
        "power_before_w": pre_power,
        "power_after_w": post_power,
        "minimum_power_delta_w": POWER_DELTA_MIN_W,
        "lamp_state_changed": False,
        "humidifier_state_changed": False,
        "environmental_response_supported": True,
    }
    try:
        replay = replay_qualification(proof_records, evidence)
    except QualificationContractError as exc:
        raise HFailure(f"formal OutputSupervisor replay failed: {exc}") from exc
    if replay.transition_uptime_ms < baseline_start_u or replay.transition_uptime_ms > candidate_u + 20_000:
        raise HFailure("formal replay selected an unexpected transition")
    print(
        f"OUTPUT_SUPERVISOR_H_REPLAY_PASS sha={replay.qualified_sha} baseline_uptime_ms={replay.baseline_uptime_ms} transition_uptime_ms={replay.transition_uptime_ms} power_delta_w={replay.power_delta_w:.3f} hardware_started=1",
        flush=True,
    )

    print(
        "OUTPUT_SUPERVISOR_H_PHYSICAL_EVIDENCE_PASS "
        f"sha={QUALIFIED_SHA} tooling_sha={TOOLING_SHA} port={PORT} shelly={SHELLY_HOST} "
        f"power_delta_w={power_delta:.3f} environmental={environmental_kind} "
        f"temp_gap_delta_c={temp_delta:.3f} ah_gap_delta_gm3={ah_delta:.3f} "
        f"raw_rf=0 forbidden_port_untouched={FORBIDDEN_PORT} hardware_started=1",
        flush=True,
    )


def main() -> int:
    ser = serial.Serial(port=None, baudrate=115200, timeout=0.2, write_timeout=1.0)
    ser.dtr = False
    ser.rts = False
    ser.port = PORT
    observer: Observer | None = None
    final_safe = False
    evidence_pass = False
    failure: Exception | None = None

    try:
        ser.open()
        observer = Observer(ser)
        print(
            f"H_SINGLE_OPEN port={PORT} expected_port_open_reset=1 forbidden_port_untouched={FORBIDDEN_PORT}",
            flush=True,
        )
        observer.query()
        identity_deadline = time.monotonic() + 60.0
        while time.monotonic() < identity_deadline and not observer.identity_ok:
            observer.read_once()
            if int(time.monotonic()) % 5 == 0:
                observer.send("status")
        if not observer.identity_ok:
            raise HFailure("could not verify exact firmware identity")
        session = discover_session(observer)
        wait_until_ready(observer)
        run_h(observer, session)
        evidence_pass = True
    except Exception as exc:
        failure = exc
        print(f"OUTPUT_SUPERVISOR_H_PHYSICAL_FAIL reason={type(exc).__name__}:{exc}", flush=True)
    finally:
        if observer is not None:
            try:
                final_safe = final_automation_off(observer)
            except Exception as exc:
                print(f"H_FINALIZATION_EXCEPTION error={type(exc).__name__}:{exc}", flush=True)
        if ser.is_open:
            ser.close()

    if failure is not None:
        raise SystemExit(1)
    if not evidence_pass or not final_safe:
        print(
            f"OUTPUT_SUPERVISOR_H_PHYSICAL_FAIL evidence_pass={int(evidence_pass)} final_safe={int(final_safe)}",
            flush=True,
        )
        return 1
    print(
        "OUTPUT_SUPERVISOR_H_PHYSICAL_PASS "
        f"sha={QUALIFIED_SHA} tooling_sha={TOOLING_SHA} port={PORT} shelly={SHELLY_HOST} "
        f"raw_rf=0 forbidden_port_untouched={FORBIDDEN_PORT} hardware_started=1",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
