from pathlib import Path

EXPECTED = '34ed66f92c7b11aa4038f34ddcbf63a38da93cff'


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    assert count == 1, f'{path}: expected one match, got {count}'
    p.write_text(text.replace(old, new, 1))

# Neutral climate-layer execution projection. The output module maps its supervisor
# projection into this contract; environment_control does not depend on app output types.
replace_once(
    'lib/environment_control/src/climate/ClimateTypes.h',
    '''struct ClimatePolicyRequest {\n  float heater = 0.0F, cooler = 0.0F, exhaust_fan = 0.0F, humidifier = 0.0F, dehumidifier = 0.0F,\n        co2_doser = 0.0F;\n};\n''',
    '''struct ClimatePolicyRequest {\n  float heater = 0.0F, cooler = 0.0F, exhaust_fan = 0.0F, humidifier = 0.0F, dehumidifier = 0.0F,\n        co2_doser = 0.0F;\n};\n\nenum ClimateExecutionKnownMask : std::uint8_t {\n  ClimateExecutionKnownNone = 0U,\n  ClimateExecutionKnownHeater = 1U << 0U,\n  ClimateExecutionKnownCooler = 1U << 1U,\n  ClimateExecutionKnownExhaustFan = 1U << 2U,\n  ClimateExecutionKnownHumidifier = 1U << 3U,\n  ClimateExecutionKnownDehumidifier = 1U << 4U,\n  ClimateExecutionKnownCo2Doser = 1U << 5U,\n  ClimateExecutionKnownAll = (1U << 6U) - 1U,\n};\n\nstruct ClimateExecutionProjection {\n  ClimatePolicyRequest executed{};\n  std::uint8_t known_mask = ClimateExecutionKnownNone;\n\n  bool known(ClimateExecutionKnownMask mask) const noexcept {\n    return (known_mask & static_cast<std::uint8_t>(mask)) != 0U;\n  }\n};\n'''
)

replace_once(
    'lib/environment_control/src/climate/ClimateRuntimeController.h',
    '''  ClimatePolicyRequest applied{};\n  EstimatedEffectiveClimateActions effective_after{};\n''',
    '''  ClimatePolicyRequest applied{};\n  ClimateExecutionProjection execution{};\n  EstimatedEffectiveClimateActions effective_after{};\n'''
)
replace_once(
    'lib/environment_control/src/climate/ClimateRuntimeController.h',
    '''  // Reconcile a decision after the actuator sink reports the levels that were\n  // actually accepted. This rewinds the estimator to effective_before and\n  // advances it with the confirmed physical command instead of the proposal.\n  void reconcileApplied(const ClimatePolicyRequest& confirmed_applied,\n                        const ClimateCapabilities& capabilities,\n                        ClimateRuntimeDecision& decision) noexcept;\n''',
    '''  // Reconcile estimator state from execution truth. Known roles use the\n  // executed command projection; unknown roles hold effective_before rather\n  // than being fabricated as OFF. No physical acknowledgement is implied.\n  void reconcileExecution(const ClimateExecutionProjection& execution,\n                          const ClimateCapabilities& capabilities,\n                          ClimateRuntimeDecision& decision) noexcept;\n\n  // Short migration wrapper for sinks/tests that still report a complete request.\n  void reconcileApplied(const ClimatePolicyRequest& confirmed_applied,\n                        const ClimateCapabilities& capabilities,\n                        ClimateRuntimeDecision& decision) noexcept;\n'''
)

