// D367 IO probe (IO_PROBE=1): timed disc reads for GDEMU / optical-drive calibration.
//
// Runs once at the end of OSInit, and only when /cd/dc/ioprobe.txt exists. Without the file
// nothing runs. The probe borrows the platform arena as scratch before any game heap exists,
// and zeroes it again afterwards. Optional "key=value" tokens in the fixture:
//   seq=8        MB per sequential pass (64 KiB and 128 KiB aligned reads: the bulk path)
//   cold=48      32 KiB cold reads (open, seek, read into a misaligned buffer, close): a motion miss
//   opens=50     open+close pairs
//   rate=225     KB/s of the paced FMV-like stream (16 KiB refills, 64 KiB buffer)
//   idle=0 load=0   seconds of stream alone, then stream + bulk loader + cold reads, twice.
//                Both default to 0 (off). The stream phases run on probe threads with static
//                8 KiB stacks, and in Flycast they have faulted or reset the guest (4 of 6 runs;
//                once after the idle phase alone: PC inside the probe stack array). Cause not
//                found. Pass idle=N / load=N only for diagnosis.
//   lock=1       serialise the probe's direct reads with one mutex (lock=0: three threads read
//                concurrently through KOS, which reset/hung the guest in Flycast; diagnostic only)
//   seqfile= streamfile= bulkfile= coldfiles=a,b,c  (paths under /cd)
// Results go to the log ring ("ioprobe:" lines), to the re4dc_ioprobe struct (RAM telemetry),
// to VMU LCD pages (6 pages of 12x5 characters, 3 s each, forever), and to a PERF_HUD row.
// With DISC_ASYNC=1 the stream, bulk and cold reads under load go through the disc service
// at STREAM / BULK / MOTION priority. With DISC_ASYNC=0 they are direct KOS reads from three
// threads, serialised by a mutex unless lock=0.
#include <kos.h>
#include <dc/maple.h>
#include <dc/vmu_fb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "re4dc_platform.h"
extern "C" int re4dc_fixture_read(const char* path, char* buffer, unsigned size);   // os.cpp

extern "C" {
struct Re4dcIoProbe {
    unsigned version, done, async;
    unsigned seq_bytes, seq64_kbs, seq128_kbs;
    unsigned cold_n, cold_p50_us, cold_p95_us, cold_max_us;
    unsigned open_n, open_p50_us, open_max_us;
    unsigned rate_kbs;
    unsigned idle_chunks, idle_underruns, idle_deficit_us, idle_read_max_us;
    unsigned load_chunks, load_underruns, load_deficit_us, load_read_max_us;
    unsigned load_bulk_bytes, load_bulk_kbs;
    unsigned load_cold_n, load_cold_p50_us, load_cold_p95_us, load_cold_max_us;
    // whole motion keys (/cd/dc/mot/*.fcv): today's misaligned read vs the disc service
    unsigned key_n, key_direct_p50_us, key_direct_max_us, key_svc_p50_us, key_svc_max_us, key_mismatch;
    // timer_us_gettime64() reads that went backwards (clamped by now()), and the largest step
    unsigned clock_back_n, clock_back_max_us;
    // the same keys read synchronously through an aligned bounce (body stream + <32 B tail)
    unsigned key_aligned_p50_us, key_aligned_max_us;
    // 2 KiB aligned read after a 2 KiB read at distance d (next sector, 1, 16, 128 MiB): p50/max
    unsigned seek_n, seek_p50_us[4], seek_max_us[4];
    // the stream + load pass again with 32-byte-aligned cold reads (lock: reads serialised)
    unsigned lock, load2_chunks, load2_underruns, load2_deficit_us, load2_read_max_us, load2_bulk_kbs;
    unsigned load2_cold_n, load2_cold_p50_us, load2_cold_p95_us, load2_cold_max_us;
};
__attribute__((used)) Re4dcIoProbe re4dc_ioprobe;
}

