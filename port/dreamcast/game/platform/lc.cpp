// The Gekko locked cache (16 KB at 0xE0000000) as an ordinary buffer. The game's
// skinning keeps its matrix palette there (trans.cpp PSMTXReorder / CalcSk1_x) and
// main() enables it with LCEnable; on the Dreamcast it is plain RAM and the DMA
// queue calls are no-ops.
extern "C" {
unsigned char re4dc_locked_cache[0x4000] __attribute__((aligned(32)));

void LCEnable(void) {}
void LCDisable(void) {}
}
