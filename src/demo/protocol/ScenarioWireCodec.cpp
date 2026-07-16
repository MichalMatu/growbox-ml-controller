#include "ScenarioWireCodec.h"

#include "EnvironmentTypes.h"

#include <cJSON.h>

#include <cmath>
#include <cstring>
#include <limits>

namespace growbox {
namespace demo {
namespace wire {
namespace {

using control::schema::FeatureIndex;

const cJSON* item(const cJSON* object, const char* key) noexcept {
  return cJSON_IsObject(object) ? cJSON_GetObjectItemCaseSensitive(object, key) : nullptr;
}

const cJSON* objectItem(const cJSON* object, const char* key) noexcept {
  const cJSON* value = item(object, key);
  return cJSON_IsObject(value) ? value : nullptr;
}

const cJSON* arrayItem(const cJSON* object, const char* key) noexcept {
  const cJSON* value = item(object, key);
  return cJSON_IsArray(value) ? value : nullptr;
}

bool readFiniteFloat(const cJSON* object, const char* key, float& destination) noexcept {
  const cJSON* value = item(object, key);
  if (!cJSON_IsNumber(value) || !std::isfinite(value->valuedouble) ||
      std::fabs(value->valuedouble) > std::numeric_limits<float>::max()) {
    return false;
  }
  const float parsed = static_cast<float>(value->valuedouble);
  if (!std::isfinite(parsed)) {
    return false;
  }
  destination = parsed;
  return true;
}

bool readOptionalFiniteFloat(const cJSON* object, const char* key, float& destination) noexcept {
  const cJSON* value = item(object, key);
  if (value == nullptr || cJSON_IsNull(value)) {
    return true;
  }
  return readFiniteFloat(object, key, destination);
}

bool readBool(const cJSON* object, const char* key, bool& destination) noexcept {
  const cJSON* value = item(object, key);
  if (!cJSON_IsBool(value)) {
    return false;
  }
  destination = cJSON_IsTrue(value);
  return true;
}

bool readOptionalBool(const cJSON* object, const char* key, bool& destination) noexcept {
  const cJSON* value = item(object, key);
  if (value == nullptr || cJSON_IsNull(value)) {
    return true;
  }
  return readBool(object, key, destination);
}

bool readUnsigned(const cJSON* object, const char* key, std::uint32_t& destination) noexcept {
  const cJSON* value = item(object, key);
  if (!cJSON_IsNumber(value) || !std::isfinite(value->valuedouble) || value->valuedouble < 0.0 ||
      value->valuedouble > static_cast<double>(std::numeric_limits<std::uint32_t>::max()) ||
      std::floor(value->valuedouble) != value->valuedouble) {
    return false;
  }
  destination = static_cast<std::uint32_t>(value->valuedouble);
  return true;
}

const char* readString(const cJSON* object, const char* key) noexcept {
  const cJSON* value = item(object, key);
  return cJSON_IsString(value) && value->valuestring != nullptr ? value->valuestring : nullptr;
}

FeatureIndex zoneAvailableIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::Pot1Available;
  case 1U:
    return FeatureIndex::Pot2Available;
  case 2U:
    return FeatureIndex::Pot3Available;
  default:
    return FeatureIndex::Pot4Available;
  }
}

FeatureIndex zoneSoilMoistureIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::SoilMoisturePot1Pct;
  case 1U:
    return FeatureIndex::SoilMoisturePot2Pct;
  case 2U:
    return FeatureIndex::SoilMoisturePot3Pct;
  default:
    return FeatureIndex::SoilMoisturePot4Pct;
  }
}

FeatureIndex zoneSoilTemperatureIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::SoilTemperaturePot1C;
  case 1U:
    return FeatureIndex::SoilTemperaturePot2C;
  case 2U:
    return FeatureIndex::SoilTemperaturePot3C;
  default:
    return FeatureIndex::SoilTemperaturePot4C;
  }
}

FeatureIndex zoneSoilMoistureValidIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::SoilMoisturePot1Valid;
  case 1U:
    return FeatureIndex::SoilMoisturePot2Valid;
  case 2U:
    return FeatureIndex::SoilMoisturePot3Valid;
  default:
    return FeatureIndex::SoilMoisturePot4Valid;
  }
}

FeatureIndex zoneSoilTemperatureValidIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::SoilTemperaturePot1Valid;
  case 1U:
    return FeatureIndex::SoilTemperaturePot2Valid;
  case 2U:
    return FeatureIndex::SoilTemperaturePot3Valid;
  default:
    return FeatureIndex::SoilTemperaturePot4Valid;
  }
}

FeatureIndex zonePotVolumeIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::Pot1PotVolumeL;
  case 1U:
    return FeatureIndex::Pot2PotVolumeL;
  case 2U:
    return FeatureIndex::Pot3PotVolumeL;
  default:
    return FeatureIndex::Pot4PotVolumeL;
  }
}

FeatureIndex zoneSubstrateCapacityIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::Pot1SubstrateWaterCapacityMl;
  case 1U:
    return FeatureIndex::Pot2SubstrateWaterCapacityMl;
  case 2U:
    return FeatureIndex::Pot3SubstrateWaterCapacityMl;
  default:
    return FeatureIndex::Pot4SubstrateWaterCapacityMl;
  }
}

FeatureIndex zoneTranspirationIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::Pot1TranspirationFactor;
  case 1U:
    return FeatureIndex::Pot2TranspirationFactor;
  case 2U:
    return FeatureIndex::Pot3TranspirationFactor;
  default:
    return FeatureIndex::Pot4TranspirationFactor;
  }
}

FeatureIndex zoneTargetSoilMoistureIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::Pot1TargetSoilMoisturePct;
  case 1U:
    return FeatureIndex::Pot2TargetSoilMoisturePct;
  case 2U:
    return FeatureIndex::Pot3TargetSoilMoisturePct;
  default:
    return FeatureIndex::Pot4TargetSoilMoisturePct;
  }
}

FeatureIndex zoneIrrigationAvailableIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::Pot1IrrigationAvailable;
  case 1U:
    return FeatureIndex::Pot2IrrigationAvailable;
  case 2U:
    return FeatureIndex::Pot3IrrigationAvailable;
  default:
    return FeatureIndex::Pot4IrrigationAvailable;
  }
}

FeatureIndex zoneIrrigationFlowIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::Pot1IrrigationFlowMlS;
  case 1U:
    return FeatureIndex::Pot2IrrigationFlowMlS;
  case 2U:
    return FeatureIndex::Pot3IrrigationFlowMlS;
  default:
    return FeatureIndex::Pot4IrrigationFlowMlS;
  }
}