namespace {
struct Params {
    unsigned seq_mb = 8, cold = 48, opens = 50, rate = 225, idle_s = 0, load_s = 0, lock = 1;
    char seqfile[64] = "/cd/bgm/bio4evt.sbb";
    char streamfile[64] = "/cd/bgm/bio4bgm.sbb";
    char bulkfile[64] = "/cd/st1/r101.arc";
    char coldfiles[4][64] = {"/cd/bgm/bio4evt.sbb", "/cd/bgm/bio4bgm.sbb", "/cd/em/em10.drs", "/cd/em/em12.drs"};
    unsigned ncold = 4;
};
Params P;

constexpr unsigned kChunk = 16384, kRing = 65536, kCold = 32768, kBulk = 131072;
unsigned char* scratch;            // arena borrow (32-byte aligned)
unsigned char *seqbuf, *bulkbuf, *streambuf, *coldbuf;

// Monotonic: the OFF arm saw timer_us_gettime64() step backwards between two threads' reads
// (pinned KOS), and an unsigned delta turned into a near-infinite thd_sleep. Clamp and count.
unsigned long long now()
{
    static unsigned long long last;
    const int irq = irq_disable();
    unsigned long long t = timer_us_gettime64();
    if (t < last) {
        const unsigned back = (unsigned) (last - t);
        ++re4dc_ioprobe.clock_back_n;
        if (back > re4dc_ioprobe.clock_back_max_us) re4dc_ioprobe.clock_back_max_us = back;
        t = last;
    } else {
        last = t;
    }
    irq_restore(irq);
    return t;
}

unsigned rng = 0x2545F491u;
unsigned rnd() { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }

void parse(char* t)
{
    for (char* tok = strtok(t, " \t\r\n"); tok; tok = strtok(nullptr, " \t\r\n")) {
        char* eq = strchr(tok, '=');
        if (!eq) continue;
        *eq = 0;
        const char* v = eq + 1;
        auto num = [&](const char* k, unsigned& out) { if (!strcmp(tok, k)) out = (unsigned) atoi(v); };
        num("seq", P.seq_mb); num("cold", P.cold); num("opens", P.opens); num("rate", P.rate);
        num("idle", P.idle_s); num("load", P.load_s); num("lock", P.lock);
        auto str = [&](const char* k, char* out) { if (!strcmp(tok, k)) { strncpy(out, v, 63); out[63] = 0; } };
        str("seqfile", P.seqfile); str("streamfile", P.streamfile); str("bulkfile", P.bulkfile);
        if (!strcmp(tok, "coldfiles")) {
            P.ncold = 0;
            char tmp[256]; strncpy(tmp, v, 255); tmp[255] = 0;
            for (char* s = tmp; s && *s && P.ncold < 4;) {
                char* c = strchr(s, ',');
                if (c) *c = 0;
                strncpy(P.coldfiles[P.ncold++], s, 63);
                s = c ? c + 1 : nullptr;
            }
        }
    }
}

void sort_u(unsigned* a, unsigned n)
{
    for (unsigned i = 1; i < n; ++i) { unsigned v = a[i], j = i; while (j && a[j - 1] > v) { a[j] = a[j - 1]; --j; } a[j] = v; }
}
void pct(unsigned* a, unsigned n, unsigned& p50, unsigned& p95, unsigned& mx)
{
    if (!n) { p50 = p95 = mx = 0; return; }
    sort_u(a, n);
    p50 = a[n / 2]; p95 = a[(n * 95) / 100 < n ? (n * 95) / 100 : n - 1]; mx = a[n - 1];
}

unsigned file_size(const char* path)
{
    file_t f = fs_open(path, O_RDONLY);
    if (f < 0) return 0;
    const unsigned n = (unsigned) fs_total(f);
    fs_close(f);
    return n;
}

// Sequential pass: `bytes` from `offset` in `chunk` pieces into an aligned buffer (KOS stream path).
unsigned seq_pass(const char* path, unsigned offset, unsigned bytes, unsigned chunk)
{
    file_t f = fs_open(path, O_RDONLY);
    if (f < 0) return 0;
    fs_seek(f, offset, SEEK_SET);
    const unsigned long long t0 = now();
    unsigned done = 0;
    while (done < bytes) {
        const ssize_t n = fs_read(f, seqbuf, chunk);
        if (n <= 0) break;
        done += (unsigned) n;
    }
    const unsigned long long us = now() - t0;
    fs_close(f);
    return us ? (unsigned) ((unsigned long long) done * 1000000ull / 1024ull / us) : 0;
}

// Direct reads from several probe threads go through one mutex (P.lock): KOS keeps one
// streaming state per drive, and unserialised readers hung or reset the guest in Flycast.
mutex_t g_io = MUTEX_INITIALIZER;
struct IoLock {
    IoLock() { if (P.lock) mutex_lock(&g_io); }
    ~IoLock() { if (P.lock) mutex_unlock(&g_io); }
};

// One motion-miss-shaped read: 32 KiB at a random 2 KiB-aligned offset, misaligned destination.
unsigned cold_read_direct()
{
    IoLock lk;
    const char* path = P.coldfiles[rnd() % P.ncold];
    const unsigned long long t0 = now();
    file_t f = fs_open(path, O_RDONLY);
    if (f < 0) return 0;
    const unsigned size = (unsigned) fs_total(f);
    const unsigned off = size > kCold ? (rnd() % (size - kCold)) & ~2047u : 0;
    fs_seek(f, off, SEEK_SET);
    unsigned got = 0;
    while (got < kCold) { const ssize_t n = fs_read(f, coldbuf + 16 + got, kCold - got); if (n <= 0) break; got += (unsigned) n; }
    fs_close(f);
    return (unsigned) (now() - t0);
}

// The same read into a 32-byte-aligned buffer (one stream command), then copied.
unsigned cold_read_aligned()
{
    IoLock lk;
    const char* path = P.coldfiles[rnd() % P.ncold];
    const unsigned long long t0 = now();
    file_t f = fs_open(path, O_RDONLY);
    if (f < 0) return 0;
    const unsigned size = (unsigned) fs_total(f);
    const unsigned off = size > kCold ? (rnd() % (size - kCold)) & ~2047u : 0;
    fs_seek(f, off, SEEK_SET);
    unsigned got = 0;
    while (got < kCold) { const ssize_t n = fs_read(f, seqbuf + got, kCold - got); if (n <= 0) break; got += (unsigned) n; }
    fs_close(f);
    memcpy(coldbuf + 16, seqbuf, got);
    return (unsigned) (now() - t0);
}

unsigned cold_read_under_load(bool aligned)
{
    return aligned ? cold_read_aligned() : cold_read_direct();
}

// A motion key the way the disc service reads it, synchronously: the 32-byte multiple through
// an aligned bounce (one KOS stream command), then the <32-byte tail after moving the fd off the
// stream (a block-cache read; KOS's tail stream request is the one that never returns).
int aligned_key_read(const char* path, unsigned size, unsigned char* dst, unsigned char* bounce)
{
    file_t f = fs_open(path, O_RDONLY);
    if (f < 0) return -1;
    const unsigned body = size & ~31u;
    unsigned got = 0;
    while (got < body) { const ssize_t n = fs_read(f, bounce + got, body - got); if (n <= 0) break; got += (unsigned) n; }
    memcpy(dst, bounce, got);
    if (got == body && got < size) {
        static unsigned char tail[64] __attribute__((aligned(32)));
        if (got) { fs_seek(f, 0, SEEK_SET); fs_seek(f, got, SEEK_SET); }
        const unsigned start = got;
        while (got < size) { const ssize_t n = fs_read(f, tail + 16 + (got - start), size - got); if (n <= 0) break; got += (unsigned) n; }
        memcpy(dst + start, tail + 16, got - start);
    }
    fs_close(f);
    return (int) got;
}

// Seek behaviour: a 2 KiB aligned read, then another at distance d past it (d = 0 continues the
// stream). The second read is timed. Flycast charges per GD command, not per distance; on a
// GD-ROM or GDEMU this is the curve to measure.
void seek_sweep()
{
    Re4dcIoProbe& r = re4dc_ioprobe;
    static const unsigned dist[4] = {0, 1u << 20, 16u << 20, 128u << 20};
    static unsigned lat[4][16];
    file_t f = fs_open(P.streamfile, O_RDONLY);
    if (f < 0) return;
    const unsigned size = (unsigned) fs_total(f);
    unsigned n = 0;
    for (unsigned i = 0; i < 16; ++i) {
        for (unsigned k = 0; k < 4; ++k) {
            const unsigned d = dist[k] < size / 2 ? dist[k] : (size / 2) & ~2047u;
            const unsigned base = (rnd() % (size - d - 8192)) & ~2047u;
            fs_seek(f, base, SEEK_SET);
            fs_read(f, seqbuf, 2048);
            fs_seek(f, base + 2048 + d, SEEK_SET);
            const unsigned long long t0 = now();
            fs_read(f, seqbuf, 2048);
            lat[k][i] = (unsigned) (now() - t0);
        }
        ++n;
    }
    fs_close(f);
    r.seek_n = n;
    unsigned p;
    for (unsigned k = 0; k < 4; ++k) pct(lat[k], n, r.seek_p50_us[k], p, r.seek_max_us[k]);
    re4dc_log("ioprobe: seek2k n=%u p50 next=%u 1M=%u 16M=%u 128M=%u us; max %u/%u/%u/%u us\n", n,
              r.seek_p50_us[0], r.seek_p50_us[1], r.seek_p50_us[2], r.seek_p50_us[3],
              r.seek_max_us[0], r.seek_max_us[1], r.seek_max_us[2], r.seek_max_us[3]);
}

// ---- paced stream: a consumer drains `rate` from a kRing buffer; the reader refills kChunk
// pieces whenever a chunk of space is free. An underrun is the consumer running dry.
struct StreamRun {
    unsigned seconds, chunks, underruns, deficit_us, read_max_us;
    volatile int stop;
};
StreamRun g_stream;
volatile int g_bulk_stop;
unsigned g_bulk_bytes;
unsigned long long g_bulk_us;

unsigned stream_read(file_t f, unsigned off)
{
    IoLock lk;
    fs_seek(f, off, SEEK_SET);
    unsigned got = 0;
    while (got < kChunk) { const ssize_t n = fs_read(f, streambuf + got, kChunk - got); if (n <= 0) break; got += (unsigned) n; }
    return got;
}

void* stream_main(void*)
{
    StreamRun& s = g_stream;
    file_t f = -1;
    f = fs_open(P.streamfile, O_RDONLY);
    if (f < 0) return nullptr;
    const unsigned size = file_size(P.streamfile);
    const double rate = P.rate * 1024.0;   // bytes per second
    unsigned off = size > 64u * 1048576u ? (rnd() % (size / 2)) & ~2047u : 0;
    unsigned long long filled = 0;
    // Prefill the buffer, then start the consumer clock.
    while (filled < kRing) { stream_read(f, off); off += kChunk; filled += kChunk; }
    const unsigned long long t_play = now(), t_end = t_play + s.seconds * 1000000ull;
    for (;;) {
        unsigned long long t = now();
        if (t >= t_end || s.stop) break;
        // Wait for a chunk of free space: consumed(t) >= filled + kChunk - kRing.
        const double need = (double) (filled + kChunk - kRing);
        const unsigned long long t_space = t_play + (unsigned long long) (need / rate * 1e6);
        if (t < t_space) {                             // at most 50 ms, then re-check stop/end
            const unsigned long long ms = (t_space - t) / 1000 + 1;
            thd_sleep(ms > 50 ? 50 : (int) ms);
            continue;
        }
        const unsigned long long t0 = now();
        stream_read(f, off);
        const unsigned long long t1 = now();
        const unsigned rd = (unsigned) (t1 - t0);
        if (rd > s.read_max_us) s.read_max_us = rd;
        const double consumed = (t1 - t_play) * rate / 1e6;
        if (consumed > (double) filled) {                 // ran dry before this chunk landed
            ++s.underruns;
            const unsigned deficit = (unsigned) ((consumed - filled) / rate * 1e6);
            if (deficit > s.deficit_us) s.deficit_us = deficit;
            filled = (unsigned long long) consumed;       // resume from the dry point
        }
        filled += kChunk; off += kChunk; ++s.chunks;
        if (off + kChunk > size) off = 0;
    }
    fs_close(f);
    return nullptr;
}

// Bulk loader shaped like the source DVD queue: back-to-back 128 KiB reads of one big file.
void* bulk_main(void*)
{
    const unsigned size = file_size(P.bulkfile);
    const unsigned long long t0 = now();
    file_t f = fs_open(P.bulkfile, O_RDONLY);
    if (f < 0) return nullptr;
    unsigned off = 0;
    while (!g_bulk_stop) {
        if (off >= size) off = 0;
        const unsigned want = size - off < kBulk ? size - off : kBulk;
        ssize_t n;
        {
            IoLock lk;
            fs_seek(f, off, SEEK_SET);
            n = fs_read(f, bulkbuf, want);
        }
        thd_pass();   // let a waiting reader take the lock between pieces
        if (n <= 0) break;
        off += (unsigned) n; g_bulk_bytes += (unsigned) n;
    }
    fs_close(f);
    g_bulk_us = now() - t0;
    return nullptr;
}

// Static stacks: KOS malloc has only a few KB left once the arena is carved.
alignas(32) unsigned char stacks[2][8192];
alignas(32) unsigned char vmu_stack[4096];
kthread_t* spawn(void* (*fn)(void*), int prio, const char* label, unsigned slot)
{
    kthread_attr_t a;
    memset(&a, 0, sizeof(a));
    a.stack_size = sizeof(stacks[slot]);
    a.stack_ptr = stacks[slot];
    a.prio = prio;
    a.label = label;
    return thd_create_ex(&a, fn, nullptr);
}

void stream_phase(unsigned seconds, bool load, bool aligned, unsigned* chunks, unsigned* under, unsigned* deficit,
                  unsigned* rdmax, unsigned* cold /* n, p50, p95, max */, unsigned* bulk_kbs)
{
    g_stream = StreamRun{seconds, 0, 0, 0, 0, 0};
    g_bulk_stop = 0; g_bulk_bytes = 0; g_bulk_us = 0;
    kthread_t* st = spawn(stream_main, 9, "ioprobe-stream", 0);
    // Below the probe's own thread (16): with Flycast's near-instant DMA a direct bulk loop
    // would otherwise never yield the CPU back to the cold-read loop.
    kthread_t* bl = load ? spawn(bulk_main, 17, "ioprobe-bulk", 1) : nullptr;
    static unsigned lat[256];
    unsigned n = 0;
    if (load) {
        const unsigned long long t_end = now() + seconds * 1000000ull;
        while (now() < t_end && n < 256) { lat[n++] = cold_read_under_load(aligned); thd_sleep(150); }
        g_bulk_stop = 1;
        g_stream.stop = 1;
    }
    thd_join(st, nullptr);
    if (bl) thd_join(bl, nullptr);
    *chunks = g_stream.chunks; *under = g_stream.underruns; *deficit = g_stream.deficit_us; *rdmax = g_stream.read_max_us;
    if (load) {
        cold[0] = n;
        pct(lat, n, cold[1], cold[2], cold[3]);
        re4dc_ioprobe.load_bulk_bytes = g_bulk_bytes;
        *bulk_kbs = g_bulk_us ? (unsigned) ((unsigned long long) g_bulk_bytes * 1000000ull / 1024ull / g_bulk_us) : 0;
    }
}

// ---- VMU pages (dca3 style: vmu_printf to every LCD), 12 x 5 characters of the 4x6 font.
char pages[6][128];
void ms1(char* out, unsigned us) { sprintf(out, "%u.%u", us / 1000, (us % 1000) / 100); }
void build_pages()
{
    const Re4dcIoProbe& r = re4dc_ioprobe;
    char a[16], b[16], c[16], d[16];
    ms1(a, r.open_p50_us); ms1(b, r.open_max_us);
    snprintf(pages[0], 128, "IO 1/6 %s\nSQ64 %6uK\nSQ128%6uK\nOPN %s\nOPNX %s", r.async ? "ASY" : "SYN",
             r.seq64_kbs, r.seq128_kbs, a, b);
    ms1(a, r.cold_p50_us); ms1(b, r.cold_p95_us); ms1(c, r.cold_max_us);
    snprintf(pages[1], 128, "IO 2/6 COLD\n32K MS n%u\nP50 %s\nP95 %s\nMAX %s", r.cold_n, a, b, c);
    ms1(a, r.idle_deficit_us); ms1(b, r.idle_read_max_us);
    snprintf(pages[2], 128, "IO 3/6 STRM\n%uK/S IDLE\nUND %u\nDEF %s\nRDX %s", r.rate_kbs, r.idle_underruns, a, b);
    ms1(a, r.load_deficit_us); ms1(b, r.load_read_max_us);
    snprintf(pages[3], 128, "IO 4/6 +LD\nUND %u\nDEF %s\nRDX %s\nBLK %uK", r.load_underruns, a, b, r.load_bulk_kbs);
    ms1(a, r.load_cold_p50_us); ms1(b, r.load_cold_p95_us); ms1(c, r.load_cold_max_us);
    snprintf(pages[4], 128, "IO 5/6 +LD\nCOLD n%u\nP50 %s\nP95 %s\nMAX %s", r.load_cold_n, a, b, c);
    ms1(a, r.key_direct_p50_us); ms1(b, r.key_aligned_p50_us); ms1(c, r.seek_p50_us[1]); ms1(d, r.seek_p50_us[3]);
    (void) d;
    snprintf(pages[5], 128, "IO 6/6 KEY\nDIR %s\nALN %s\nSK1M %s\nUND %u/%u", a, b, c,
             r.load_underruns, r.load2_underruns);
}
void* vmu_main(void*)
{
    for (unsigned i = 0;; i = (i + 1) % 6) { vmu_printf("%s", pages[i]); thd_sleep(3000); }
    return nullptr;
}
}  // namespace

