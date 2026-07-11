#pragma once

#include <cmath>
#include <cstring>
#include <exception>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

namespace mini_unity {

class AssertionFailure final : public std::runtime_error {
 public:
  explicit AssertionFailure(const std::string& message) : std::runtime_error(message) {}
};

inline int test_count = 0;
inline int failure_count = 0;

[[noreturn]] inline void fail(const char* file, int line, const std::string& detail) {
  std::ostringstream message;
  message << file << ':' << line << ": " << detail;
  throw AssertionFailure(message.str());
}

inline int begin() {
  test_count = 0;
  failure_count = 0;
  std::cout << "environment_control host tests\n";
  return 0;
}

inline int end() {
  std::cout << "\n" << test_count << " tests, " << failure_count << " failures\n";
  return failure_count;
}

template <typename Function, typename Setup, typename Teardown>
void run(const char* name, Function function, Setup setup, Teardown teardown) {
  ++test_count;
  try {
    setup();
    function();
    teardown();
    std::cout << "[PASS] " << name << '\n';
  } catch (const std::exception& error) {
    try {
      teardown();
    } catch (...) {
    }
    ++failure_count;
    std::cout << "[FAIL] " << name << " - " << error.what() << '\n';
  } catch (...) {
    try {
      teardown();
    } catch (...) {
    }
    ++failure_count;
    std::cout << "[FAIL] " << name << " - unknown exception\n";
  }
}

template <typename Expected, typename Actual>
void assertEqual(const Expected& expected, const Actual& actual, const char* file, int line) {
  if (!(actual == expected)) {
    std::ostringstream detail;
    detail << "expected " << expected << ", got " << actual;
    fail(file, line, detail.str());
  }
}

template <typename Expected, typename Actual>
void assertNotEqual(const Expected& expected, const Actual& actual, const char* file, int line) {
  if (actual == expected) {
    std::ostringstream detail;
    detail << "did not expect " << expected;
    fail(file, line, detail.str());
  }
}

inline void assertStringEqual(const char* expected, const char* actual, const char* file, int line) {
  const bool equal = expected == actual ||
                     (expected != nullptr && actual != nullptr && std::strcmp(expected, actual) == 0);
  if (!equal) {
    std::ostringstream detail;
    detail << "expected string '" << (expected != nullptr ? expected : "<null>") << "', got '"
           << (actual != nullptr ? actual : "<null>") << "'";
    fail(file, line, detail.str());
  }
}

inline void assertFloatWithin(double tolerance, double expected, double actual, const char* file,
                              int line) {
  if (!std::isfinite(expected) || !std::isfinite(actual) || tolerance < 0.0 ||
      std::fabs(actual - expected) > tolerance) {
    std::ostringstream detail;
    detail << "expected " << expected << " +/- " << tolerance << ", got " << actual;
    fail(file, line, detail.str());
  }
}

}  // namespace mini_unity

#define UNITY_BEGIN() ::mini_unity::begin()
#define UNITY_END() ::mini_unity::end()
#define RUN_TEST(function) ::mini_unity::run(#function, function, setUp, tearDown)

#define TEST_ASSERT_TRUE(condition)                                                            \
  do {                                                                                         \
    if (!(condition)) {                                                                        \
      ::mini_unity::fail(__FILE__, __LINE__, "expected true: " #condition);                    \
    }                                                                                          \
  } while (false)

#define TEST_ASSERT_FALSE(condition)                                                           \
  do {                                                                                         \
    if (condition) {                                                                           \
      ::mini_unity::fail(__FILE__, __LINE__, "expected false: " #condition);                   \
    }                                                                                          \
  } while (false)

#define TEST_ASSERT_EQUAL_UINT8(expected, actual)                                              \
  ::mini_unity::assertEqual((expected), (actual), __FILE__, __LINE__)
#define TEST_ASSERT_EQUAL_UINT32(expected, actual)                                             \
  ::mini_unity::assertEqual((expected), (actual), __FILE__, __LINE__)
#define TEST_ASSERT_EQUAL_UINT64(expected, actual)                                             \
  ::mini_unity::assertEqual((expected), (actual), __FILE__, __LINE__)
#define TEST_ASSERT_NOT_EQUAL(expected, actual)                                                \
  ::mini_unity::assertNotEqual((expected), (actual), __FILE__, __LINE__)
#define TEST_ASSERT_EQUAL_STRING(expected, actual)                                             \
  ::mini_unity::assertStringEqual((expected), (actual), __FILE__, __LINE__)
#define TEST_ASSERT_FLOAT_WITHIN(tolerance, expected, actual)                                  \
  ::mini_unity::assertFloatWithin((tolerance), (expected), (actual), __FILE__, __LINE__)