FeatureIndex zoneIrrigationMaximumPulseIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::Pot1IrrigationMaximumPulseS;
  case 1U:
    return FeatureIndex::Pot2IrrigationMaximumPulseS;
  case 2U:
    return FeatureIndex::Pot3IrrigationMaximumPulseS;
  default:
    return FeatureIndex::Pot4IrrigationMaximumPulseS;
  }
}

FeatureIndex zoneIrrigationMinimumIntervalIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::Pot1IrrigationMinimumIntervalS;
  case 1U:
    return FeatureIndex::Pot2IrrigationMinimumIntervalS;
  case 2U:
    return FeatureIndex::Pot3IrrigationMinimumIntervalS;
  default:
    return FeatureIndex::Pot4IrrigationMinimumIntervalS;
  }
}

FeatureIndex zoneIrrigationControlTypeIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::Pot1IrrigationControlType;
  case 1U:
    return FeatureIndex::Pot2IrrigationControlType;
  case 2U:
    return FeatureIndex::Pot3IrrigationControlType;
  default:
    return FeatureIndex::Pot4IrrigationControlType;
  }
}

FeatureIndex zonePreviousIrrigationIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::Pot1PreviousIrrigation;
  case 1U:
    return FeatureIndex::Pot2PreviousIrrigation;
  case 2U:
    return FeatureIndex::Pot3PreviousIrrigation;
  default:
    return FeatureIndex::Pot4PreviousIrrigation;
  }
}

FeatureIndex zoneTargetSoilTemperatureIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::Pot1TargetSoilTemperatureC;
  case 1U:
    return FeatureIndex::Pot2TargetSoilTemperatureC;
  case 2U:
    return FeatureIndex::Pot3TargetSoilTemperatureC;
  default:
    return FeatureIndex::Pot4TargetSoilTemperatureC;
  }
}

FeatureIndex zoneHeatMatAvailableIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::Pot1HeatMatAvailable;
  case 1U:
    return FeatureIndex::Pot2HeatMatAvailable;
  case 2U:
    return FeatureIndex::Pot3HeatMatAvailable;
  default:
    return FeatureIndex::Pot4HeatMatAvailable;
  }
}

FeatureIndex zoneHeatMatMaxPowerIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::Pot1HeatMatMaxPowerW;
  case 1U:
    return FeatureIndex::Pot2HeatMatMaxPowerW;
  case 2U:
    return FeatureIndex::Pot3HeatMatMaxPowerW;
  default:
    return FeatureIndex::Pot4HeatMatMaxPowerW;
  }
}

FeatureIndex zoneHeatMatControlTypeIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::Pot1HeatMatControlType;
  case 1U:
    return FeatureIndex::Pot2HeatMatControlType;
  case 2U:
    return FeatureIndex::Pot3HeatMatControlType;
  default:
    return FeatureIndex::Pot4HeatMatControlType;
  }
}

FeatureIndex zonePreviousHeatMatIndex(std::size_t pot_index) noexcept {
  switch (pot_index) {
  case 0U:
    return FeatureIndex::Pot1PreviousHeatMat;
  case 1U:
    return FeatureIndex::Pot2PreviousHeatMat;
  case 2U:
    return FeatureIndex::Pot3PreviousHeatMat;
  default:
    return FeatureIndex::Pot4PreviousHeatMat;
  }
}

bool parseSensors(const cJSON* object, control::SensorState& sensors) noexcept {
  return object != nullptr &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::AirTemperatureC),
                         sensors.air_temperature_c) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::AirHumidityPct),
                         sensors.air_humidity_pct) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::Co2Ppm), sensors.co2_ppm) &&
         readFiniteFloat(object,
                         control::schema::wireKey(FeatureIndex::NutrientSolutionTemperatureC),
                         sensors.nutrient_solution_temperature_c) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::OutsideTemperatureC),
                         sensors.outside_temperature_c) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::OutsideHumidityPct),
                         sensors.outside_humidity_pct) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::OutsideCo2Ppm),
                         sensors.outside_co2_ppm);
}

bool parseValidity(const cJSON* object, control::SensorValidity& validity) noexcept {
  return object != nullptr &&
         readBool(object, control::schema::wireKey(FeatureIndex::AirTemperatureValid),
                  validity.air_temperature) &&
         readBool(object, control::schema::wireKey(FeatureIndex::AirHumidityValid),
                  validity.air_humidity) &&
         readBool(object, control::schema::wireKey(FeatureIndex::Co2Valid), validity.co2) &&
         readBool(object, control::schema::wireKey(FeatureIndex::NutrientSolutionTemperatureValid),
                  validity.nutrient_solution_temperature) &&
         readBool(object, control::schema::wireKey(FeatureIndex::OutsideTemperatureValid),
                  validity.outside_temperature) &&
         readBool(object, control::schema::wireKey(FeatureIndex::OutsideHumidityValid),
                  validity.outside_humidity) &&
         readBool(object, control::schema::wireKey(FeatureIndex::OutsideCo2Valid),
                  validity.outside_co2);
}

bool parseEnvironment(const cJSON* object, control::EnvironmentConfig& config) noexcept {
  return object != nullptr &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::GrowboxVolumeM3),
                         config.growbox_volume_m3) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::ThermalMassJPerK),
                         config.thermal_mass_j_per_k) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::HeatLossWPerK),
                         config.heat_loss_w_per_k) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::AirLeakRateAch),
                         config.air_leak_rate_ach);
}

bool parsePseudo(const cJSON* object, bool& lights_active) noexcept {
  return object != nullptr &&
         readBool(object, control::schema::wireKey(FeatureIndex::LightsActive), lights_active);
}

const char* controlTypeName(control::ActuatorControlType type) noexcept {
  return type == control::ActuatorControlType::Pwm ? "pwm" : "binary";
}

bool parseControlType(const char* control_type,
                      control::ActuatorControlType& destination) noexcept {
  if (control_type != nullptr && std::strcmp(control_type, "binary") == 0) {
    destination = control::ActuatorControlType::Binary;
    return true;
  }
  if (control_type != nullptr && std::strcmp(control_type, "pwm") == 0) {
    destination = control::ActuatorControlType::Pwm;
    return true;
  }
  return false;
}

