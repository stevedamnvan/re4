// D367 VMU saves (VMU_SAVE=1): the VMU file layer under the virtual memory card
// (platform/vmu_store.cpp). Caller memory only; every call that touches the device is blocking
// and must run on the card worker thread (or at boot), never in the vsync IRQ.
#ifndef RE4DC_VMU_STORE_H
#define RE4DC_VMU_STORE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

typedef struct VmuStore {
    void* dev;              // maple_device_t*, pinned for the session
    int port, unit;
    unsigned char* root;    // 512 B
    uint16_t* fat;          // 512 B
    unsigned char* dir;     // dir_size * 512 B (at most 13 blocks)
    int mounted;            // 1 root/FAT/dir cached, 0 not, -1 not a usable file system
} VmuStore;

enum { VMUS_OK = 0, VMUS_NOCARD = -3, VMUS_IOERROR = -5, VMUS_NOFS = -13, VMUS_NOFILE = -4, VMUS_FULL = -9 };

int vmus_pick(VmuStore* s);                                 // A1 first, then the first memory card
int vmus_present(const VmuStore* s);                        // the pinned device is still there
int vmus_mount(VmuStore* s, void* root512, void* fat512, void* dir6656);
int vmus_find(const VmuStore* s, const char* name);         // dir index or -1
unsigned vmus_file_blocks(const VmuStore* s, int idx);
unsigned vmus_free_blocks(const VmuStore* s);
unsigned vmus_free_dirents(const VmuStore* s);
// Reads the first `blocks` blocks of file `idx` (all when 0) into `buf` (capacity `cap` bytes).
int vmus_read(VmuStore* s, int idx, void* buf, unsigned cap, unsigned blocks);
// Writes `blocks` blocks as `name`. `old` (or NULL) is the live copy it replaces: A/B when the
// free blocks allow (new data, FAT, dir entry = commit, then the old entry and its blocks),
// otherwise in place (the old copy is released first). *inplace reports which.
int vmus_write(VmuStore* s, const char* name, const void* data, unsigned blocks, const char* old, int* inplace);
// Same-size rewrite of an existing file in place, block by block (RE4DCSYS / RE4DCCFG: a torn
// write fails the VMS CRC and the reader falls back to defaults).
int vmus_rewrite(VmuStore* s, int idx, const void* data, unsigned blocks);
int vmus_delete(VmuStore* s, const char* name);             // dir entry first, then the FAT
// VMS package header (128 B) + the 32x32 icon (512 B) in front of `payload_len` bytes already at
// out + 640; fills the CRC. Returns the file size rounded up to blocks.
unsigned vmus_package(unsigned char* out, const char* desc_long, unsigned payload_len);

#ifdef __cplusplus
}
#endif
#endif