extern "C" void re4dc_ioprobe_run(void)
{
    static int entered;
    if (entered++) { re4dc_log("ioprobe: re-entered (%d), ignored\n", entered); return; }
    char text[256] = {};
    if (re4dc_fixture_read("/cd/dc/ioprobe.txt", text, sizeof(text) - 1) < 0) return;
    parse(text);
    Re4dcIoProbe& r = re4dc_ioprobe;
    memset(&r, 0, sizeof(r));
    r.version = 1;
    r.rate_kbs = P.rate;
    r.lock = P.lock;
    const unsigned need = kBulk + kBulk + kRing + kCold + 64;
    scratch = (unsigned char*) ((re4dc_mem.arena_lo + 31) & ~31ul);
    if (re4dc_mem.arena_hi - (unsigned long) scratch < need) { re4dc_log("ioprobe: arena too small\n"); return; }
    seqbuf = scratch; bulkbuf = seqbuf + kBulk; streambuf = bulkbuf + kBulk; coldbuf = streambuf + kRing;
    re4dc_log("ioprobe: start async=%u lock=%u seq=%uMB cold=%u opens=%u rate=%u idle=%us load=%us\n", r.async,
              P.lock, P.seq_mb, P.cold, P.opens, P.rate, P.idle_s, P.load_s);
    vmu_printf("IO PROBE\nRUNNING");

    // 1. sequential (two disjoint regions so the second pass is cold as well)
    const unsigned seq = P.seq_mb * 1048576u;
    const unsigned fsz = file_size(P.seqfile);
    const unsigned base = fsz > 3 * seq ? (fsz / 3) & ~2047u : 0;
    r.seq_bytes = seq;
    r.seq64_kbs = seq_pass(P.seqfile, base, seq, 65536);
    r.seq128_kbs = seq_pass(P.seqfile, base + seq, seq, kBulk);
    re4dc_log("ioprobe: seq file=%s bytes=%u kbs64=%u kbs128=%u\n", P.seqfile, seq, r.seq64_kbs, r.seq128_kbs);

    // 2. cold 32 KiB reads, 3. open/close
    static unsigned lat[256];
    const unsigned nc = P.cold < 256 ? P.cold : 256;
    for (unsigned i = 0; i < nc; ++i) lat[i] = cold_read_direct();
    r.cold_n = nc;
    pct(lat, nc, r.cold_p50_us, r.cold_p95_us, r.cold_max_us);
    const unsigned no = P.opens < 256 ? P.opens : 256;
    static const char* const open_set[] = {"/cd/st1/r100.dar", "/cd/st1/r101.arc", "/cd/em/em12.drs", "/cd/evd/r100s03.evd",
                                           "/cd/bgm/bio4bgm.sbb", "/cd/dc/padscript.txt", "/cd/em/pl00.drs", "/cd/st1/r120.dar"};
    unsigned no_ok = 0;
    for (unsigned i = 0; i < no; ++i) {
        const unsigned long long t0 = now();
        file_t f = fs_open(open_set[i % 8], O_RDONLY);
        if (f >= 0) { fs_close(f); lat[no_ok++] = (unsigned) (now() - t0); }
    }
    unsigned p95;
    r.open_n = no_ok;
    pct(lat, no_ok, r.open_p50_us, p95, r.open_max_us);
    re4dc_log("ioprobe: cold32k n=%u p50=%u p95=%u max=%u us; open n=%u p50=%u max=%u us\n", r.cold_n, r.cold_p50_us,
              r.cold_p95_us, r.cold_max_us, r.open_n, r.open_p50_us, r.open_max_us);

    // 3b. whole motion keys, as native_motion.cpp reads them: today's path (open, misaligned
    // read, close) and, with DISC_ASYNC, the disc service MOTION class; bytes must match.
    {
        static unsigned lat2[64], lat3[64];
        unsigned nk = 0, nsvc = 0;
        file_t d = fs_open("/cd/dc/mot", O_RDONLY | O_DIR);
        const dirent_t* de;
        while (d >= 0 && nk < 64 && (de = fs_readdir(d)) != nullptr) {
            if (de->size <= 0 || de->size > (int) kCold) continue;
            char path[288];   // "/cd/dc/mot/" + a 256-byte dirent name
            snprintf(path, sizeof(path), "/cd/dc/mot/%s", de->name);
            const unsigned size = (unsigned) de->size;
            unsigned long long t0;
            t0 = now();
            file_t f = fs_open(path, O_RDONLY);
            if (f < 0) continue;
            unsigned got = 0;
            while (got < size) { const ssize_t n = fs_read(f, coldbuf + 16 + got, size - got); if (n <= 0) break; got += (unsigned) n; }
            fs_close(f);
            lat[nk] = (unsigned) (now() - t0);
            unsigned h1 = 2166136261u;
            for (unsigned j = 0; j < got; ++j) h1 = (h1 ^ coldbuf[16 + j]) * 16777619u;
            t0 = now();
            const int g3 = aligned_key_read(path, size, coldbuf + 16, seqbuf);
            lat3[nk] = (unsigned) (now() - t0);
            unsigned h3 = 2166136261u;
            for (int j = 0; j < g3; ++j) h3 = (h3 ^ coldbuf[16 + j]) * 16777619u;
            if (g3 != (int) got || h3 != h1) ++r.key_mismatch;
            (void) h1;
            ++nk;
        }
        if (d >= 0) fs_close(d);
        unsigned p;
        r.key_n = nk;
        pct(lat, nk, r.key_direct_p50_us, p, r.key_direct_max_us);
        pct(lat2, nsvc, r.key_svc_p50_us, p, r.key_svc_max_us);
        pct(lat3, nk, r.key_aligned_p50_us, p, r.key_aligned_max_us);
        re4dc_log("ioprobe: motion keys n=%u direct p50=%u max=%u us aligned p50=%u max=%u us service p50=%u max=%u us "
                  "mismatches=%u\n", r.key_n, r.key_direct_p50_us, r.key_direct_max_us, r.key_aligned_p50_us,
                  r.key_aligned_max_us, r.key_svc_p50_us, r.key_svc_max_us, r.key_mismatch);
    }
    seek_sweep();

    // 4. paced stream alone, then with a bulk loader and cold reads competing
    if (P.idle_s) {
    unsigned cold_dummy[4], kbs_dummy;
    stream_phase(P.idle_s, false, false, &r.idle_chunks, &r.idle_underruns, &r.idle_deficit_us, &r.idle_read_max_us,
                 cold_dummy, &kbs_dummy);
    re4dc_log("ioprobe: stream idle rate=%uKB/s chunks=%u underruns=%u deficit=%u us readmax=%u us\n", P.rate,
              r.idle_chunks, r.idle_underruns, r.idle_deficit_us, r.idle_read_max_us);
    }
    if (P.load_s) {
    stream_phase(P.load_s, true, false, &r.load_chunks, &r.load_underruns, &r.load_deficit_us, &r.load_read_max_us,
                 &r.load_cold_n, &r.load_bulk_kbs);
    re4dc_log("ioprobe: stream+load misaligned-cold chunks=%u underruns=%u deficit=%u us readmax=%u us bulk=%u B %u KB/s "
              "cold32k n=%u p50=%u p95=%u max=%u us\n", r.load_chunks, r.load_underruns, r.load_deficit_us,
              r.load_read_max_us, r.load_bulk_bytes, r.load_bulk_kbs, r.load_cold_n, r.load_cold_p50_us,
              r.load_cold_p95_us, r.load_cold_max_us);
    stream_phase(P.load_s, true, true, &r.load2_chunks, &r.load2_underruns, &r.load2_deficit_us, &r.load2_read_max_us,
                 &r.load2_cold_n, &r.load2_bulk_kbs);
    re4dc_log("ioprobe: stream+load aligned-cold chunks=%u underruns=%u deficit=%u us readmax=%u us bulk %u KB/s "
              "cold32k n=%u p50=%u p95=%u max=%u us\n", r.load2_chunks, r.load2_underruns, r.load2_deficit_us,
              r.load2_read_max_us, r.load2_bulk_kbs, r.load2_cold_n, r.load2_cold_p50_us, r.load2_cold_p95_us,
              r.load2_cold_max_us);
    }

    memset(scratch, 0, need);
    r.done = 1;
    build_pages();
    kthread_attr_t a;
    memset(&a, 0, sizeof(a));
    a.create_detached = true; a.stack_size = sizeof(vmu_stack); a.stack_ptr = vmu_stack; a.prio = 10; a.label = "ioprobe-vmu";
    thd_create_ex(&a, vmu_main, nullptr);
    re4dc_log("ioprobe: done clock_back n=%u max=%u us\n", re4dc_ioprobe.clock_back_n, re4dc_ioprobe.clock_back_max_us);
}

// PERF_HUD row: seq128 KB/s, cold p95 (0.1 ms), stream underruns under load, worst deficit (0.1 ms).
extern "C" int re4dc_ioprobe_hud(unsigned v[4])
{
    const Re4dcIoProbe& r = re4dc_ioprobe;
    if (!r.done) return 0;
    v[0] = r.seq128_kbs; v[1] = (r.cold_p95_us + 50) / 100; v[2] = r.load_underruns; v[3] = (r.load_deficit_us + 50) / 100;
    return 4;
}