bool parseZoneCultivation(const cJSON* object, control::PotCultivationConfig& cultivation,
                          std::size_t pot_index) noexcept {
  return object != nullptr &&
         readFiniteFloat(object, control::schema::wireKey(zonePotVolumeIndex(pot_index)),
                         cultivation.pot_volume_l) &&
         readFiniteFloat(object, control::schema::wireKey(zoneSubstrateCapacityIndex(pot_index)),
                         cultivation.substrate_water_capacity_ml) &&
         readFiniteFloat(object, control::schema::wireKey(zoneTranspirationIndex(pot_index)),
                         cultivation.transpiration_factor);
}

bool parseZoneHeatMat(const cJSON* object, control::HeatMatCapabilities& heat_mat,
                      std::size_t pot_index) noexcept {
  if (object == nullptr) {
    return true;
  }
  control::ActuatorControlType control_type = control::ActuatorControlType::Binary;
  if (!parseControlType(
          readString(object, control::schema::wireKey(zoneHeatMatControlTypeIndex(pot_index))),
          control_type)) {
    return false;
  }
  heat_mat.control_type = control_type;
  return readOptionalBool(object, control::schema::wireKey(zoneHeatMatAvailableIndex(pot_index)),
                          heat_mat.available) &&
         readOptionalFiniteFloat(object,
                                 control::schema::wireKey(zoneHeatMatMaxPowerIndex(pot_index)),
                                 heat_mat.max_power_w);
}

bool parseZoneIrrigation(const cJSON* object, control::IrrigationPumpCapabilities& irrigation,
                         std::size_t pot_index) noexcept {
  if (object == nullptr) {
    return false;
  }
  control::ActuatorControlType control_type = control::ActuatorControlType::Binary;
  if (!parseControlType(
          readString(object, control::schema::wireKey(zoneIrrigationControlTypeIndex(pot_index))),
          control_type)) {
    return false;
  }
  irrigation.control_type = control_type;
  return readBool(object, control::schema::wireKey(zoneIrrigationAvailableIndex(pot_index)),
                  irrigation.available) &&
         readFiniteFloat(object, control::schema::wireKey(zoneIrrigationFlowIndex(pot_index)),
                         irrigation.flow_ml_s) &&
         readFiniteFloat(object,
                         control::schema::wireKey(zoneIrrigationMaximumPulseIndex(pot_index)),
                         irrigation.maximum_pulse_s) &&
         readFiniteFloat(object,
                         control::schema::wireKey(zoneIrrigationMinimumIntervalIndex(pot_index)),
                         irrigation.minimum_interval_s);
}

bool parseZoneObject(const cJSON* object, control::PotConfig& pot, std::size_t pot_index) noexcept {
  const cJSON* sensors = objectItem(object, "sensors");
  const cJSON* validity = objectItem(object, "validity");
  const cJSON* cultivation = objectItem(object, "cultivation");
  const cJSON* targets = objectItem(object, "targets");
  const cJSON* irrigation = objectItem(object, "irrigation");
  const cJSON* heat_mat = objectItem(object, "heat_mat");
  const cJSON* previous = objectItem(object, "previous");
  return object != nullptr &&
         readBool(object, control::schema::wireKey(zoneAvailableIndex(pot_index)), pot.available) &&
         sensors != nullptr &&
         readFiniteFloat(sensors, control::schema::wireKey(zoneSoilMoistureIndex(pot_index)),
                         pot.sensors.soil_moisture_pct) &&
         readFiniteFloat(sensors, control::schema::wireKey(zoneSoilTemperatureIndex(pot_index)),
                         pot.sensors.soil_temperature_c) &&
         validity != nullptr &&
         readBool(validity, control::schema::wireKey(zoneSoilMoistureValidIndex(pot_index)),
                  pot.validity.soil_moisture) &&
         readBool(validity, control::schema::wireKey(zoneSoilTemperatureValidIndex(pot_index)),
                  pot.validity.soil_temperature) &&
         parseZoneCultivation(cultivation, pot.cultivation, pot_index) && targets != nullptr &&
         readFiniteFloat(targets, control::schema::wireKey(zoneTargetSoilMoistureIndex(pot_index)),
                         pot.target_soil_moisture_pct) &&
         readOptionalFiniteFloat(
             targets, control::schema::wireKey(zoneTargetSoilTemperatureIndex(pot_index)),
             pot.target_soil_temperature_c) &&
         parseZoneIrrigation(irrigation, pot.irrigation, pot_index) &&
         parseZoneHeatMat(heat_mat, pot.heat_mat, pot_index) && previous != nullptr &&
         readFiniteFloat(previous, control::schema::wireKey(zonePreviousIrrigationIndex(pot_index)),
                         pot.previous_irrigation) &&
         readOptionalFiniteFloat(previous,
                                 control::schema::wireKey(zonePreviousHeatMatIndex(pot_index)),
                                 pot.previous_heat_mat);
}

bool parseZones(const cJSON* array,
                std::array<control::PotConfig, control::kMaxPots>& pots) noexcept {
  if (array == nullptr ||
      static_cast<std::size_t>(cJSON_GetArraySize(array)) != control::kMaxPots) {
    return false;
  }
  for (std::size_t pot_index = 0U; pot_index < control::kMaxPots; ++pot_index) {
    const cJSON* zone_json = cJSON_GetArrayItem(array, static_cast<int>(pot_index));
    if (!parseZoneObject(zone_json, pots[pot_index], pot_index)) {
      return false;
    }
  }
  return true;
}

bool parseTargets(const cJSON* object, control::ControlTargets& targets,
                  bool require_all) noexcept {
  if (object == nullptr) {
    return false;
  }

  bool parsed_any = false;
  auto read_optional = [&](const char* key, float& destination) {
    const cJSON* value = item(object, key);
    if (value == nullptr || cJSON_IsNull(value)) {
      return !require_all;
    }
    parsed_any = true;
    return readFiniteFloat(object, key, destination);
  };

  const bool valid =
      read_optional(control::schema::wireKey(FeatureIndex::TargetAirTemperatureC),
                    targets.air_temperature_c) &&
      read_optional(control::schema::wireKey(FeatureIndex::TargetAirHumidityPct),
                    targets.air_humidity_pct) &&
      read_optional(control::schema::wireKey(FeatureIndex::TargetCo2Ppm), targets.co2_ppm) &&
      read_optional(control::schema::wireKey(FeatureIndex::TargetNutrientSolutionTemperatureC),
                    targets.nutrient_solution_temperature_c);
  return valid && (require_all || parsed_any);
}

