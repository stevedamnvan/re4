// PS2 prerecorded cinematics as presentation for source events (PS2-inspired
// profile). Generalised from the experiment/ps2-fmv-spike r120s00 adapter:
// same R4FMV003 transport (MPEG-1 WxH 29.97 + PCM16 stereo 32 kHz, one
// interleaved record per picture), same bounded reader, decoder and AICA
// stream; any route movie by id, and a native_ui override so a movie shows
// while the source holds its picture (System_flg 0x400).
// In-room budget: everything below comes from the current source heap and is
// returned at the terminal. At the route size 288x192 the player stages about
// 250 KB (two I/P frames 166 KB, video 32 KB, read 16 KB, PCM 16 KB, AICA
// separation 8 KB, callback 8 KB, strip 4.5 KB); r100's entry event has
// 311 KB free. The KOS heap is not used (native_movie_stream.c).
// The source event caller owns every gameplay effect and the skip semantics;
// this file never touches source state.
#include <kos.h>
#include <dc/sound/stream.h>
#include <dc/sound/sound.h>
#include <fcntl.h>
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <malloc.h>
#include "re4dc_platform.h"
#include "native_ui.h"
#include "native_io.h"
#include "native_movie.h"
#include "../../room/room_storage.hpp"
#if RE4DC_ROUTE_MOVIES
namespace { void* plm_alloc(size_t n); }
// Two I/P reference frames, fixed buffers: no growth path is reachable.
#define PLM_MALLOC(n) plm_alloc(n)
#define PLM_REALLOC(p,n) nullptr
#define PLM_FREE(p) ((void)0)
#define PLM_NO_STDIO
#define PLM_VIDEO_TWO_FRAMES
#define PLM_RE4DC_FAST        // bit-exact fast paths (third_party/PL_MPEG_PIN.md)
#define PL_MPEG_IMPLEMENTATION
#include "../third_party/pl_mpeg.h"
extern "C" int re4dc_movie_stream_initialized();
extern "C" unsigned re4dc_movie_stream_active();
extern "C" unsigned re4dc_movie_stream_staged;
extern "C" void re4dc_pad_consume_movie_skip(unsigned);
// Fixture state reports are optional: the pad-script fixture defines this
// (uncommitted pad.cpp work); without it the movie reports nothing.
extern "C" void re4dc_fixture_state(const char* name,int a,int b) __attribute__((weak));
static void movie_state(int a,int b){if(re4dc_fixture_state)re4dc_fixture_state("movie",a,b);}
extern "C" int re4dc_ui_movie_open(unsigned width, unsigned height);
extern "C" int re4dc_ui_movie_present_now();
extern "C" unsigned re4dc_pad_movie_buttons();
extern "C" unsigned long re4dc_vi_retrace_count(void);
extern "C" int re4dc_ui_movie_upload_begin();
extern "C" void re4dc_ui_movie_upload_rows(const void* uyvy, unsigned y, unsigned rows);
extern "C" void re4dc_ui_movie_upload_end();
extern "C" int re4dc_ui_movie_close();
extern "C" unsigned re4dc_ui_movie_presented();
extern "C" uint64_t re4dc_ui_movie_first_picture_us();
extern "C" int re4dc_ui_movie_last_presented();
namespace {
// Hard caps: every write is checked against them, nothing grows.
// snd_stream_fill asks for half the 8 KiB ring per channel: 8 KiB interleaved.
constexpr unsigned VideoCap=32768, AudioCap=16384, AudioStart=12288, CallbackCap=8192, ReadCap=16384;
constexpr unsigned Rows=8, MaxWidth=320, MaxHeight=240;
constexpr unsigned MaxAllocs=10;
struct Movie {
    unsigned id=0; char path[40]{};
    file_t file=-1; plm_buffer_t* input=nullptr; plm_video_t* decoder=nullptr;
    unsigned char *pcm=nullptr,*callback=nullptr,*readbuf=nullptr,*rows=nullptr;
    void* allocs[MaxAllocs]{}; unsigned nallocs=0, staged=0;
    unsigned transport_left=0,read_at=0,read_used=0;
    snd_stream_hnd_t stream=-1; bool owns_service=false,started=false,failed=false,texture=false;
    unsigned pcm_used=0,video_left=0,audio_left=0,frames=0,uploaded=0,underruns=0,silence_bytes=0;
    unsigned samples=0,last_real_sample=0,expected_frames=0,audio_bytes=0;
    unsigned long long entered=0,start=0,max_read=0,max_decode=0,max_convert=0,max_upload=0;
    unsigned long long sum_decode=0,sum_convert=0,sum_upload=0,duration_us=0;
    int heap_before=0,heap_active=0,terminal=0; unsigned vram_before=0,width=0,height=0;
    unsigned shown=0,dropped=0,late=0,cadence2=0,cadence_other=0,max_gap=0,last_submit=0,v0=0;
    unsigned long long sum_present=0,max_present=0,sum_idle=0;
} m;
void* plm_alloc(size_t n){
    if(m.nallocs==MaxAllocs)return nullptr;
    void* p=re4dc_ui_stage_alloc((unsigned)n);
    if(p){m.allocs[m.nallocs++]=p;m.staged+=n;}
    return p;
}
unsigned little(const unsigned char* p){return p[0]|p[1]<<8|p[2]<<16|p[3]<<24;}
void* audio(snd_stream_hnd_t,int requested,int* received){
    // The pinned snd_stream.c passes a byte count.
    unsigned bytes=(unsigned)requested;
    if(bytes>CallbackCap){
        if(!m.failed)re4dc_log("route movie audio request %u exceeds %u\n",bytes,CallbackCap);
        m.failed=true;*received=0;return nullptr;
    }
    unsigned take=bytes<m.pcm_used?bytes:m.pcm_used;
    std::memcpy(m.callback,m.pcm,take);std::memmove(m.pcm,m.pcm+take,m.pcm_used-take);m.pcm_used-=take;
    if(take<bytes){std::memset(m.callback+take,0,bytes-take);if(m.audio_left){++m.underruns;m.silence_bytes+=bytes-take;}}
    if(take)m.last_real_sample=m.samples+take/4;
    m.samples+=bytes/4;*received=requested;return m.callback;
}
int poll_audio(){return snd_stream_poll(m.stream);}
// Sequential transport through the shared ReaderGuard: 32 KiB aligned chunks,
// the header is sector padded so every full chunk stays aligned.
bool transport(void* destination,unsigned bytes){
    auto* out=(unsigned char*)destination;
    while(bytes){
        if(m.read_at==m.read_used){
            unsigned n=m.transport_left<ReadCap?m.transport_left:ReadCap;
            if(!n)return false;
            auto t=timer_us_gettime64();bool ok=true;
            {Re4dcIoScope owner;unsigned aligned=n&~31U;
             if(aligned)ok=re4dc::storage::read_aligned_chunk(m.file,m.readbuf,aligned);
             if(ok&&aligned<n)ok=re4dc::storage::read_exact(m.file,m.readbuf+aligned,n-aligned);}
            auto dt=timer_us_gettime64()-t;if(dt>m.max_read)m.max_read=dt;if(!ok)return false;
            m.transport_left-=n;m.read_at=0;m.read_used=n;
        }
        unsigned n=m.read_used-m.read_at;if(n>bytes)n=bytes;
        std::memcpy(out,m.readbuf+m.read_at,n);out+=n;m.read_at+=n;bytes-=n;
    }
    return true;
}
bool record(){
    unsigned char h[8];if(!transport(h,8))return false;
    unsigned nv=little(h),na=little(h+4);
    if(nv>16384||na>8192||nv>m.video_left||na>m.audio_left||(!nv&&!na))return false;
    plm_buffer_discard_read_bytes(m.input);
    if(nv>VideoCap-m.input->length||na>AudioCap-m.pcm_used)return false;
    if(!transport(m.input->bytes+m.input->length,nv)||!transport(m.pcm+m.pcm_used,na))return false;
    m.input->length+=nv;m.input->has_ended=0;m.pcm_used+=na;m.video_left-=nv;m.audio_left-=na;
    if(!m.video_left)plm_buffer_signal_end(m.input);
    return true;
}
// Interleaved records carry one picture of PCM (<= 4276 bytes); only the
// audio-only tail records carry up to 8 KiB. The AICA asks for 8 KiB (64 ms)
// at a time, so the PCM ring is topped up before every poll, not once a step.
bool feed(){
    for(unsigned i=0;i<4&&(m.video_left||m.audio_left);++i){
        plm_buffer_discard_read_bytes(m.input);
        if(VideoCap-m.input->length<16384||AudioCap-m.pcm_used<(m.video_left?4352u:8192u))break;
        if(!record())return false;
    }
    return true;
}
void path_for(unsigned id,char* out,unsigned size){
    snprintf(out,size,"/cd/dc/movie/r%03xs%02x.seq",(id>>8)&0xfff,id&0xff);
}
bool header(file_t f,unsigned* video,unsigned* audio_bytes,unsigned* frames,unsigned* width=nullptr,unsigned* height=nullptr){
    unsigned char h[32];
    if(!re4dc::storage::read_exact(f,h,32))return false;
    const unsigned w=little(h+8),hh=little(h+12);
    // Macroblock sizes only (the PVR row load needs 32-byte rows); the 512x256
    // texture and the staging budget bound the rest.
    if(std::memcmp(h,"R4FMV003",8)||!w||!hh||(w&15)||(hh&15)||w>MaxWidth||hh>MaxHeight||little(h+28)!=0)return false;
    if(width)*width=w;
    if(height)*height=hh;
    *video=little(h+16);*audio_bytes=little(h+20);*frames=little(h+24);
    return *video>=4096 && *video<=16000000 && *audio_bytes>=16384 && *audio_bytes<=24000000 &&
           !(*audio_bytes&3) && *frames && *frames<=6000;
}
void memory(const char* phase){
    auto k=mallinfo();
    re4dc_log("route movie %s: id=%05x source_heap=%d staged=%u vram_free=%u aica_largest_any=%u kos_free=%u stream_init=%d stream_active=%u\n",
        phase,m.id,re4dc_ui_heap_free(),m.staged,(unsigned)pvr_mem_available(),(unsigned)snd_mem_available(),(unsigned)k.fordblks,
        re4dc_movie_stream_initialized(),re4dc_movie_stream_active());
}
int finish(int status){
    if(m.terminal)status=m.terminal;else m.terminal=status;
    const unsigned presented=m.texture?re4dc_ui_movie_presented():0;
    if(m.stream>=0){snd_stream_stop(m.stream);snd_stream_destroy(m.stream);m.stream=-1;}
    // Retire only a service this movie initialised, after its own stream is gone.
    if(m.owns_service&&re4dc_movie_stream_active()==0){snd_stream_shutdown();m.owns_service=false;}
    if(m.file>=0){Re4dcIoScope owner;fs_close(m.file);m.file=-1;}
    // The texture is freed once the last scene that samples it has rendered.
    for(unsigned tries=0;m.texture&&!re4dc_ui_movie_close()&&tries<100;++tries)thd_sleep(1);
    m.texture=false;
    for(unsigned i=0;i<m.nallocs;++i)re4dc_ui_stage_free(m.allocs[i]);
    const unsigned long long wall=timer_us_gettime64()-(m.start?m.start:m.entered);
    const unsigned d=m.frames?m.frames:1;
    re4dc_log("route movie terminal=%d id=%05x frames=%u/%u uploaded=%u presented=%u wall_us=%llu media_us=%llu underruns=%u silence_bytes=%u heap_before=%d heap_active=%d staged=%u\n",
        status,m.id,m.frames,m.expected_frames,m.uploaded,presented,wall,m.duration_us,m.underruns,m.silence_bytes,m.heap_before,m.heap_active,m.staged);
    re4dc_log("route movie cost id=%05x decode_avg_us=%llu decode_max_us=%llu convert_avg_us=%llu convert_max_us=%llu upload_avg_us=%llu upload_max_us=%llu present_avg_us=%llu present_max_us=%llu read_max_us=%llu idle_us=%llu\n",
        m.id,m.sum_decode/d,m.max_decode,m.sum_convert/(m.uploaded?m.uploaded:1),m.max_convert,
        m.sum_upload/(m.uploaded?m.uploaded:1),m.max_upload,m.sum_present/(m.shown?m.shown:1),m.max_present,m.max_read,m.sum_idle);
    re4dc_log("route movie cadence id=%05x shown=%u dropped=%u late=%u two_field=%u other=%u max_gap_fields=%u (29.97 fps = one picture per 2 fields)\n",
        m.id,m.shown,m.dropped,m.late,m.cadence2,m.cadence_other,m.max_gap);
    memory("retired");
    movie_state(4,status);
    m=Movie{};
    return status;
}
bool open(unsigned id){
    m.id=id;m.entered=timer_us_gettime64();m.heap_before=re4dc_ui_heap_free();m.vram_before=pvr_mem_available();
    path_for(id,m.path,sizeof(m.path));
    movie_state(0,(int)(id&0xffff));
    {Re4dcIoScope owner;m.file=fs_open(m.path,O_RDONLY);}
    if(m.file<0)return false;
    {Re4dcIoScope owner;if(!header(m.file,&m.video_left,&m.audio_left,&m.expected_frames,&m.width,&m.height))return false;}
    m.audio_bytes=m.audio_left;
    auto size=fs_total(m.file);if(size<2048||size>40000000)return false;
    m.transport_left=size-2048;
    {Re4dcIoScope owner;if(fs_seek(m.file,2048,SEEK_SET)!=2048)return false;}
    const unsigned long long video_us=(unsigned long long)m.expected_frames*1001000ULL/30,audio_us=(unsigned long long)m.audio_bytes*1000000ULL/128000;
    m.duration_us=video_us>audio_us?video_us:audio_us;
    unsigned char* rb=(unsigned char*)plm_alloc(ReadCap+32);
    m.readbuf=rb?(unsigned char*)(((uintptr_t)rb+31)&~(uintptr_t)31):nullptr;
    m.pcm=(unsigned char*)plm_alloc(AudioCap);m.callback=(unsigned char*)plm_alloc(CallbackCap);m.rows=(unsigned char*)plm_alloc(Rows*m.width*2);
    if(!m.readbuf||!m.pcm||!m.callback||!m.rows)return false;
    m.input=plm_buffer_create_with_capacity(VideoCap);if(!m.input||!m.input->bytes||!record())return false;
    auto* seq=m.input->bytes;
    if(m.input->length<8||std::memcmp(seq,"\0\0\1\xb3",4)||unsigned((seq[4]<<4)|(seq[5]>>4))!=m.width||unsigned(((seq[5]&15)<<8)|seq[6])!=m.height||(seq[7]&15)!=4)return false;
    m.decoder=plm_video_create_with_buffer(m.input,1);
    if(!m.decoder||plm_video_get_width(m.decoder)!=(int)m.width||plm_video_get_height(m.decoder)!=(int)m.height)return false;
    plm_video_set_no_delay(m.decoder,1); // I/P-only: the newest picture is the output
    if(!re4dc_ui_movie_open(m.width,m.height))return false;
    m.texture=true;
    m.owns_service=!re4dc_movie_stream_initialized();
    if(snd_stream_init_ex(2,8192)<0)return false;
    m.stream=snd_stream_alloc(audio,8192);if(m.stream<0)return false;
    m.staged+=re4dc_movie_stream_staged;
    m.heap_active=re4dc_ui_heap_free();
    memory("active");
    re4dc_log("route movie start: id=%05x path=%s size=%ux%u frames=%u media_us=%llu staged=%u heap=%d->%d\n",
        id,m.path,m.width,m.height,m.expected_frames,m.duration_us,m.staged,m.heap_before,m.heap_active);
    return true;
}
// PVR samples packed UYVY: expand studio range with two small tables, 8 rows
// at a time into a small staging strip uploaded by the existing frame owner.
void convert_upload(plm_frame_t* f){
    static unsigned char yfull[256],cfull[256];static bool initialized;
    if(!initialized){for(int i=0;i<256;++i){int y=(i-16)*255/219,c=(i-128)*255/224+128;
        yfull[i]=y<0?0:y>255?255:y;cfull[i]=c<0?0:c>255?255:c;}initialized=true;}
    auto t=timer_us_gettime64();
    unsigned long long convert_us=0;
    const unsigned pairs=m.width/2;
    for(unsigned y0=0;y0<m.height;y0+=Rows){
        auto c0=timer_us_gettime64();
        auto* out=(unsigned*)m.rows;
        for(unsigned r=0;r<Rows;++r){
            const unsigned y=y0+r;
            const auto* yy=f->y.data+y*f->y.width;
            const auto* u=f->cb.data+(y/2)*f->cb.width;
            const auto* v=f->cr.data+(y/2)*f->cr.width;
            for(unsigned x=0;x<pairs;++x)out[r*pairs+x]=cfull[u[x]]|yfull[yy[x*2]]<<8|cfull[v[x]]<<16|yfull[yy[x*2+1]]<<24;
        }
        convert_us+=timer_us_gettime64()-c0;
        re4dc_ui_movie_upload_rows(m.rows,y0,Rows);
    }
    re4dc_ui_movie_upload_end();
    const auto total=timer_us_gettime64()-t, upload=total>convert_us?total-convert_us:0;
    m.sum_convert+=convert_us;if(convert_us>m.max_convert)m.max_convert=convert_us;
    m.sum_upload+=upload;if(upload>m.max_upload)m.max_upload=upload;
    ++m.uploaded;
}
}
extern "C" int re4dc_movie_available(unsigned id){
    char path[40];path_for(id,path,sizeof(path));
    Re4dcIoScope owner;file_t f=fs_open(path,O_RDONLY);if(f<0)return 0;
    unsigned v,a,n;bool ok=header(f,&v,&a,&n);fs_close(f);return ok;
}
namespace {
plm_frame_t* decode_next(){
    if(!m.video_left)plm_buffer_signal_end(m.input);
    auto t=timer_us_gettime64();plm_frame_t* f=plm_video_decode(m.decoder);
    auto dt=timer_us_gettime64()-t;
    if(f){m.sum_decode+=dt;if(dt>m.max_decode)m.max_decode=dt;++m.frames;}
    return f;
}
// Upload picture `index` and submit it one field before its flip vblank.
bool show(plm_frame_t* f,unsigned index,unsigned now,RouteMoviePictureTick tick){
    if(!re4dc_ui_movie_upload_begin())return false;
    convert_upload(f);
    auto t=timer_us_gettime64();
    if(!re4dc_ui_movie_present_now())return false;
    auto dt=timer_us_gettime64()-t;m.sum_present+=dt;if(dt>m.max_present)m.max_present=dt;
    if(m.shown){const unsigned gap=now-m.last_submit;if(gap==2)++m.cadence2;else ++m.cadence_other;if(gap>m.max_gap)m.max_gap=gap;}
    m.last_submit=now;++m.shown;
    if(m.shown==1){movie_state(1,(int)(m.id&0xffff));
        re4dc_log("route movie first picture: id=%05x latency_us=%llu\n",m.id,timer_us_gettime64()-m.entered);}
    if(tick)tick(index);
    return true;
}
}
extern "C" unsigned re4dc_movie_picture(){return m.shown?m.shown-1:0;}
// Movie-owned presentation: the caller's game frame is not run while the
// picture plays (the world is hidden; the caller is a source task that simply
// does not sleep). Picture k flips at vblank v0 + 2k: 29.97 fps on NTSC,
// every picture held exactly two fields. Decode of k+1 overlaps the display
// of k; a picture two fields late is dropped (never shown late) so audio and
// picture stay on one clock.
extern "C" int re4dc_movie_play(unsigned id,unsigned mask,RouteMoviePictureTick tick){
    if(!open(id)){
        const bool missing=m.file<0;
        int st=finish(RE4DC_MOVIE_ERROR);
        if(missing){re4dc_log("route movie id=%05x: no media, source presentation applies\n",id);return RE4DC_MOVIE_UNHANDLED;}
        return st;
    }
    unsigned held=re4dc_pad_movie_buttons();
    bool armed=!(held&mask);
    // Prime: PCM for the AICA ring and picture 0, before the clock starts.
    while(m.pcm_used<AudioStart&&m.audio_left)if(!feed()||m.failed)return finish(RE4DC_MOVIE_ERROR);
    plm_frame_t* pending=decode_next();
    if(!pending||!feed())return finish(RE4DC_MOVIE_ERROR);
    m.start=timer_us_gettime64();snd_stream_start(m.stream,32000,1);m.started=true;
    m.v0=re4dc_vi_retrace_count()+1;
    unsigned k=0;
    for(;;){
        const unsigned b=re4dc_pad_movie_buttons(),pressed=b&~held;held=b;
        if(!(b&mask))armed=true;
        if(armed&&(pressed&mask)){
            re4dc_pad_consume_movie_skip(pressed&mask);
            re4dc_log("route movie skip: id=%05x mask=%x picture=%u elapsed_us=%llu\n",m.id,pressed&mask,k,timer_us_gettime64()-m.entered);
            return finish(RE4DC_MOVIE_SKIP);
        }
        if(!feed()||poll_audio()<0||m.failed)return finish(RE4DC_MOVIE_ERROR);
        const unsigned now=re4dc_vi_retrace_count(),due=m.v0+2*k;
        if(pending&&now+1>=due){
            if(now>=due+2&&m.frames<m.expected_frames){++m.dropped;pending=nullptr;++k;}
            else{
                if(now>due)++m.late;
                if(!show(pending,k,now,tick))return finish(RE4DC_MOVIE_ERROR);
                pending=nullptr;++k;
            }
        }
        if(!pending&&m.frames<m.expected_frames){
            pending=decode_next();
            if(!pending)return finish(RE4DC_MOVIE_ERROR);
            continue;
        }
        if(!pending&&!m.audio_left&&!m.pcm_used&&m.samples>=m.last_real_sample+4096&&now>=m.v0+2*k)
            return finish(RE4DC_MOVIE_EOF);
        if(timer_us_gettime64()-m.start>m.duration_us+10000000ULL)return finish(RE4DC_MOVIE_ERROR); // stalled media
        auto t=timer_us_gettime64();
        while(re4dc_vi_retrace_count()==now&&timer_us_gettime64()-t<2000){} // ahead: wait (bounded) for the next field
        m.sum_idle+=timer_us_gettime64()-t;
    }
}
extern "C" int re4dc_movie_cancel(){return m.entered?finish(RE4DC_MOVIE_CANCEL):RE4DC_MOVIE_CANCEL;}
#else
extern "C" int re4dc_movie_available(unsigned){return 0;}
extern "C" unsigned re4dc_movie_picture(){return 0;}
extern "C" int re4dc_movie_play(unsigned,unsigned,RouteMoviePictureTick){return RE4DC_MOVIE_UNHANDLED;}
extern "C" int re4dc_movie_cancel(){return RE4DC_MOVIE_CANCEL;}
#endif
