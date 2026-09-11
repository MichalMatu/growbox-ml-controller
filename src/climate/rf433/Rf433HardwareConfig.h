#pragma once

#include "climate/rf433/Rf433ProtocolCodec.h"

namespace growbox::app::climate_io::rf433 {

struct RemoteSocketHardwareConfig {
  const char* label;
  FrameConfig on;
  FrameConfig off;
};

// Stage28C freeze for exactly one learned original remote/socket pair.
// The label is intentionally neutral: semantic actuator roles belong above the
// hardware/config layer and are not assigned here.
inline constexpr char kRemoteSocket1Label[] = "remote_socket_1";

// repeat=10 is the physically validated transmit repeat count for reliable
// control with this hardware. It is not claimed to be a measured exact repeat
// count emitted by the original handheld remote.
inline constexpr FrameConfig kRemoteSocket1On{{906118656U, 32U, 2U}, 10U, 575U};
inline constexpr FrameConfig kRemoteSocket1Off{{1040336384U, 32U, 2U}, 10U, 575U};

inline constexpr RemoteSocketHardwareConfig kRemoteSocket1{
    kRemoteSocket1Label,
    kRemoteSocket1On,
    kRemoteSocket1Off,
};

// Stage28D service-console captured profiles. These identities are neutral hardware
// records and do not assign semantic actuator roles. Their 560 us transmit profile
// still requires physical ESP-to-socket validation.
inline constexpr char kRemoteSocket2Label[] = "remote_socket_2";
inline constexpr FrameConfig kRemoteSocket2On{{235030016U, 32U, 2U}, 10U, 560U};
inline constexpr FrameConfig kRemoteSocket2Off{{16926208U, 32U, 2U}, 10U, 560U};
inline constexpr RemoteSocketHardwareConfig kRemoteSocket2{
    kRemoteSocket2Label,
    kRemoteSocket2On,
    kRemoteSocket2Off,
};

inline constexpr char kRemoteSocket3Label[] = "remote_socket_3";
inline constexpr FrameConfig kRemoteSocket3On{{637683200U, 32U, 2U}, 10U, 560U};
inline constexpr FrameConfig kRemoteSocket3Off{{771900928U, 32U, 2U}, 10U, 560U};
inline constexpr RemoteSocketHardwareConfig kRemoteSocket3{
    kRemoteSocket3Label,
    kRemoteSocket3On,
    kRemoteSocket3Off,
};

} // namespace growbox::app::climate_io::rf433
