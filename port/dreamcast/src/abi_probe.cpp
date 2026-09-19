#include "re4dc/abi.hpp"

#include <climits>
#include <cstdio>

int main() {
    std::printf("{\n");
    std::printf("  \"pointer_bytes\": %zu,\n", sizeof(void*));
    std::printf("  \"long_bytes\": %zu,\n", sizeof(long));
    std::printf("  \"char_bits\": %d,\n", CHAR_BIT);
    std::printf("  \"native_endian\": \"%s\",\n",
                re4dc::kNativeLittleEndian ? "little" : "big");
#ifdef __sh__
    std::printf("  \"target\": \"sh\"\n");
#else
    std::printf("  \"target\": \"host\"\n");
#endif
    std::printf("}\n");

    return re4dc::from_big_endian<re4dc::u32>(0x12345678u) == 0x78563412u
                   ? 0
                   : 1;
}
