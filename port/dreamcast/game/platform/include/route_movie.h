#pragma once
// Route cutscenes: a source event presented by its PS2 prerecorded movie while
// the source caller keeps every gameplay effect (docs/ROUTE_CUTSCENES.md).
#include "native_movie.h"
enum {
    ROUTE_MOVIE_SND_EVENT = 1,  // evd header sndFlag bit31 clear: SndEventInit/SndEventEnd
    ROUTE_MOVIE_KEEP_POSE = 2,  // caller sets Event StatusFlag 0x800: ExeEndEvt keeps the pose
};
class Event;
typedef void (*RouteEvtFunc)(Event*);
typedef void (*RouteMovieTick)(unsigned picture);  // per-cut source hooks, by movie picture
// Runs in the caller's scenario task until the movie ends. Returns the movie
// terminal (EOF/SKIP/ERROR); RE4DC_MOVIE_UNHANDLED means nothing happened and
// the caller's source event path applies unchanged.
int RouteMoviePlay(unsigned id, unsigned flags, RouteEvtFunc func, RouteMovieTick tick);
