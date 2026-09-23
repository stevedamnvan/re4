// GD-ROM high-density mount for /cd (D367 W10, GDEMU image).
//
// The pinned KOS (804b319) fs_iso9660 mounts /cd from the LOW-density table
// of contents: init_percd() calls cdrom_read_toc(&toc, false) and uses the
// last data track listed there. On a GD-ROM (a GDI on GDEMU or in Flycast)
// that is track 1, a placeholder in the single-density area. The game's file
// system is track 3 at LBA 45000 in the high-density area, so every
// fs_open("/cd/...") would fail even though the disc boots.
//
// The game link wraps cdrom_read_toc (-Wl,--wrap=cdrom_read_toc, game/Makefile
// GAME_LDFLAGS). When the drive reports a GD-ROM, a low-density request gets
// the high-density TOC instead, so fs_iso9660 finds track 3. fs_iso9660 is the
// only caller in KOS and in the game. A CD-R image (game.cue; disc type is not
// CD_GDROM) takes the original path unchanged, so one ELF boots both images.
// The KOS tree is not modified.
#include <kos.h>
#include <dc/cdrom.h>

#include "re4dc_platform.h"

extern "C" int __real_cdrom_read_toc(cd_toc_t* toc, bool high_density);

extern "C" int __wrap_cdrom_read_toc(cd_toc_t* toc, bool high_density)
{
    if (!high_density) {
        int status = 0, type = -1;
        // fs_iso9660 calls this right after cdrom_reinit(); a busy status read
        // is retried a few times before falling back to the original request.
        for (int tries = 0; tries < 4 && cdrom_get_status(&status, &type) < 0; tries++) type = -1;
        if (type == CD_GDROM && __real_cdrom_read_toc(toc, true) == 0) {
            const uint32_t fad = cdrom_locate_data_track(toc);
            if (fad) {
                static bool logged;
                if (!logged) {
                    logged = true;
                    re4dc_log("gdrom: /cd from high-density TOC, data track FAD %lu (LBA %lu)\n",
                              (unsigned long) fad, (unsigned long) (fad - 150));
                }
                return 0;
            }
        }
    }
    return __real_cdrom_read_toc(toc, high_density);
}
