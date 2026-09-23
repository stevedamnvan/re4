// D367 IO probe (IO_PROBE=1), diagnostic only: where the room-entry wall time blocks.
//
// Link-time wraps (Makefile: -Wl,--wrap=fs_open,fs_read,thd_sleep,genwait_wait) time every
// blocking call, from every thread, and add it to small tables:
//   fs_read by file path (fs_open records the path of each handle), with calls, us, bytes and
//     the reads into a destination that is not 32-byte aligned (KOS then takes the per-sector
//     PIO path instead of one DMA stream);
//   fs_read / fs_open / thd_sleep by caller (return address; symbolize with symbols-demangled.txt);
//   genwait_wait (the base of every KOS sem/cond/mutex/sleep block) by wait kind and thread label;
//   per-thread totals of fs_read and genwait time.
// ui_bridge.cpp resets the tables at the door request and prints them ("iowrap:" lines) with
// the "iotime: door" line. Nothing here changes what is read or when.
#include <kos.h>
#include <string.h>

#include "re4dc_platform.h"

extern "C" {
ssize_t __real_fs_read(file_t hnd, void* buffer, size_t cnt);
file_t __real_fs_open(const char* fn, int mode);
void __real_thd_sleep(unsigned ms);
int __real_genwait_wait(void* obj, const char* mesg, unsigned int timeout);
}

namespace {
unsigned long long us_now() { return timer_us_gettime64(); }

struct Site { unsigned kind; void* ra; unsigned n, bytes, mis; unsigned long long us; };
struct PathRow { char path[28]; unsigned n, bytes, mis, opens; unsigned long long us, open_us; };
struct WaitRow { const char* mesg; char thread[16]; unsigned n; unsigned long long us; };
struct ThreadRow { char thread[16]; unsigned reads; unsigned long long read_us, wait_us; };
struct Handle { file_t fd; short row1; };   // row1: path row + 1 (0 = empty)

constexpr unsigned kSites = 48, kPaths = 96, kWaits = 24, kThreads = 12, kHandles = 32;
Site sites[kSites]; unsigned nsites;
PathRow paths[kPaths]; unsigned npaths;
WaitRow waits[kWaits]; unsigned nwaits;
ThreadRow threads[kThreads]; unsigned nthreads;
Handle handles[kHandles];
unsigned dropped;
bool enabled;
const char* const kKind[] = {"fs_read", "fs_open", "thd_sleep"};

void label_of(char out[16])
{
    kthread_t* t = thd_get_current();
    const char* l = t ? t->label : "?";
    if (!l || !*l) l = "?";
    strncpy(out, l, 15); out[15] = 0;
}

Site* site(unsigned kind, void* ra)
{
    for (unsigned i = 0; i < nsites; ++i)
        if (sites[i].ra == ra && sites[i].kind == kind) return &sites[i];
    if (nsites == kSites) { ++dropped; return nullptr; }
    Site* s = &sites[nsites++]; memset(s, 0, sizeof(*s)); s->kind = kind; s->ra = ra; return s;
}

int path_row(const char* fn)
{
    const size_t len = strlen(fn);
    const char* tail = len > 27 ? fn + len - 27 : fn;   // keep the file name end
    for (unsigned i = 0; i < npaths; ++i) if (!strcmp(paths[i].path, tail)) return (int) i;
    if (npaths == kPaths) { ++dropped; return -1; }
    PathRow* p = &paths[npaths]; memset(p, 0, sizeof(*p)); strcpy(p->path, tail);
    return (int) npaths++;
}

ThreadRow* thread_row(const char* label)
{
    for (unsigned i = 0; i < nthreads; ++i) if (!strcmp(threads[i].thread, label)) return &threads[i];
    if (nthreads == kThreads) { ++dropped; return nullptr; }
    ThreadRow* t = &threads[nthreads++]; memset(t, 0, sizeof(*t)); strcpy(t->thread, label); return t;
}

int handle_row(file_t fd)
{
    for (auto& h : handles) if (h.row1 && h.fd == fd) return h.row1 - 1;
    return -1;
}
}

extern "C" file_t __wrap_fs_open(const char* fn, int mode)
{
    void* ra = __builtin_return_address(0);
    const unsigned long long t0 = us_now();
    const file_t fd = __real_fs_open(fn, mode);
    const unsigned us = (unsigned) (us_now() - t0);
    const int irq = irq_disable();
    if (enabled) {
        if (Site* s = site(1, ra)) { ++s->n; s->us += us; }
    }
    // The handle map is kept even while the tables are off, so reads of files opened before
    // the door still get their path.
    if (fn && fd >= 0) {
        const int row = path_row(fn);
        if (row >= 0) {
            if (enabled) { ++paths[row].opens; paths[row].open_us += us; }
            Handle* slot = nullptr;
            for (auto& h : handles) if (h.row1 && h.fd == fd) { slot = &h; break; }
            if (!slot) for (auto& h : handles) if (!h.row1) { slot = &h; break; }
            if (!slot) slot = &handles[(unsigned) fd % kHandles];
            slot->fd = fd; slot->row1 = (short) (row + 1);
        }
    }
    irq_restore(irq);
    return fd;
}