bool parsePrevious(const cJSON* object, control::PreviousControlState& previous) noexcept {
  return object != nullptr &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::PreviousHeater),
                         previous.heater) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::PreviousFan),
                         previous.fan) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::PreviousHumidifier),
                         previous.humidifier) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::PreviousDehumidifier),
                         previous.dehumidifier) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::PreviousCooler),
                         previous.cooler) &&
         readFiniteFloat(object, control::schema::wireKey(FeatureIndex::PreviousCo2Doser),
                         previous.co2_doser) &&
         readOptionalFiniteFloat(object,
                                 control::schema::wireKey(FeatureIndex::PreviousNutrientHeater),
                                 previous.nutrient_heater);
}

bool parseSafety(const cJSON* object, control::SafetyConfig& safety) noexcept {
  if (object == nullptr || cJSON_IsNull(object)) {
    return true;
  }
  return readOptionalFiniteFloat(object, "maximum_air_temperature_c",
                                 safety.maximum_air_temperature_c) &&
         readOptionalFiniteFloat(object, "alarm_air_temperature_c",
                                 safety.alarm_air_temperature_c) &&
         readOptionalFiniteFloat(object, "alarm_minimum_fan", safety.alarm_minimum_fan) &&
         readOptionalFiniteFloat(object, "binary_threshold", safety.binary_threshold) &&
         readOptionalFiniteFloat(object, "heater_minimum_on_s", safety.heater_minimum_on_s) &&
         readOptionalFiniteFloat(object, "heater_minimum_off_s", safety.heater_minimum_off_s) &&
         readOptionalFiniteFloat(object, "humidifier_minimum_on_s",
                                 safety.humidifier_minimum_on_s) &&
         readOptionalFiniteFloat(object, "humidifier_minimum_off_s",
                                 safety.humidifier_minimum_off_s) &&
         readOptionalFiniteFloat(object, "dehumidifier_minimum_on_s",
                                 safety.dehumidifier_minimum_on_s) &&
         readOptionalFiniteFloat(object, "dehumidifier_minimum_off_s",
                                 safety.dehumidifier_minimum_off_s) &&
         readOptionalFiniteFloat(object, "cooler_minimum_on_s", safety.cooler_minimum_on_s) &&
         readOptionalFiniteFloat(object, "cooler_minimum_off_s", safety.cooler_minimum_off_s) &&
         readOptionalFiniteFloat(object, "co2_doser_minimum_interval_s",
                                 safety.co2_doser_minimum_interval_s) &&
         readOptionalFiniteFloat(object, "fan_venting_co2_threshold",
                                 safety.fan_venting_co2_threshold) &&
         readOptionalFiniteFloat(object, "maximum_nutrient_soil_delta_c",
                                 safety.maximum_nutrient_soil_delta_c) &&
         readOptionalFiniteFloat(object, "minimum_nutrient_solution_temperature_c",
                                 safety.minimum_nutrient_solution_temperature_c);
}

bool parseActuators(const cJSON* object, control::GlobalActuatorCapabilities& actuators) noexcept {
  if (object == nullptr) {
    return false;
  }

  const cJSON* heater = objectItem(object, control::schema::kWireObjectHeater);
  const cJSON* fan = objectItem(object, control::schema::kWireObjectFan);
  const cJSON* humidifier = objectItem(object, control::schema::kWireObjectHumidifier);
  const cJSON* dehumidifier = objectItem(object, control::schema::kWireObjectDehumidifier);
  const cJSON* cooler = objectItem(object, control::schema::kWireObjectCooler);
  const cJSON* co2_doser = objectItem(object, control::schema::kWireObjectCo2Doser);
  const cJSON* nutrient_heater = objectItem(object, control::schema::kWireObjectNutrientHeater);
  if (heater == nullptr || fan == nullptr || humidifier == nullptr || dehumidifier == nullptr ||
      cooler == nullptr || co2_doser == nullptr) {
    return false;
  }

  const bool parsed_core =
      readBool(heater, control::schema::wireKey(FeatureIndex::HeaterAvailable),
               actuators.heater.available) &&
      readFiniteFloat(heater, control::schema::wireKey(FeatureIndex::HeaterMaxPowerW),
                      actuators.heater.max_power_w) &&
      readFiniteFloat(heater, control::schema::wireKey(FeatureIndex::HeaterEfficiency),
                      actuators.heater.efficiency) &&
      readBool(fan, control::schema::wireKey(FeatureIndex::FanAvailable),
               actuators.fan.available) &&
      readFiniteFloat(fan, control::schema::wireKey(FeatureIndex::FanMaxAirflowM3H),
                      actuators.fan.max_airflow_m3_h) &&
      readFiniteFloat(fan, control::schema::wireKey(FeatureIndex::FanMinimumCommand),
                      actuators.fan.minimum_command) &&
      readBool(humidifier, control::schema::wireKey(FeatureIndex::HumidifierAvailable),
               actuators.humidifier.available) &&
      readFiniteFloat(humidifier, control::schema::wireKey(FeatureIndex::HumidifierMaxOutputGH),
                      actuators.humidifier.max_output_g_h) &&
      readBool(dehumidifier, control::schema::wireKey(FeatureIndex::DehumidifierAvailable),
               actuators.dehumidifier.available) &&
      readFiniteFloat(dehumidifier,
                      control::schema::wireKey(FeatureIndex::DehumidifierMaxRemovalGH),
                      actuators.dehumidifier.max_removal_g_h) &&
      readBool(cooler, control::schema::wireKey(FeatureIndex::CoolerAvailable),
               actuators.cooler.available) &&
      readFiniteFloat(cooler, control::schema::wireKey(FeatureIndex::CoolerMaxCoolingW),
                      actuators.cooler.max_cooling_w) &&
      readBool(co2_doser, control::schema::wireKey(FeatureIndex::Co2DoserAvailable),
               actuators.co2_doser.available) &&
      readFiniteFloat(co2_doser,
                      control::schema::wireKey(FeatureIndex::Co2DoserDosePpmPerFullPulse),
                      actuators.co2_doser.dose_ppm_per_full_pulse) &&
      readFiniteFloat(co2_doser, control::schema::wireKey(FeatureIndex::Co2DoserMaximumPulseS),
                      actuators.co2_doser.maximum_pulse_s);
  if (!parsed_core) {
    return false;
  }
  if (nutrient_heater == nullptr) {
    return true;
  }
  return readOptionalBool(nutrient_heater,
                          control::schema::wireKey(FeatureIndex::NutrientHeaterAvailable),
                          actuators.nutrient_heater.available) &&
         readOptionalFiniteFloat(nutrient_heater,
                                 control::schema::wireKey(FeatureIndex::NutrientHeaterMaxPowerW),
                                 actuators.nutrient_heater.max_power_w) &&
         readOptionalFiniteFloat(nutrient_heater,
                                 control::schema::wireKey(FeatureIndex::NutrientHeaterEfficiency),
                                 actuators.nutrient_heater.efficiency);
}

