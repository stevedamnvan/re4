#pragma once

#include <bit>
#include <cstddef>
#include <cstdint>
#include <type_traits>

namespace re4dc {

using s8 = std::int8_t;
using s16 = std::int16_t;
using s32 = std::int32_t;
using s64 = std::int64_t;
using u8 = std::uint8_t;
using u16 = std::uint16_t;
using u32 = std::uint32_t;
using u64 = std::uint64_t;
using f32 = float;
using f64 = double;

static_assert(sizeof(s8) == 1);
static_assert(sizeof(s16) == 2);
static_assert(sizeof(s32) == 4);
static_assert(sizeof(s64) == 8);
static_assert(sizeof(u8) == 1);
static_assert(sizeof(u16) == 2);
static_assert(sizeof(u32) == 4);
static_assert(sizeof(u64) == 8);
static_assert(sizeof(f32) == 4);
static_assert(sizeof(f64) == 8);

constexpr bool kNativeLittleEndian = std::endian::native == std::endian::little;
constexpr bool kNativeBigEndian = std::endian::native == std::endian::big;

// Source-file formats are GameCube big-endian. Runtime packages for Dreamcast
// are little-endian and versioned. Parsers must decode rather than reinterpret.
constexpr u16 byte_swap(u16 value) {
    return static_cast<u16>((value << 8) | (value >> 8));
}

constexpr u32 byte_swap(u32 value) {
    return ((value & 0x000000ffu) << 24) |
           ((value & 0x0000ff00u) << 8) |
           ((value & 0x00ff0000u) >> 8) |
           ((value & 0xff000000u) >> 24);
}

template <typename T>
constexpr T from_big_endian(T value) {
    static_assert(std::is_same_v<T, u16> || std::is_same_v<T, u32>);
    if constexpr (kNativeLittleEndian) {
        return byte_swap(value);
    }
    return value;
}

} // namespace re4dc
