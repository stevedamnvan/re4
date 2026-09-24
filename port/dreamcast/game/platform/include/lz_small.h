// D367 VMU saves: deterministic LZ4-block codec (platform/lz_small.cpp, tools/vmusave.py).
#ifndef RE4DC_LZ_SMALL_H
#define RE4DC_LZ_SMALL_H
#ifdef __cplusplus
extern "C" {
#endif

#define LZS_HASH_BITS 11  // table: (1 << 11) u16 = 4 KiB, caller memory
#define LZS_TABLE_BYTES (2u << LZS_HASH_BITS)

// Compresses `n` (<= 65535) bytes into `dst` (capacity `cap`). Returns the compressed length or
// -1 when it does not fit.
int lzs_encode(const void* src, unsigned n, void* dst, unsigned cap, unsigned short* table);
// Decompresses exactly `raw_len` bytes. Returns raw_len, or -1 on any malformed input.
int lzs_decode(const void* src, unsigned n, void* dst, unsigned raw_len);
// Checks that `src` decodes to exactly `expected` (no output buffer). raw_len or -1.
int lzs_verify(const void* src, unsigned n, const void* expected, unsigned raw_len);

#ifdef __cplusplus
}
#endif
#endif