void addZoneSnapshot(cJSON* zone_json, const control::PotConfig& pot,
                     std::size_t pot_index) noexcept {
  if (zone_json == nullptr) {
    return;
  }

  cJSON_AddBoolToObject(zone_json, control::schema::wireKey(zoneAvailableIndex(pot_index)),
                        pot.available);

  cJSON* sensors = cJSON_AddObjectToObject(zone_json, "sensors");
  cJSON_AddNumberToObject(sensors, control::schema::wireKey(zoneSoilMoistureIndex(pot_index)),
                          pot.sensors.soil_moisture_pct);
  cJSON_AddNumberToObject(sensors, control::schema::wireKey(zoneSoilTemperatureIndex(pot_index)),
                          pot.sensors.soil_temperature_c);

  cJSON* validity = cJSON_AddObjectToObject(zone_json, "validity");
  cJSON_AddBoolToObject(validity, control::schema::wireKey(zoneSoilMoistureValidIndex(pot_index)),
                        pot.validity.soil_moisture);
  cJSON_AddBoolToObject(validity,
                        control::schema::wireKey(zoneSoilTemperatureValidIndex(pot_index)),
                        pot.validity.soil_temperature);

  cJSON* cultivation = cJSON_AddObjectToObject(zone_json, "cultivation");
  cJSON_AddNumberToObject(cultivation, control::schema::wireKey(zonePotVolumeIndex(pot_index)),
                          pot.cultivation.pot_volume_l);
  cJSON_AddNumberToObject(cultivation,
                          control::schema::wireKey(zoneSubstrateCapacityIndex(pot_index)),
                          pot.cultivation.substrate_water_capacity_ml);
  cJSON_AddNumberToObject(cultivation, control::schema::wireKey(zoneTranspirationIndex(pot_index)),
                          pot.cultivation.transpiration_factor);

  cJSON* targets = cJSON_AddObjectToObject(zone_json, "targets");
  cJSON_AddNumberToObject(targets, control::schema::wireKey(zoneTargetSoilMoistureIndex(pot_index)),
                          pot.target_soil_moisture_pct);
  cJSON_AddNumberToObject(targets,
                          control::schema::wireKey(zoneTargetSoilTemperatureIndex(pot_index)),
                          pot.target_soil_temperature_c);

  cJSON* irrigation = cJSON_AddObjectToObject(zone_json, "irrigation");
  cJSON_AddBoolToObject(irrigation,
                        control::schema::wireKey(zoneIrrigationAvailableIndex(pot_index)),
                        pot.irrigation.available);
  cJSON_AddNumberToObject(irrigation, control::schema::wireKey(zoneIrrigationFlowIndex(pot_index)),
                          pot.irrigation.flow_ml_s);
  cJSON_AddNumberToObject(irrigation,
                          control::schema::wireKey(zoneIrrigationMaximumPulseIndex(pot_index)),
                          pot.irrigation.maximum_pulse_s);
  cJSON_AddNumberToObject(irrigation,
                          control::schema::wireKey(zoneIrrigationMinimumIntervalIndex(pot_index)),
                          pot.irrigation.minimum_interval_s);
  cJSON_AddStringToObject(irrigation,
                          control::schema::wireKey(zoneIrrigationControlTypeIndex(pot_index)),
                          controlTypeName(pot.irrigation.control_type));

  cJSON* heat_mat = cJSON_AddObjectToObject(zone_json, "heat_mat");
  cJSON_AddBoolToObject(heat_mat, control::schema::wireKey(zoneHeatMatAvailableIndex(pot_index)),
                        pot.heat_mat.available);
  cJSON_AddNumberToObject(heat_mat, control::schema::wireKey(zoneHeatMatMaxPowerIndex(pot_index)),
                          pot.heat_mat.max_power_w);
  cJSON_AddStringToObject(heat_mat,
                          control::schema::wireKey(zoneHeatMatControlTypeIndex(pot_index)),
                          controlTypeName(pot.heat_mat.control_type));

  cJSON* previous = cJSON_AddObjectToObject(zone_json, "previous");
  cJSON_AddNumberToObject(previous,
                          control::schema::wireKey(zonePreviousIrrigationIndex(pot_index)),
                          pot.previous_irrigation);
  cJSON_AddNumberToObject(previous, control::schema::wireKey(zonePreviousHeatMatIndex(pot_index)),
                          pot.previous_heat_mat);
}

void addActuatorAvailability(cJSON* document,
                             const control::GlobalActuatorCapabilities& actuators) noexcept {
  if (document == nullptr) {
    return;
  }
  cJSON* actuators_json = cJSON_AddObjectToObject(document, "actuators");
  cJSON* heater_json = cJSON_AddObjectToObject(actuators_json, "heater");
  cJSON_AddBoolToObject(heater_json, "available", actuators.heater.available);
  cJSON* fan_json = cJSON_AddObjectToObject(actuators_json, "fan");
  cJSON_AddBoolToObject(fan_json, "available", actuators.fan.available);
  cJSON* humidifier_json = cJSON_AddObjectToObject(actuators_json, "humidifier");
  cJSON_AddBoolToObject(humidifier_json, "available", actuators.humidifier.available);
  cJSON* dehumidifier_json = cJSON_AddObjectToObject(actuators_json, "dehumidifier");
  cJSON_AddBoolToObject(dehumidifier_json, "available", actuators.dehumidifier.available);
  cJSON* cooler_json = cJSON_AddObjectToObject(actuators_json, "cooler");
  cJSON_AddBoolToObject(cooler_json, "available", actuators.cooler.available);
  cJSON* co2_doser_json = cJSON_AddObjectToObject(actuators_json, "co2_doser");
  cJSON_AddBoolToObject(co2_doser_json, "available", actuators.co2_doser.available);
  cJSON* nutrient_heater_json =
      cJSON_AddObjectToObject(actuators_json, control::schema::kWireObjectNutrientHeater);
  cJSON_AddBoolToObject(nutrient_heater_json, "available", actuators.nutrient_heater.available);
}

} // namespace