extern "C" ssize_t __wrap_fs_read(file_t hnd, void* buffer, size_t cnt)
{
    void* ra = __builtin_return_address(0);
    const unsigned long long t0 = us_now();
    const ssize_t r = __real_fs_read(hnd, buffer, cnt);
    if (!enabled) return r;
    const unsigned us = (unsigned) (us_now() - t0);
    const unsigned bytes = r > 0 ? (unsigned) r : 0u;
    const bool mis = ((unsigned) (uintptr_t) buffer & 31u) != 0;
    char label[16]; label_of(label);
    const int irq = irq_disable();
    if (Site* s = site(0, ra)) { ++s->n; s->us += us; s->bytes += bytes; s->mis += mis; }
    const int row = handle_row(hnd);
    if (row >= 0) { PathRow& p = paths[row]; ++p.n; p.us += us; p.bytes += bytes; p.mis += mis; }
    if (ThreadRow* t = thread_row(label)) { ++t->reads; t->read_us += us; }
    irq_restore(irq);
    return r;
}

extern "C" void __wrap_thd_sleep(unsigned ms)
{
    void* ra = __builtin_return_address(0);
    const unsigned long long t0 = us_now();
    __real_thd_sleep(ms);
    if (!enabled) return;
    const unsigned us = (unsigned) (us_now() - t0);
    const int irq = irq_disable();
    if (Site* s = site(2, ra)) { ++s->n; s->us += us; }
    irq_restore(irq);
}

extern "C" int __wrap_genwait_wait(void* obj, const char* mesg, unsigned int timeout)
{
    const unsigned long long t0 = us_now();
    const int r = __real_genwait_wait(obj, mesg, timeout);
    if (!enabled) return r;
    const unsigned us = (unsigned) (us_now() - t0);
    char label[16]; label_of(label);
    const int irq = irq_disable();
    WaitRow* w = nullptr;
    for (unsigned i = 0; i < nwaits; ++i)
        if (waits[i].mesg == mesg && !strcmp(waits[i].thread, label)) { w = &waits[i]; break; }
    if (!w && nwaits < kWaits) { w = &waits[nwaits++]; memset(w, 0, sizeof(*w)); w->mesg = mesg; strcpy(w->thread, label); }
    if (w) { ++w->n; w->us += us; } else ++dropped;
    if (ThreadRow* t = thread_row(label)) t->wait_us += us;
    irq_restore(irq);
    return r;
}

// Reset the tables and start collecting (door request).
extern "C" void re4dc_iowrap_reset(void)
{
    const int irq = irq_disable();
    nsites = nwaits = nthreads = 0; dropped = 0;
    for (unsigned i = 0; i < npaths; ++i) {
        PathRow& p = paths[i]; p.n = p.bytes = p.mis = p.opens = 0; p.us = p.open_us = 0;
    }
    enabled = true;
    irq_restore(irq);
}

// Print the tables, largest time first ("iowrap:" lines), then reset.
extern "C" void re4dc_iowrap_report(const char* what, unsigned cycle)
{
    // Sorted and printed in place: collection pauses until the reset at the end (the tables
    // cost bss, which comes out of the KOS malloc break).
    enabled = false;
    Site* s = sites; PathRow* p = paths; WaitRow* w = waits; ThreadRow* t = threads;
    const unsigned ns = nsites, np = npaths, nw = nwaits, nt = nthreads, dr = dropped;
    // selection order by time (small n)
    auto top = [](auto* a, unsigned n, auto key) {
        for (unsigned i = 0; i < n; ++i)
            for (unsigned j = i + 1; j < n; ++j)
                if (key(a[j]) > key(a[i])) { auto x = a[i]; a[i] = a[j]; a[j] = x; }
    };
    top(t, nt, [](const ThreadRow& r) { return r.read_us + r.wait_us; });
    for (unsigned i = 0; i < nt; ++i)
        re4dc_log("iowrap: %s cycle=%u thread=%s reads=%u read_us=%llu wait_us=%llu\n", what, cycle,
                  t[i].thread, t[i].reads, t[i].read_us, t[i].wait_us);
    top(w, nw, [](const WaitRow& r) { return r.us; });
    for (unsigned i = 0; i < nw && i < 24; ++i)
        re4dc_log("iowrap: %s cycle=%u wait=%s thread=%s n=%u us=%llu\n", what, cycle,
                  w[i].mesg ? w[i].mesg : "?", w[i].thread, w[i].n, w[i].us);
    top(s, ns, [](const Site& r) { return r.us; });
    for (unsigned i = 0; i < ns && i < 32; ++i)
        re4dc_log("iowrap: %s cycle=%u site=%s ra=0x%08x n=%u us=%llu bytes=%u mis=%u\n", what, cycle,
                  kKind[s[i].kind], (unsigned) (uintptr_t) s[i].ra, s[i].n, s[i].us, s[i].bytes, s[i].mis);
    top(p, np, [](const PathRow& r) { return r.us + r.open_us; });
    for (unsigned i = 0; i < np && i < 40; ++i) {
        if (!p[i].n && !p[i].opens) break;
        re4dc_log("iowrap: %s cycle=%u path=%s opens=%u open_us=%llu reads=%u us=%llu bytes=%u mis=%u\n", what, cycle,
                  p[i].path, p[i].opens, p[i].open_us, p[i].n, p[i].us, p[i].bytes, p[i].mis);
    }
    re4dc_log("iowrap: %s cycle=%u dropped=%u\n", what, cycle, dr);
    // Sorting moved the path rows: forget the handle map (files opened before this point lose
    // their path; the room loads open their files again).
    memset(handles, 0, sizeof(handles));
    re4dc_iowrap_reset();
}
