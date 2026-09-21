// Memory card interface: no card. Every call reports CARD_RESULT_NOCARD, which
// the game's card state machine (src/game/card.cpp) treats as "no memory
// card inserted"; the VMU mapping is a later slice.
typedef signed long s32;
typedef unsigned long u32;
typedef unsigned long long u64;

enum { CARD_RESULT_NOCARD = -3 };

extern "C" {

void CARDInit(void) {}
s32 CARDCheckAsync(s32 chan, void* cb) { (void) chan; (void) cb; return CARD_RESULT_NOCARD; }
s32 CARDClose(void* fi) { (void) fi; return CARD_RESULT_NOCARD; }
s32 CARDCreateAsync(s32 chan, const char* name, u32 size, void* fi, void* cb) { (void) chan; (void) name; (void) size; (void) fi; (void) cb; return CARD_RESULT_NOCARD; }
s32 CARDDeleteAsync(s32 chan, const char* name, void* cb) { (void) chan; (void) name; (void) cb; return CARD_RESULT_NOCARD; }
s32 CARDFormatAsync(s32 chan, void* cb) { (void) chan; (void) cb; return CARD_RESULT_NOCARD; }
s32 CARDFreeBlocks(s32 chan, s32* bytes, s32* files) { (void) chan; if (bytes) *bytes = 0; if (files) *files = 0; return CARD_RESULT_NOCARD; }
s32 CARDGetResultCode(s32 chan) { (void) chan; return CARD_RESULT_NOCARD; }
s32 CARDGetSerialNo(s32 chan, u64* serial) { (void) chan; if (serial) *serial = 0; return CARD_RESULT_NOCARD; }
s32 CARDGetStatus(s32 chan, s32 fileNo, void* stat) { (void) chan; (void) fileNo; (void) stat; return CARD_RESULT_NOCARD; }
s32 CARDMountAsync(s32 chan, void* work, void* detach, void* attach) { (void) chan; (void) work; (void) detach; (void) attach; return CARD_RESULT_NOCARD; }
s32 CARDOpen(s32 chan, const char* name, void* fi) { (void) chan; (void) name; (void) fi; return CARD_RESULT_NOCARD; }
s32 CARDProbeEx(s32 chan, s32* memSize, s32* sectorSize) { (void) chan; if (memSize) *memSize = 0; if (sectorSize) *sectorSize = 0; return CARD_RESULT_NOCARD; }
s32 CARDReadAsync(void* fi, void* buf, s32 len, s32 ofs, void* cb) { (void) fi; (void) buf; (void) len; (void) ofs; (void) cb; return CARD_RESULT_NOCARD; }
s32 CARDSetStatusAsync(s32 chan, s32 fileNo, void* stat, void* cb) { (void) chan; (void) fileNo; (void) stat; (void) cb; return CARD_RESULT_NOCARD; }
s32 CARDUnmount(s32 chan) { (void) chan; return CARD_RESULT_NOCARD; }
s32 CARDWriteAsync(void* fi, void* buf, s32 len, s32 ofs, void* cb) { (void) fi; (void) buf; (void) len; (void) ofs; (void) cb; return CARD_RESULT_NOCARD; }

}  // extern "C"
