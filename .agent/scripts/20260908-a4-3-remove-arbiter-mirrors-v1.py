from pathlib import Path

h = Path('src/climate/Stage28dBinaryRoleArbiter.h')
c = Path('src/climate/Stage28dBinaryRoleArbiter.cpp')

hs = h.read_text()
cs = c.read_text()

replacements_h = [
("  bool exhaustOn() const noexcept { return exhaust_.known && exhaust_.on; }\n  bool humidifierOn() const noexcept { return humidifier_.known && humidifier_.on; }\n  std::uint32_t transitionCount() const noexcept { return transition_count_; }\n  std::uint32_t dwellHoldCount() const noexcept { return dwell_hold_count_; }\n",
 "  bool exhaustOn() const noexcept { return exhaust_policy_.on(); }\n  bool humidifierOn() const noexcept { return humidifier_policy_.on(); }\n  std::uint32_t transitionCount() const noexcept {\n    return exhaust_policy_.transitionCount() + humidifier_policy_.transitionCount();\n  }\n  std::uint32_t dwellHoldCount() const noexcept {\n    return exhaust_policy_.dwellHoldCount() + humidifier_policy_.dwellHoldCount();\n  }\n"),
("private:\n  struct BinaryState {\n    bool known{false};\n    bool on{false};\n    std::uint64_t last_change_ms{0U};\n  };\n\n  struct CounterSnapshot {\n",
 "private:\n  struct CounterSnapshot {\n"),
("  static ::growbox::app::output::BinaryActuatorPolicyConfig\n  policyConfig(BinaryActuatorConfig config) noexcept;\n  void syncPolicyCounters() noexcept;\n  void checkCounterContinuity() noexcept;\n  bool applyBinary(ClimateActuatorRole role, float requested_level,\n                   std::uint64_t monotonic_ms,\n                   ::growbox::app::output::BinaryActuatorPolicy& policy,\n                   BinaryState& state, bool force_on) noexcept;\n  bool forceBinaryOff(ClimateActuatorRole role, std::uint64_t monotonic_ms,\n                      ::growbox::app::output::BinaryActuatorPolicy& policy,\n                      BinaryState& state) noexcept;\n\n  ClimateRoleDriver& downstream_;\n  BinaryRoleArbiterConfig config_{};\n",
 "  static ::growbox::app::output::BinaryActuatorPolicyConfig\n  policyConfig(BinaryActuatorConfig config) noexcept;\n  void checkCounterContinuity() noexcept;\n  bool applyBinary(ClimateActuatorRole role, float requested_level,\n                   std::uint64_t monotonic_ms,\n                   ::growbox::app::output::BinaryActuatorPolicy& policy,\n                   bool force_on) noexcept;\n  bool forceBinaryOff(ClimateActuatorRole role, std::uint64_t monotonic_ms,\n                      ::growbox::app::output::BinaryActuatorPolicy& policy) noexcept;\n\n  ClimateRoleDriver& downstream_;\n"),
("  ::growbox::app::output::BinaryActuatorPolicy exhaust_policy_{};\n  ::growbox::app::output::BinaryActuatorPolicy humidifier_policy_{};\n  // Compatibility mirrors only. A4.3 removes these after parity is proven.\n  BinaryState exhaust_{};\n  BinaryState humidifier_{};\n  bool safety_force_exhaust_{false};\n  std::uint32_t transition_count_{0U};\n  std::uint32_t dwell_hold_count_{0U};\n",
 "  ::growbox::app::output::BinaryActuatorPolicy exhaust_policy_{};\n  ::growbox::app::output::BinaryActuatorPolicy humidifier_policy_{};\n  bool safety_force_exhaust_{false};\n")
]
for old, new in replacements_h:
    if old not in hs:
        raise SystemExit('header marker missing')
    hs = hs.replace(old, new, 1)

