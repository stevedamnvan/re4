// D367 VMU saves (VMU_SAVE=1, vmusave.mk; empty in the default image): the VMU file layer under
// the virtual memory card (platform/card.cpp). KOS vmufs low-level calls over caller buffers
// (pinned KOS, no vmufs_write: its OVERWRITE deletes before writing). No allocation here.
//
// Write order (design-vmu 5.3), A/B when the free blocks hold the new copy:
//   1. new data blocks into free blocks (FAT changes stay in RAM)   pull: nothing lost
//   2. FAT                                                          pull: leaked blocks, old save intact
//   3. dir block with the new entry = commit                        pull: two copies, newest seq wins
//   4. old entry: dir block, then FAT
// When the VMU is too full for both copies (user decision 2026-09-23), the old copy is released
// in RAM first and the new one written into the freed blocks: FAT, then dir. A pull then risks
// only that one save (a bad CRC -> the game's "damaged file" path); no other file's blocks move.
#if RE4DC_VMU_SAVE
#include <kos.h>
#include <dc/vmufs.h>
#include <dc/maple.h>
#include <dc/maple/vmu.h>
#include <string.h>

#include "vmu_store.h"
#include "re4dc_platform.h"

extern "C" uint16_t net_crc16ccitt(const uint8_t* data, int size, uint16_t start);

namespace {
maple_device_t* dev_of(const VmuStore* s) { return static_cast<maple_device_t*>(s->dev); }
vmu_root_t* root_of(const VmuStore* s) { return reinterpret_cast<vmu_root_t*>(s->root); }
vmu_dir_t* dir_of(const VmuStore* s) { return reinterpret_cast<vmu_dir_t*>(s->dir); }
unsigned dir_count(const VmuStore* s) { return root_of(s)->dir_size * 16U; }

bool is_memcard(maple_device_t* d) { return d && d->valid && (d->info.functions & MAPLE_FUNC_MEMCARD); }

// dir entries hold names without a terminator; vmufs_dir_find compares 12 bytes with strncmp.
void set_name(vmu_dir_t* e, const char* name)
{
    memset(e->filename, 0, sizeof(e->filename));
    for (unsigned i = 0; i < sizeof(e->filename) && name[i]; ++i) e->filename[i] = name[i];
}

struct Lock {
    Lock() { vmufs_mutex_lock(); }
    ~Lock() { vmufs_mutex_unlock(); }
};

// The same 32x32 16-colour placeholder icon as tools/vmusave.py default_icon().
void build_icon(unsigned char* hdr_pal, unsigned char* px)
{
    static const uint16_t pal[4] = {0x0000, 0xF311, 0xFCCB, 0xFA22};
    for (int i = 0; i < 16; ++i) {
        const uint16_t c = i < 4 ? pal[i] : 0xF000;
        hdr_pal[2 * i] = (unsigned char) c;
        hdr_pal[2 * i + 1] = (unsigned char) (c >> 8);
    }
    memset(px, 0, 512);
    for (int y = 0; y < 32; ++y)
        for (int x = 0; x < 32; ++x) {
            const int c = (x == 0 || x == 31 || y == 0 || y == 31) ? 2 : (x >= 10 && x <= 21 && y >= 10 && y <= 21) ? 3 : 1;
            const int i = y * 32 + x;
            px[i >> 1] |= (i & 1) ? c : c << 4;
        }
}
}  // namespace

