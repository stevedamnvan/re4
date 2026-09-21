// Fault capture for the boot-forward work: KOS debug output (dbglog, panics,
// the unhandled-exception dump) is routed into the RAM log ring, and an
// unhandled SH-4 exception logs the faulting context and parks the CPU so the
// evidence tooling can still read the ring out of the emulator.
#include <kos.h>
#include <kos/dbgio.h>
#include <arch/irq.h>
#include <stdio.h>

#include "re4dc_platform.h"

extern "C" void re4dc_log_raw(const char* data, unsigned long len);
extern "C" int re4dc_log_console;

static int ringDetected(void) { return 1; }
static int ringInit(void) { return 0; }
static int ringShutdown(void) { return 0; }
static int ringSetIrqUsage(int mode) { (void) mode; return 0; }
static int ringFlush(void) { return 0; }
static int ringWriteBuffer(const uint8_t* data, int len, int xlat)
{
    (void) xlat;
    re4dc_log_raw((const char*) data, (unsigned long) len);
    return len;
}
static int ringReadBuffer(uint8_t* data, int len)
{
    (void) data;
    (void) len;
    return -1;
}

static dbgio_handler_t g_ringHandler = {
    "re4ring", ringDetected, ringInit, ringShutdown, ringSetIrqUsage, ringFlush, ringWriteBuffer, ringReadBuffer, {NULL}};

static void onFault(irq_t code, irq_context_t* ctx, void* data)
{
    (void) data;
    re4dc_log("FAULT code=%03x pc=%08lx pr=%08lx sp=%08lx sr=%08lx\n", (unsigned) code, (unsigned long) ctx->pc,
              (unsigned long) ctx->pr, (unsigned long) ctx->r[15], (unsigned long) ctx->sr);
    for (int i = 0; i < 16; i += 4) {
        re4dc_log("  r%-2d %08lx  r%-2d %08lx  r%-2d %08lx  r%-2d %08lx\n", i, (unsigned long) ctx->r[i], i + 1,
                  (unsigned long) ctx->r[i + 1], i + 2, (unsigned long) ctx->r[i + 2], i + 3,
                  (unsigned long) ctx->r[i + 3]);
    }
    re4dc_set_stage(0xDEAD0000ul | (unsigned long) code);
    irq_disable();
    for (;;) {
    }
}

extern "C" void re4dc_fault_init(void)
{
    dbgio_add_handler(&g_ringHandler);
    if (dbgio_dev_select("re4ring") == 0) {
        re4dc_log_console = 0;  // stdout now lands in the ring itself
    }
    irq_set_handler(EXC_UNHANDLED_EXC, onFault, NULL);
    re4dc_log("re4dc_fault_init: dbgio -> ring, unhandled-exception handler set\n");
}