replacements_c = [
("    : downstream_(downstream), config_(config), instance_id_(nextBinaryArbiterInstanceId()),\n      exhaust_policy_(policyConfig(config.exhaust_fan)),\n      humidifier_policy_(policyConfig(config.humidifier)) {\n  config_.exhaust_fan = sanitized(config_.exhaust_fan);\n  config_.humidifier = sanitized(config_.humidifier);\n",
 "    : downstream_(downstream), instance_id_(nextBinaryArbiterInstanceId()),\n      exhaust_policy_(policyConfig(config.exhaust_fan)),\n      humidifier_policy_(policyConfig(config.humidifier)) {\n"),
("  recordArbiterBreadcrumb(instance_id_, constructionCount(), transition_count_, dwell_hold_count_,\n                          safety_override_count_, continuity_fault_count_, false);\n",
 "  recordArbiterBreadcrumb(instance_id_, constructionCount(), transitionCount(), dwellHoldCount(),\n                          safety_override_count_, continuity_fault_count_, false);\n"),
("void Stage28dBinaryRoleArbiter::syncPolicyCounters() noexcept {\n  transition_count_ = exhaust_policy_.transitionCount() + humidifier_policy_.transitionCount();\n  dwell_hold_count_ = exhaust_policy_.dwellHoldCount() + humidifier_policy_.dwellHoldCount();\n}\n\n",
 ""),
("  const CounterSnapshot current{transition_count_, dwell_hold_count_, safety_override_count_};\n",
 "  const CounterSnapshot current{transitionCount(), dwellHoldCount(), safety_override_count_};\n"),
("  exhaust_policy_.synchronize(::growbox::app::output::BinaryOutputState::Off, monotonic_ms);\n  humidifier_policy_.synchronize(::growbox::app::output::BinaryOutputState::Off, monotonic_ms);\n  syncPolicyCounters();\n  exhaust_ = {true, false, monotonic_ms};\n  humidifier_ = {true, false, monotonic_ms};\n",
 "  exhaust_policy_.synchronize(::growbox::app::output::BinaryOutputState::Off, monotonic_ms);\n  humidifier_policy_.synchronize(::growbox::app::output::BinaryOutputState::Off, monotonic_ms);\n"),
("    return applyBinary(role, level, monotonic_ms, exhaust_policy_, exhaust_,\n                       safety_force_exhaust_);\n",
 "    return applyBinary(role, level, monotonic_ms, exhaust_policy_, safety_force_exhaust_);\n"),
("    return applyBinary(role, level, monotonic_ms, humidifier_policy_, humidifier_, false);\n",
 "    return applyBinary(role, level, monotonic_ms, humidifier_policy_, false);\n"),
("  if (role == ClimateActuatorRole::ExhaustFan && exhaust_.known) {\n    return exhaust_.on ? 1.0F : 0.0F;\n  }\n  if (role == ClimateActuatorRole::Humidifier && humidifier_.known) {\n    return humidifier_.on ? 1.0F : 0.0F;\n  }\n",
 "  if (role == ClimateActuatorRole::ExhaustFan && exhaust_policy_.known()) {\n    return exhaust_policy_.on() ? 1.0F : 0.0F;\n  }\n  if (role == ClimateActuatorRole::Humidifier && humidifier_policy_.known()) {\n    return humidifier_policy_.on() ? 1.0F : 0.0F;\n  }\n"),
("    return forceBinaryOff(role, monotonic_ms, exhaust_policy_, exhaust_);\n",
 "    return forceBinaryOff(role, monotonic_ms, exhaust_policy_);\n"),
("    return forceBinaryOff(role, monotonic_ms, humidifier_policy_, humidifier_);\n",
 "    return forceBinaryOff(role, monotonic_ms, humidifier_policy_);\n"),
("    ::growbox::app::output::BinaryActuatorPolicy& policy, BinaryState& state,\n    bool force_on) noexcept {\n",
 "    ::growbox::app::output::BinaryActuatorPolicy& policy, bool force_on) noexcept {\n"),
("  syncPolicyCounters();\n\n  if (!proposal.command_required) {\n",
 "\n  if (!proposal.command_required) {\n"),
("    (void)policy.commit(proposal, false);\n    syncPolicyCounters();\n    return false;\n",
 "    (void)policy.commit(proposal, false);\n    return false;\n"),
("  if (!policy.commit(proposal, true)) {\n    syncPolicyCounters();\n    return false;\n  }\n  syncPolicyCounters();\n  state.known = policy.known();\n  state.on = policy.on();\n  state.last_change_ms = policy.lastChangeMs();\n  return true;\n",
 "  return policy.commit(proposal, true);\n"),
("    ::growbox::app::output::BinaryActuatorPolicy& policy, BinaryState& state) noexcept {\n",
 "    ::growbox::app::output::BinaryActuatorPolicy& policy) noexcept {\n"),
("    if (proposal.command_required) {\n      (void)policy.commit(proposal, false);\n    }\n    syncPolicyCounters();\n    return false;\n",
 "    if (proposal.command_required) {\n      (void)policy.commit(proposal, false);\n    }\n    return false;\n"),
("    if (!policy.commit(proposal, true)) {\n      syncPolicyCounters();\n      return false;\n    }\n",
 "    if (!policy.commit(proposal, true)) {\n      return false;\n    }\n"),
("  syncPolicyCounters();\n  state.known = policy.known();\n  state.on = policy.on();\n  state.last_change_ms = policy.lastChangeMs();\n  return true;\n",
 "  return true;\n")
]
for old, new in replacements_c:
    if old not in cs:
        raise SystemExit('cpp marker missing: ' + old[:80])
    cs = cs.replace(old, new, 1)

h.write_text(hs)
c.write_text(cs)
