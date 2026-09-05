#include "climate/ClimateObservabilityMetrics.h"

#include <cassert>
#include <cmath>

using growbox::app::climate_io::calculateAirMoistureMetrics;
using growbox::app::climate_io::calculateVentilationGradients;

namespace {

bool near(float left, float right, float tolerance) {
  return std::fabs(left - right) <= tolerance;
}

void testKnownMoisturePoint() {
  const auto metrics = calculateAirMoistureMetrics(25.0F, 60.0F);
  assert(metrics.valid);
  assert(near(metrics.dew_point_c, 16.7F, 0.3F));
  assert(near(metrics.absolute_humidity_g_m3, 13.8F, 0.4F));
  assert(near(metrics.air_vpd_kpa, 1.27F, 0.05F));
}

void testVentilationGradientUsesMoistureContent() {
  const auto gradient = calculateVentilationGradients(25.0F, 60.0F, 20.0F, 50.0F);
  assert(gradient.valid);
  assert(near(gradient.temperature_delta_c, 5.0F, 0.01F));
  assert(gradient.absolute_humidity_delta_g_m3 > 4.5F);
}

void testRhAloneCanBeMisleading() {
  const auto gradient = calculateVentilationGradients(28.0F, 55.0F, 18.0F, 70.0F);
  assert(gradient.valid);
  assert(gradient.absolute_humidity_delta_g_m3 > 0.0F);
}

void testInvalidInputsFailClosed() {
  assert(!calculateAirMoistureMetrics(25.0F, 0.0F).valid);
  assert(!calculateAirMoistureMetrics(25.0F, 101.0F).valid);
  assert(!calculateAirMoistureMetrics(NAN, 60.0F).valid);
  assert(!calculateVentilationGradients(25.0F, 60.0F, 20.0F, 0.0F).valid);
}

} // namespace

int main() {
  testKnownMoisturePoint();
  testVentilationGradientUsesMoistureContent();
  testRhAloneCanBeMisleading();
  testInvalidInputsFailClosed();
  return 0;
}
