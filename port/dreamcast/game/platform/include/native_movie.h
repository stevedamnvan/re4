#pragma once
// PS2 prerecorded cinematic presentation (R4FMV003 transport). The source event
// caller stays authoritative for every gameplay effect; this layer presents the
// picture and sound only and reports how the presentation ended.
//
// Movie ids are (room << 8) | event number written as hex digits, so r100s03 is
// 0x10003 and r101s21 is 0x10121; the file is /cd/dc/movie/rRRRsEE.seq.
#ifdef __cplusplus
extern "C" {
#endif
enum {
    RE4DC_MOVIE_RUNNING = 0,
    RE4DC_MOVIE_EOF = 1,        // natural end: last picture shown, audio drained
    RE4DC_MOVIE_SKIP = 2,       // a new press of `mask` (GameCube PAD bits) after release
    RE4DC_MOVIE_ERROR = 3,      // presentation failed after it was attempted
    RE4DC_MOVIE_CANCEL = 4,     // owner cancelled (room retire)
    RE4DC_MOVIE_UNHANDLED = 5,  // no media for this id: nothing presented, source path applies
};
typedef void (*RouteMoviePictureTick)(unsigned picture);
// 1 when /cd/dc/movie/<id>.seq exists and carries a valid header.
int re4dc_movie_available(unsigned id);
// Plays the whole movie before returning (movie-owned presentation at 29.97 fps
// on the vblank clock; the caller's game frame does not run meanwhile). `tick`
// sees each presented picture index, for source per-cut hooks. Skip: `mask` in
// GameCube PAD bits (START 0x1000 = the source event cancel key, Key bit 29).
int re4dc_movie_play(unsigned id, unsigned mask, RouteMoviePictureTick tick);
int re4dc_movie_cancel(void);
// Index of the last presented picture; 0 before the first.
unsigned re4dc_movie_picture(void);
#ifdef __cplusplus
}
#endif