void addScenarioSnapshot(cJSON* document, const control::ControllerInput& input) noexcept {
  if (document == nullptr) {
    return;
  }

  cJSON* sensors = cJSON_AddObjectToObject(document, control::schema::kWireRootSensors);
  cJSON_AddNumberToObject(sensors, control::schema::wireKey(FeatureIndex::AirTemperatureC),
                          input.sensors.air_temperature_c);
  cJSON_AddNumberToObject(sensors, control::schema::wireKey(FeatureIndex::AirHumidityPct),
                          input.sensors.air_humidity_pct);
  cJSON_AddNumberToObject(sensors, control::schema::wireKey(FeatureIndex::Co2Ppm),
                          input.sensors.co2_ppm);
  cJSON_AddNumberToObject(sensors,
                          control::schema::wireKey(FeatureIndex::NutrientSolutionTemperatureC),
                          input.sensors.nutrient_solution_temperature_c);
  cJSON_AddNumberToObject(sensors, control::schema::wireKey(FeatureIndex::OutsideTemperatureC),
                          input.sensors.outside_temperature_c);
  cJSON_AddNumberToObject(sensors, control::schema::wireKey(FeatureIndex::OutsideHumidityPct),
                          input.sensors.outside_humidity_pct);
  cJSON_AddNumberToObject(sensors, control::schema::wireKey(FeatureIndex::OutsideCo2Ppm),
                          input.sensors.outside_co2_ppm);

  cJSON* validity = cJSON_AddObjectToObject(document, control::schema::kWireRootValidity);
  cJSON_AddBoolToObject(validity, control::schema::wireKey(FeatureIndex::AirTemperatureValid),
                        input.validity.air_temperature);
  cJSON_AddBoolToObject(validity, control::schema::wireKey(FeatureIndex::AirHumidityValid),
                        input.validity.air_humidity);
  cJSON_AddBoolToObject(validity, control::schema::wireKey(FeatureIndex::Co2Valid),
                        input.validity.co2);
  cJSON_AddBoolToObject(validity,
                        control::schema::wireKey(FeatureIndex::NutrientSolutionTemperatureValid),
                        input.validity.nutrient_solution_temperature);
  cJSON_AddBoolToObject(validity, control::schema::wireKey(FeatureIndex::OutsideTemperatureValid),
                        input.validity.outside_temperature);
  cJSON_AddBoolToObject(validity, control::schema::wireKey(FeatureIndex::OutsideHumidityValid),
                        input.validity.outside_humidity);
  cJSON_AddBoolToObject(validity, control::schema::wireKey(FeatureIndex::OutsideCo2Valid),
                        input.validity.outside_co2);

  cJSON* pots = cJSON_AddArrayToObject(document, control::schema::kWireRootPots);
  for (std::size_t pot_index = 0U; pot_index < control::kMaxPots; ++pot_index) {
    cJSON* zone_json = cJSON_CreateObject();
    addZoneSnapshot(zone_json, input.pots[pot_index], pot_index);
    cJSON_AddItemToArray(pots, zone_json);
  }

  cJSON* pseudo = cJSON_AddObjectToObject(document, control::schema::kWireRootPseudo);
  cJSON_AddBoolToObject(pseudo, control::schema::wireKey(FeatureIndex::LightsActive),
                        input.lights_active);

  cJSON* environment = cJSON_AddObjectToObject(document, control::schema::kWireRootEnvironment);
  cJSON_AddNumberToObject(environment, control::schema::wireKey(FeatureIndex::GrowboxVolumeM3),
                          input.environment.growbox_volume_m3);
  cJSON_AddNumberToObject(environment, control::schema::wireKey(FeatureIndex::ThermalMassJPerK),
                          input.environment.thermal_mass_j_per_k);
  cJSON_AddNumberToObject(environment, control::schema::wireKey(FeatureIndex::HeatLossWPerK),
                          input.environment.heat_loss_w_per_k);
  cJSON_AddNumberToObject(environment, control::schema::wireKey(FeatureIndex::AirLeakRateAch),
                          input.environment.air_leak_rate_ach);

  cJSON* actuators = cJSON_AddObjectToObject(document, control::schema::kWireRootActuators);
  cJSON* heater = cJSON_AddObjectToObject(actuators, control::schema::kWireObjectHeater);
  cJSON_AddBoolToObject(heater, control::schema::wireKey(FeatureIndex::HeaterAvailable),
                        input.actuators.heater.available);
  cJSON_AddNumberToObject(heater, control::schema::wireKey(FeatureIndex::HeaterMaxPowerW),
                          input.actuators.heater.max_power_w);
  cJSON_AddNumberToObject(heater, control::schema::wireKey(FeatureIndex::HeaterEfficiency),
                          input.actuators.heater.efficiency);

  cJSON* fan = cJSON_AddObjectToObject(actuators, control::schema::kWireObjectFan);
  cJSON_AddBoolToObject(fan, control::schema::wireKey(FeatureIndex::FanAvailable),
                        input.actuators.fan.available);
  cJSON_AddNumberToObject(fan, control::schema::wireKey(FeatureIndex::FanMaxAirflowM3H),
                          input.actuators.fan.max_airflow_m3_h);
  cJSON_AddNumberToObject(fan, control::schema::wireKey(FeatureIndex::FanMinimumCommand),
                          input.actuators.fan.minimum_command);

  cJSON* humidifier = cJSON_AddObjectToObject(actuators, control::schema::kWireObjectHumidifier);
  cJSON_AddBoolToObject(humidifier, control::schema::wireKey(FeatureIndex::HumidifierAvailable),
                        input.actuators.humidifier.available);
  cJSON_AddNumberToObject(humidifier, control::schema::wireKey(FeatureIndex::HumidifierMaxOutputGH),
                          input.actuators.humidifier.max_output_g_h);

  cJSON* dehumidifier =
      cJSON_AddObjectToObject(actuators, control::schema::kWireObjectDehumidifier);
  cJSON_AddBoolToObject(dehumidifier, control::schema::wireKey(FeatureIndex::DehumidifierAvailable),
                        input.actuators.dehumidifier.available);
  cJSON_AddNumberToObject(dehumidifier,
                          control::schema::wireKey(FeatureIndex::DehumidifierMaxRemovalGH),
                          input.actuators.dehumidifier.max_removal_g_h);

  cJSON* cooler = cJSON_AddObjectToObject(actuators, control::schema::kWireObjectCooler);
  cJSON_AddBoolToObject(cooler, control::schema::wireKey(FeatureIndex::CoolerAvailable),
                        input.actuators.cooler.available);
  cJSON_AddNumberToObject(cooler, control::schema::wireKey(FeatureIndex::CoolerMaxCoolingW),
                          input.actuators.cooler.max_cooling_w);

  cJSON* co2_doser = cJSON_AddObjectToObject(actuators, control::schema::kWireObjectCo2Doser);
  cJSON_AddBoolToObject(co2_doser, control::schema::wireKey(FeatureIndex::Co2DoserAvailable),
                        input.actuators.co2_doser.available);
  cJSON_AddNumberToObject(co2_doser,
                          control::schema::wireKey(FeatureIndex::Co2DoserDosePpmPerFullPulse),
                          input.actuators.co2_doser.dose_ppm_per_full_pulse);
  cJSON_AddNumberToObject(co2_doser, control::schema::wireKey(FeatureIndex::Co2DoserMaximumPulseS),
                          input.actuators.co2_doser.maximum_pulse_s);

  cJSON* nutrient_heater =
      cJSON_AddObjectToObject(actuators, control::schema::kWireObjectNutrientHeater);
  cJSON_AddBoolToObject(nutrient_heater,
                        control::schema::wireKey(FeatureIndex::NutrientHeaterAvailable),
                        input.actuators.nutrient_heater.available);
  cJSON_AddNumberToObject(nutrient_heater,
                          control::schema::wireKey(FeatureIndex::NutrientHeaterMaxPowerW),
                          input.actuators.nutrient_heater.max_power_w);
  cJSON_AddNumberToObject(nutrient_heater,
                          control::schema::wireKey(FeatureIndex::NutrientHeaterEfficiency),
                          input.actuators.nutrient_heater.efficiency);

  cJSON* targets = cJSON_AddObjectToObject(document, control::schema::kWireRootTargets);
  cJSON_AddNumberToObject(targets, control::schema::wireKey(FeatureIndex::TargetAirTemperatureC),
                          input.targets.air_temperature_c);
  cJSON_AddNumberToObject(targets, control::schema::wireKey(FeatureIndex::TargetAirHumidityPct),
                          input.targets.air_humidity_pct);
  cJSON_AddNumberToObject(targets, control::schema::wireKey(FeatureIndex::TargetCo2Ppm),
                          input.targets.co2_ppm);
  cJSON_AddNumberToObject(
      targets, control::schema::wireKey(FeatureIndex::TargetNutrientSolutionTemperatureC),
      input.targets.nutrient_solution_temperature_c);

  cJSON* previous = cJSON_AddObjectToObject(document, control::schema::kWireRootPrevious);
  cJSON_AddNumberToObject(previous, control::schema::wireKey(FeatureIndex::PreviousHeater),
                          input.previous.heater);
  cJSON_AddNumberToObject(previous, control::schema::wireKey(FeatureIndex::PreviousFan),
                          input.previous.fan);
  cJSON_AddNumberToObject(previous, control::schema::wireKey(FeatureIndex::PreviousHumidifier),
                          input.previous.humidifier);
  cJSON_AddNumberToObject(previous, control::schema::wireKey(FeatureIndex::PreviousDehumidifier),
                          input.previous.dehumidifier);
  cJSON_AddNumberToObject(previous, control::schema::wireKey(FeatureIndex::PreviousCooler),
                          input.previous.cooler);
  cJSON_AddNumberToObject(previous, control::schema::wireKey(FeatureIndex::PreviousCo2Doser),
                          input.previous.co2_doser);
  cJSON_AddNumberToObject(previous, control::schema::wireKey(FeatureIndex::PreviousNutrientHeater),
                          input.previous.nutrient_heater);

  cJSON* safety = cJSON_AddObjectToObject(document, "safety");
  cJSON_AddNumberToObject(safety, "maximum_air_temperature_c",
                          input.safety.maximum_air_temperature_c);
  cJSON_AddNumberToObject(safety, "alarm_air_temperature_c", input.safety.alarm_air_temperature_c);
  cJSON_AddNumberToObject(safety, "alarm_minimum_fan", input.safety.alarm_minimum_fan);
  cJSON_AddNumberToObject(safety, "binary_threshold", input.safety.binary_threshold);
  cJSON_AddNumberToObject(safety, "heater_minimum_on_s", input.safety.heater_minimum_on_s);
  cJSON_AddNumberToObject(safety, "heater_minimum_off_s", input.safety.heater_minimum_off_s);
  cJSON_AddNumberToObject(safety, "humidifier_minimum_on_s", input.safety.humidifier_minimum_on_s);
  cJSON_AddNumberToObject(safety, "humidifier_minimum_off_s",
                          input.safety.humidifier_minimum_off_s);
  cJSON_AddNumberToObject(safety, "dehumidifier_minimum_on_s",
                          input.safety.dehumidifier_minimum_on_s);
  cJSON_AddNumberToObject(safety, "dehumidifier_minimum_off_s",
                          input.safety.dehumidifier_minimum_off_s);
  cJSON_AddNumberToObject(safety, "cooler_minimum_on_s", input.safety.cooler_minimum_on_s);
  cJSON_AddNumberToObject(safety, "cooler_minimum_off_s", input.safety.cooler_minimum_off_s);
  cJSON_AddNumberToObject(safety, "co2_doser_minimum_interval_s",
                          input.safety.co2_doser_minimum_interval_s);
  cJSON_AddNumberToObject(safety, "fan_venting_co2_threshold",
                          input.safety.fan_venting_co2_threshold);
  cJSON_AddNumberToObject(safety, "maximum_nutrient_soil_delta_c",
                          input.safety.maximum_nutrient_soil_delta_c);
  cJSON_AddNumberToObject(safety, "minimum_nutrient_solution_temperature_c",
                          input.safety.minimum_nutrient_solution_temperature_c);
}