extern "C" {

int vmus_pick(VmuStore* s)
{
    maple_device_t* d = maple_enum_dev(0, 1);  // A1
    if (!is_memcard(d)) {
        d = nullptr;
        for (int p = 0; p < 4 && !d; ++p)
            for (int u = 1; u < 3 && !d; ++u) {
                maple_device_t* c = maple_enum_dev(p, u);
                if (is_memcard(c)) d = c;
            }
    }
    s->dev = d;
    s->mounted = 0;
    if (!d) return VMUS_NOCARD;
    s->port = d->port;
    s->unit = d->unit;
    return VMUS_OK;
}

int vmus_present(const VmuStore* s)
{
    if (!s->dev) return 0;
    maple_device_t* d = maple_enum_dev(s->port, s->unit);
    return d == s->dev && is_memcard(d);
}

int vmus_mount(VmuStore* s, void* root512, void* fat512, void* dir6656)
{
    s->root = static_cast<unsigned char*>(root512);
    s->fat = static_cast<uint16_t*>(fat512);
    s->dir = static_cast<unsigned char*>(dir6656);
    s->mounted = 0;
    if (!vmus_present(s)) return VMUS_NOCARD;
    Lock lock;
    if (vmufs_root_read(dev_of(s), root_of(s)) < 0) return vmus_present(s) ? VMUS_IOERROR : VMUS_NOCARD;
    const vmu_root_t* r = root_of(s);
    for (int i = 0; i < 16; ++i)
        if (r->magic[i] != 0x55) {
            s->mounted = -1;
            return VMUS_NOFS;
        }
    if (r->fat_size != 1 || r->dir_size == 0 || r->dir_size > 13 || r->blk_cnt == 0 || r->blk_cnt > 241 ||
        r->fat_loc >= 256 || r->dir_loc >= 256) {
        s->mounted = -1;
        return VMUS_NOFS;
    }
    if (vmufs_fat_read(dev_of(s), root_of(s), s->fat) < 0 || vmufs_dir_read(dev_of(s), root_of(s), dir_of(s)) < 0)
        return vmus_present(s) ? VMUS_IOERROR : VMUS_NOCARD;
    for (unsigned i = 0; i < dir_count(s); ++i) dir_of(s)[i].dirty = 0;
    s->mounted = 1;
    return VMUS_OK;
}

int vmus_find(const VmuStore* s, const char* name)
{
    if (s->mounted != 1) return -1;
    char n[12];
    memset(n, 0, sizeof(n));
    for (unsigned i = 0; i < sizeof(n) && name[i]; ++i) n[i] = name[i];
    for (unsigned i = 0; i < dir_count(s); ++i) {
        const vmu_dir_t* e = &dir_of(s)[i];
        if (e->filetype && memcmp(e->filename, n, sizeof(n)) == 0) return (int) i;
    }
    return -1;
}

unsigned vmus_file_blocks(const VmuStore* s, int idx) { return idx < 0 ? 0 : dir_of(s)[idx].filesize; }
unsigned vmus_free_blocks(const VmuStore* s) { return s->mounted == 1 ? (unsigned) vmufs_fat_free(root_of(s), s->fat) : 0; }
unsigned vmus_free_dirents(const VmuStore* s) { return s->mounted == 1 ? (unsigned) vmufs_dir_free(root_of(s), dir_of(s)) : 0; }

int vmus_read(VmuStore* s, int idx, void* buf, unsigned cap, unsigned blocks)
{
    if (s->mounted != 1 || idx < 0) return VMUS_NOFILE;
    const vmu_dir_t* e = &dir_of(s)[idx];
    unsigned n = e->filesize;
    if (blocks && blocks < n) n = blocks;
    if (n * 512 > cap) return VMUS_FULL;
    Lock lock;
    unsigned blk = e->firstblk;
    unsigned char* out = static_cast<unsigned char*>(buf);
    for (unsigned i = 0; i < n; ++i) {
        if (blk >= root_of(s)->blk_cnt) return VMUS_IOERROR;  // chain ends early / corrupt FAT
        if (vmu_block_read(dev_of(s), (uint16_t) blk, out + i * 512) != MAPLE_EOK)
            return vmus_present(s) ? VMUS_IOERROR : VMUS_NOCARD;
        blk = s->fat[blk];
    }
    return VMUS_OK;
}

int vmus_delete(VmuStore* s, const char* name)
{
    const int idx = vmus_find(s, name);
    if (idx < 0) return VMUS_NOFILE;
    Lock lock;
    if (vmufs_file_delete(root_of(s), s->fat, dir_of(s), dir_of(s)[idx].filename) < 0) return VMUS_IOERROR;
    if (vmufs_dir_write(dev_of(s), root_of(s), dir_of(s)) < 0 || vmufs_fat_write(dev_of(s), root_of(s), s->fat) < 0)
        return vmus_present(s) ? VMUS_IOERROR : VMUS_NOCARD;
    return VMUS_OK;
}

int vmus_write(VmuStore* s, const char* name, const void* data, unsigned blocks, const char* old, int* inplace)
{
    *inplace = 0;
    if (s->mounted != 1) return VMUS_NOCARD;
    const int oidx = old ? vmus_find(s, old) : -1;
    const unsigned free_now = vmus_free_blocks(s);
    const unsigned old_blocks = vmus_file_blocks(s, oidx);
    if (vmus_find(s, name) >= 0) return VMUS_IOERROR;           // caller clears stale copies first
    if (free_now < blocks && free_now + old_blocks < blocks) return VMUS_FULL;
    if (vmus_free_dirents(s) == 0 && oidx < 0) return VMUS_FULL;
    Lock lock;
    const bool ab = free_now >= blocks && vmus_free_dirents(s) > 0;
    if (!ab) {
        // In place: release the old copy in RAM; its blocks take the new data.
        *inplace = 1;
        if (vmufs_file_delete(root_of(s), s->fat, dir_of(s), dir_of(s)[oidx].filename) < 0) return VMUS_IOERROR;
    }
    vmu_dir_t e;
    memset(&e, 0, sizeof(e));
    e.filetype = 0x33;
    set_name(&e, name);
    vmufs_dir_fill_time(&e);
    e.hdroff = 0;
    const int rv = vmufs_file_write(dev_of(s), root_of(s), s->fat, dir_of(s), &e,
                                    const_cast<void*>(data), (int) blocks);  // step 1 (+ dir entry in RAM)
    if (rv < 0) {
        // Nothing on the card references the new blocks: reload FAT/dir to drop the RAM changes.
        vmufs_fat_read(dev_of(s), root_of(s), s->fat);
        vmufs_dir_read(dev_of(s), root_of(s), dir_of(s));
        return rv == -2 ? VMUS_FULL : (vmus_present(s) ? VMUS_IOERROR : VMUS_NOCARD);
    }
    if (vmufs_fat_write(dev_of(s), root_of(s), s->fat) < 0) goto io;          // step 2
    if (vmufs_dir_write(dev_of(s), root_of(s), dir_of(s)) < 0) goto io;       // step 3: commit
    if (ab && oidx >= 0) {                                                      // step 4
        if (vmufs_file_delete(root_of(s), s->fat, dir_of(s), dir_of(s)[oidx].filename) < 0) goto io;
        if (vmufs_dir_write(dev_of(s), root_of(s), dir_of(s)) < 0) goto io;
        if (vmufs_fat_write(dev_of(s), root_of(s), s->fat) < 0) goto io;
    }
    return VMUS_OK;
io:
    s->mounted = 0;  // RAM copies may no longer match the card: the next screen remounts
    return vmus_present(s) ? VMUS_IOERROR : VMUS_NOCARD;
}

int vmus_rewrite(VmuStore* s, int idx, const void* data, unsigned blocks)
{
    if (s->mounted != 1 || idx < 0 || dir_of(s)[idx].filesize != blocks) return VMUS_IOERROR;
    Lock lock;
    unsigned blk = dir_of(s)[idx].firstblk;
    const unsigned char* in = static_cast<const unsigned char*>(data);
    for (unsigned i = 0; i < blocks; ++i) {
        if (blk >= root_of(s)->blk_cnt) return VMUS_IOERROR;
        if (vmu_block_write(dev_of(s), (uint16_t) blk, in + i * 512) != MAPLE_EOK)
            return vmus_present(s) ? VMUS_IOERROR : VMUS_NOCARD;
        blk = s->fat[blk];
    }
    return VMUS_OK;
}

unsigned vmus_package(unsigned char* out, const char* desc_long, unsigned payload_len)
{
    static const char kShort[] = "RESIDENT EVIL 4";
    memset(out, 0, 128);
    memset(out, ' ', 48);
    memcpy(out, kShort, sizeof(kShort) - 1);
    for (unsigned i = 0; i < 32 && desc_long[i]; ++i) out[16 + i] = (unsigned char) desc_long[i];
    memcpy(out + 48, "RE4DC", 5);
    out[64] = 1;  // icon_cnt; anim speed, eyecatch 0
    out[72] = (unsigned char) payload_len;
    out[73] = (unsigned char) (payload_len >> 8);
    out[74] = (unsigned char) (payload_len >> 16);
    out[75] = (unsigned char) (payload_len >> 24);
    build_icon(out + 96, out + 128);
    const unsigned total = 128 + 512 + payload_len;
    const uint16_t crc = net_crc16ccitt(out, (int) total, 0);
    out[70] = (unsigned char) crc;
    out[71] = (unsigned char) (crc >> 8);
    const unsigned size = (total + 511) & ~511U;
    memset(out + total, 0, size - total);
    return size;
}

}  // extern "C"
#endif  // RE4DC_VMU_SAVE
