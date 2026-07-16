#include "EnvironmentTypes.h"

namespace growbox {
namespace control {

namespace {

float valueAt(const RawModelDecision& decision, std::size_t index) noexcept {
  switch (index) {
  case 0U:
    return decision.heater;
  case 1U:
    return decision.fan;
  case 2U:
    return decision.humidifier;
  case 3U:
    return decision.dehumidifier;
  case 4U:
    return decision.cooler;
  case 5U:
    return decision.co2_doser;
  case 6U:
    return decision.irrigation_zone_1;
  case 7U:
    return decision.irrigation_zone_2;
  case 8U:
    return decision.irrigation_zone_3;
  case 9U:
    return decision.irrigation_zone_4;
  case 10U:
    return decision.nutrient_heater;
  case 11U:
    return decision.heat_mat_zone_1;
  case 12U:
    return decision.heat_mat_zone_2;
  case 13U:
    return decision.heat_mat_zone_3;
  case 14U:
    return decision.heat_mat_zone_4;
  default:
    return 0.0f;
  }
}

float& mutableValueAt(RawModelDecision& decision, std::size_t index) noexcept {
  switch (index) {
  case 0U:
    return decision.heater;
  case 1U:
    return decision.fan;
  case 2U:
    return decision.humidifier;
  case 3U:
    return decision.dehumidifier;
  case 4U:
    return decision.cooler;
  case 5U:
    return decision.co2_doser;
  case 6U:
    return decision.irrigation_zone_1;
  case 7U:
    return decision.irrigation_zone_2;
  case 8U:
    return decision.irrigation_zone_3;
  case 9U:
    return decision.irrigation_zone_4;
  case 10U:
    return decision.nutrient_heater;
  case 11U:
    return decision.heat_mat_zone_1;
  case 12U:
    return decision.heat_mat_zone_2;
  case 13U:
    return decision.heat_mat_zone_3;
  default:
    return decision.heat_mat_zone_4;
  }
}

float safeValueAt(const SafeControlDecision& decision, std::size_t index) noexcept {
  switch (index) {
  case 0U:
    return decision.heater;
  case 1U:
    return decision.fan;
  case 2U:
    return decision.humidifier;
  case 3U:
    return decision.dehumidifier;
  case 4U:
    return decision.cooler;
  case 5U:
    return decision.co2_doser;
  case 6U:
    return decision.irrigation_zone_1;
  case 7U:
    return decision.irrigation_zone_2;
  case 8U:
    return decision.irrigation_zone_3;
  case 9U:
    return decision.irrigation_zone_4;
  case 10U:
    return decision.nutrient_heater;
  case 11U:
    return decision.heat_mat_zone_1;
  case 12U:
    return decision.heat_mat_zone_2;
  case 13U:
    return decision.heat_mat_zone_3;
  case 14U:
    return decision.heat_mat_zone_4;
  default:
    return decision.heat_mat_zone_4;
  }
}

float& mutableSafeValueAt(SafeControlDecision& decision, std::size_t index) noexcept {
  switch (index) {
  case 0U:
    return decision.heater;
  case 1U:
    return decision.fan;
  case 2U:
    return decision.humidifier;
  case 3U:
    return decision.dehumidifier;
  case 4U:
    return decision.cooler;
  case 5U:
    return decision.co2_doser;
  case 6U:
    return decision.irrigation_zone_1;
  case 7U:
    return decision.irrigation_zone_2;
  case 8U:
    return decision.irrigation_zone_3;
  case 9U:
    return decision.irrigation_zone_4;
  case 10U:
    return decision.nutrient_heater;
  case 11U:
    return decision.heat_mat_zone_1;
  case 12U:
    return decision.heat_mat_zone_2;
  case 13U:
    return decision.heat_mat_zone_3;
  default:
    return decision.heat_mat_zone_4;
  }
}

} // namespace

float rawOutputValue(const RawModelDecision& decision, schema::OutputIndex output) noexcept {
  return valueAt(decision, schema::index(output));
}

float& rawOutputValue(RawModelDecision& decision, schema::OutputIndex output) noexcept {
  return mutableValueAt(decision, schema::index(output));
}

float safeOutputValue(const SafeControlDecision& decision, schema::OutputIndex output) noexcept {
  return safeValueAt(decision, schema::index(output));
}

float& safeOutputValue(SafeControlDecision& decision, schema::OutputIndex output) noexcept {
  return mutableSafeValueAt(decision, schema::index(output));
}

} // namespace control
} // namespace growbox