void addDecisionContext(cJSON* document, const control::ControllerInput& input) noexcept {
  if (document == nullptr) {
    return;
  }

  cJSON* sensors = cJSON_AddObjectToObject(document, "sensors");
  cJSON_AddNumberToObject(sensors, "air_temperature_c", input.sensors.air_temperature_c);
  cJSON_AddNumberToObject(sensors, "air_humidity_pct", input.sensors.air_humidity_pct);
  cJSON_AddNumberToObject(sensors, "co2_ppm", input.sensors.co2_ppm);
  cJSON_AddNumberToObject(sensors, "nutrient_solution_temperature_c",
                          input.sensors.nutrient_solution_temperature_c);
  cJSON_AddNumberToObject(sensors, "outside_temperature_c", input.sensors.outside_temperature_c);
  cJSON_AddNumberToObject(sensors, "outside_humidity_pct", input.sensors.outside_humidity_pct);
  cJSON_AddNumberToObject(sensors, "outside_co2_ppm", input.sensors.outside_co2_ppm);

  cJSON* validity = cJSON_AddObjectToObject(document, "validity");
  cJSON_AddBoolToObject(validity, "air_temperature_c", input.validity.air_temperature);
  cJSON_AddBoolToObject(validity, "air_humidity_pct", input.validity.air_humidity);
  cJSON_AddBoolToObject(validity, "co2_ppm", input.validity.co2);
  cJSON_AddBoolToObject(validity, "nutrient_solution_temperature_c",
                        input.validity.nutrient_solution_temperature);
  cJSON_AddBoolToObject(validity, "outside_temperature_c", input.validity.outside_temperature);
  cJSON_AddBoolToObject(validity, "outside_humidity_pct", input.validity.outside_humidity);
  cJSON_AddBoolToObject(validity, "outside_co2_ppm", input.validity.outside_co2);

  cJSON* pots = cJSON_AddArrayToObject(document, "pots");
  for (std::size_t pot_index = 0U; pot_index < control::kMaxPots; ++pot_index) {
    const auto& pot = input.pots[pot_index];
    cJSON* zone_json = cJSON_CreateObject();
    cJSON_AddBoolToObject(zone_json, "available", pot.available);
    cJSON* pot_sensors = cJSON_AddObjectToObject(zone_json, "sensors");
    cJSON_AddNumberToObject(pot_sensors, "soil_moisture_pct", pot.sensors.soil_moisture_pct);
    cJSON_AddNumberToObject(pot_sensors, "soil_temperature_c", pot.sensors.soil_temperature_c);
    cJSON* pot_validity = cJSON_AddObjectToObject(zone_json, "validity");
    cJSON_AddBoolToObject(pot_validity, "soil_moisture_pct", pot.validity.soil_moisture);
    cJSON_AddBoolToObject(pot_validity, "soil_temperature_c", pot.validity.soil_temperature);
    cJSON* zone_targets = cJSON_AddObjectToObject(zone_json, "targets");
    cJSON_AddNumberToObject(zone_targets, "soil_moisture_pct", pot.target_soil_moisture_pct);
    cJSON_AddNumberToObject(zone_targets, "soil_temperature_c", pot.target_soil_temperature_c);
    cJSON_AddItemToArray(pots, zone_json);
  }

  cJSON* pseudo = cJSON_AddObjectToObject(document, "pseudo");
  cJSON_AddBoolToObject(pseudo, "lights_active", input.lights_active);

  cJSON* targets = cJSON_AddObjectToObject(document, "targets");
  cJSON_AddNumberToObject(targets, "air_temperature_c", input.targets.air_temperature_c);
  cJSON_AddNumberToObject(targets, "air_humidity_pct", input.targets.air_humidity_pct);
  cJSON_AddNumberToObject(targets, "co2_ppm", input.targets.co2_ppm);
  cJSON_AddNumberToObject(targets, "nutrient_solution_temperature_c",
                          input.targets.nutrient_solution_temperature_c);

  addActuatorAvailability(document, input.actuators);
}