replace_once(
    'lib/environment_control/src/climate/ClimateRuntimeController.cpp',
    '''void ClimateRuntimeController::reconcileApplied(const ClimatePolicyRequest& confirmed_applied,\n                                                const ClimateCapabilities& capabilities,\n                                                ClimateRuntimeDecision& decision) noexcept {\n  const float timestep =\n      std::isfinite(config_.timestep_s) && config_.timestep_s > 0.0F ? config_.timestep_s : 10.0F;\n  effective_estimator_.setState(decision.effective_before);\n  decision.applied = clipped(confirmed_applied);\n  decision.effective_after = effective_estimator_.update(decision.applied, timestep, capabilities);\n}\n''',
    '''void ClimateRuntimeController::reconcileExecution(const ClimateExecutionProjection& execution,\n                                                        const ClimateCapabilities& capabilities,\n                                                        ClimateRuntimeDecision& decision) noexcept {\n  const float timestep =\n      std::isfinite(config_.timestep_s) && config_.timestep_s > 0.0F ? config_.timestep_s : 10.0F;\n\n  const ClimatePolicyRequest bounded = clipped(execution.executed);\n  ClimatePolicyRequest estimator_request = bounded;\n  ClimatePolicyRequest compatibility_applied = decision.applied;\n\n  const auto reconcile_role = [&](ClimateExecutionKnownMask mask, float executed,\n                                  float effective_before, float& estimator_value,\n                                  float& applied_value) noexcept {\n    if (execution.known(mask)) {\n      estimator_value = executed;\n      applied_value = executed;\n    } else {\n      // Holding the estimator target at its previous effective value preserves\n      // the estimate exactly for an unreported role without inventing OFF/ON.\n      estimator_value = effective_before;\n    }\n  };\n\n  reconcile_role(ClimateExecutionKnownHeater, bounded.heater, decision.effective_before.heater,\n                 estimator_request.heater, compatibility_applied.heater);\n  reconcile_role(ClimateExecutionKnownCooler, bounded.cooler, decision.effective_before.cooler,\n                 estimator_request.cooler, compatibility_applied.cooler);\n  reconcile_role(ClimateExecutionKnownExhaustFan, bounded.exhaust_fan,\n                 decision.effective_before.exhaust_fan, estimator_request.exhaust_fan,\n                 compatibility_applied.exhaust_fan);\n  reconcile_role(ClimateExecutionKnownHumidifier, bounded.humidifier,\n                 decision.effective_before.humidifier, estimator_request.humidifier,\n                 compatibility_applied.humidifier);\n  reconcile_role(ClimateExecutionKnownDehumidifier, bounded.dehumidifier,\n                 decision.effective_before.dehumidifier, estimator_request.dehumidifier,\n                 compatibility_applied.dehumidifier);\n  reconcile_role(ClimateExecutionKnownCo2Doser, bounded.co2_doser,\n                 decision.effective_before.co2_doser, estimator_request.co2_doser,\n                 compatibility_applied.co2_doser);\n\n  effective_estimator_.setState(decision.effective_before);\n  decision.execution = execution;\n  decision.applied = clipped(compatibility_applied);\n  decision.effective_after = effective_estimator_.update(estimator_request, timestep, capabilities);\n}\n\nvoid ClimateRuntimeController::reconcileApplied(const ClimatePolicyRequest& confirmed_applied,\n                                                const ClimateCapabilities& capabilities,\n                                                ClimateRuntimeDecision& decision) noexcept {\n  ClimateExecutionProjection execution{};\n  execution.executed = confirmed_applied;\n  execution.known_mask = ClimateExecutionKnownAll;\n  reconcileExecution(execution, capabilities, decision);\n}\n'''
)

replace_once(
    'lib/environment_control/src/climate/ClimateControlLoop.cpp',
    '''  if (result.command_applied) {\n    runtime_.reconcileApplied(confirmed_applied, input.capabilities, decision);\n    previous_applied_ = previousFromRequest(decision.applied);\n''',
    '''  if (result.command_applied) {\n    ClimateExecutionProjection execution{};\n    execution.executed = confirmed_applied;\n    execution.known_mask = ClimateExecutionKnownAll;\n    runtime_.reconcileExecution(execution, input.capabilities, decision);\n    previous_applied_ = previousFromRequest(decision.applied);\n'''
)

# Focused controller test: unknown role must hold estimator truth; known OFF must decay it.
test_path = Path('test/test_climate_v6/test_main.cpp')
text = test_path.read_text()
anchor = '''void runtimeSafetyTest() {\n'''
assert text.count(anchor) == 1
new_test = r'''void runtimeExecutionReconcileTest() {
  using namespace growbox::climate;
  auto input = runtimeInput();
  ClimateRuntimeController controller{};
  ClimateRuntimeDecision decision{};

  controller.step(input, 0U, decision);
  ClimateExecutionProjection first_execution{};
  first_execution.executed = decision.applied;
  first_execution.known_mask = ClimateExecutionKnownAll;
  controller.reconcileExecution(first_execution, input.capabilities, decision);
  const float established = decision.effective_after.heater;
  check(established > 0.0F, "execution reconcile establishes heater estimate");

  controller.step(input, 10'000U, decision);
  const float before_unknown = decision.effective_before.heater;
  ClimateExecutionProjection unknown_heater{};
  unknown_heater.executed = decision.applied;
  unknown_heater.known_mask = static_cast<std::uint8_t>(
      ClimateExecutionKnownAll & ~ClimateExecutionKnownHeater);
  controller.reconcileExecution(unknown_heater, input.capabilities, decision);
  check(near(decision.effective_after.heater, before_unknown, 0.0001F),
        "unknown execution holds previous effective heater state");
  check(!decision.execution.known(ClimateExecutionKnownHeater),
        "decision preserves unknown execution truth");

  controller.step(input, 20'000U, decision);
  const float before_off = decision.effective_before.heater;
  ClimateExecutionProjection heater_off{};
  heater_off.executed = decision.applied;
  heater_off.executed.heater = 0.0F;
  heater_off.known_mask = ClimateExecutionKnownAll;
  controller.reconcileExecution(heater_off, input.capabilities, decision);
  check(decision.effective_after.heater < before_off,
        "known executed OFF decays heater estimate");
  check(decision.execution.known(ClimateExecutionKnownHeater),
        "decision records known execution truth");
}

'''
text = text.replace(anchor, new_test + anchor, 1)
main_anchor = '''  runtimePolicyModeTest();\n  runtimeSafetyTest();\n'''
assert text.count(main_anchor) == 1
text = text.replace(main_anchor, '''  runtimePolicyModeTest();\n  runtimeExecutionReconcileTest();\n  runtimeSafetyTest();\n''', 1)
test_path.write_text(text)