bool parseLoadScenario(const cJSON* root, control::ControllerInput& scenario,
                       std::uint32_t& seed) noexcept {
  const cJSON* sensors = objectItem(root, control::schema::kWireRootSensors);
  const cJSON* validity = objectItem(root, control::schema::kWireRootValidity);
  const cJSON* pots = arrayItem(root, control::schema::kWireRootPots);
  const cJSON* pseudo = objectItem(root, control::schema::kWireRootPseudo);
  const cJSON* environment = objectItem(root, control::schema::kWireRootEnvironment);
  const cJSON* actuators = objectItem(root, control::schema::kWireRootActuators);
  const cJSON* targets = objectItem(root, control::schema::kWireRootTargets);
  const cJSON* previous = objectItem(root, control::schema::kWireRootPrevious);
  const cJSON* safety = item(root, "safety");
  return readUnsigned(root, "seed", seed) && parseSensors(sensors, scenario.sensors) &&
         parseValidity(validity, scenario.validity) && parseZones(pots, scenario.pots) &&
         parsePseudo(pseudo, scenario.lights_active) &&
         parseEnvironment(environment, scenario.environment) &&
         parseActuators(actuators, scenario.actuators) &&
         parseTargets(targets, scenario.targets, true) &&
         parsePrevious(previous, scenario.previous) && parseSafety(safety, scenario.safety);
}

bool parseStepOverrides(const cJSON* root, control::SensorState& sensors,
                        control::SensorValidity& validity,
                        control::GlobalActuatorCapabilities& actuators, bool& has_sensors,
                        bool& has_validity, bool& has_actuators) noexcept {
  const cJSON* sensors_json = item(root, control::schema::kWireRootSensors);
  const cJSON* validity_json = item(root, control::schema::kWireRootValidity);
  const cJSON* actuators_json = objectItem(root, control::schema::kWireRootActuators);
  has_sensors = sensors_json != nullptr && !cJSON_IsNull(sensors_json);
  has_validity = validity_json != nullptr && !cJSON_IsNull(validity_json);
  has_actuators = actuators_json != nullptr && !cJSON_IsNull(actuators_json);
  if (has_sensors && !parseSensors(sensors_json, sensors)) {
    return false;
  }
  if (has_validity && !parseValidity(validity_json, validity)) {
    return false;
  }
  if (has_actuators && !parseActuators(actuators_json, actuators)) {
    return false;
  }
  return true;
}

bool parseTargetPatch(const cJSON* root, control::ControlTargets& targets) noexcept {
  return parseTargets(root, targets, false);
}

bool parseSeedValue(const cJSON* root, std::uint32_t& seed) noexcept {
  return readUnsigned(root, "value", seed);
}

cJSON* buildScenarioDocument(const control::ControllerInput& input, std::uint32_t seed) noexcept {
  cJSON* document = cJSON_CreateObject();
  if (document == nullptr) {
    return nullptr;
  }
  cJSON_AddStringToObject(document, "type", "scenario");
  cJSON_AddNumberToObject(document, "schema_version", control::schema::kSchemaVersion);
  cJSON_AddStringToObject(document, "schema_hash", control::schema::kSchemaHash);
  cJSON_AddNumberToObject(document, "seed", seed);
  cJSON* scenario = cJSON_AddObjectToObject(document, "scenario");
  addScenarioSnapshot(scenario, input);
  return document;
}

} // namespace wire
} // namespace demo
} // namespace growbox
