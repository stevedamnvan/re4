/* game30 GAME_TRIG=1 (needs GAME_FDLIBM=1): sinf / cosf of the game's recovered fdlibm
 * (src/lib/fdlibm, newlib 1.8.2) with their helpers copied in as static inline functions:
 *   __kernel_sinf (kf_sin.c), __kernel_cosf (kf_cos.c) and the |x| <= 2^7*pi/2 paths of
 *   __ieee754_rem_pio2f (ef_rem_pio2.c); larger or non-finite arguments still call the original
 *   __ieee754_rem_pio2f, which recomputes from x.
 * Every float operation is the original's, in the original's order, on the original constants; the
 * file is compiled -O2 -ffp-contract=off (no fmac, no reassociation without -ffast-math), so each
 * result is bit-identical by construction. What goes away is two call levels per evaluation (the
 * r100 tick makes ~2,800 sin/cos kernel evaluations per frame) and the helpers' spread over four
 * objects in the I-cache. Checked exhaustively on the host (all 2^32 inputs of both functions,
 * flush-to-zero like the SH-4's FPSCR.DN=1): tools/trig_exhaustive.c.
 * sf_sin.o and sf_cos.o drop out of the link (game30.mk); the kernels and ef_rem_pio2 stay for
 * tanf and the large-argument path.
 * GAME_SINCOS=1 (design-logic P6) adds re4dc_sincosf: sinf and cosf of one argument with the |x| test
 * and the argument reduction done once. Each output is the same kernel call on the same reduced
 * argument (rem_pio2f is a pure function of x) that sinf / cosf make, so both are bit-identical by
 * construction; checked for all 2^32 inputs on the host (tools/game30/sincos_exhaustive.sh).
 */
#include "fdlibm.h"

static const float
/* kf_sin.c */
k_half =  5.0000000000e-01, /* 0x3f000000 */
S1  = -1.6666667163e-01, /* 0xbe2aaaab */
S2  =  8.3333337680e-03, /* 0x3c088889 */
S3  = -1.9841270114e-04, /* 0xb9500d01 */
S4  =  2.7557314297e-06, /* 0x3638ef1b */
S5  = -2.5050759689e-08, /* 0xb2d72f34 */
S6  =  1.5896910177e-10, /* 0x2f2ec9d3 */
/* kf_cos.c */
one =  1.0000000000e+00, /* 0x3f800000 */
C1  =  4.1666667908e-02, /* 0x3d2aaaab */
C2  = -1.3888889225e-03, /* 0xbab60b61 */
C3  =  2.4801587642e-05, /* 0x37d00d01 */
C4  = -2.7557314297e-07, /* 0xb493f27c */
C5  =  2.0875723372e-09, /* 0x310f74f6 */
C6  = -1.1359647598e-11, /* 0xad47d74e */
/* ef_rem_pio2.c */
r_half =  5.0000000000e-01, /* 0x3f000000 */
invpio2 =  6.3661980629e-01, /* 0x3f22f984 */
pio2_1  =  1.5707855225e+00, /* 0x3fc90f80 */
pio2_1t =  1.0804334124e-05, /* 0x37354443 */
pio2_2  =  1.0804273188e-05, /* 0x37354400 */
pio2_2t =  6.0770999344e-11, /* 0x2e85a308 */
pio2_3  =  6.0770943833e-11, /* 0x2e85a300 */
pio2_3t =  6.1232342629e-17; /* 0x248d3132 */

/* ef_rem_pio2.c */
static const __int32_t npio2_hw[] = {
0x3fc90f00, 0x40490f00, 0x4096cb00, 0x40c90f00, 0x40fb5300, 0x4116cb00,
0x412fed00, 0x41490f00, 0x41623100, 0x417b5300, 0x418a3a00, 0x4196cb00,
0x41a35c00, 0x41afed00, 0x41bc7e00, 0x41c90f00, 0x41d5a000, 0x41e23100,
0x41eec200, 0x41fb5300, 0x4203f200, 0x420a3a00, 0x42108300, 0x4216cb00,
0x421d1400, 0x42235c00, 0x4229a500, 0x422fed00, 0x42363600, 0x423c7e00,
0x4242c700, 0x42490f00
};

/* kf_sin.c __kernel_sinf */
static inline __attribute__((always_inline)) float k_sinf(float x, float y, int iy)
{
	float z,r,v;
	__int32_t ix;
	GET_FLOAT_WORD(ix,x);
	ix &= 0x7fffffff;			/* high word of x */
	if(ix<0x32000000)			/* |x| < 2**-27 */
	   {if((int)x==0) return x;}		/* generate inexact */
	z	=  x*x;
	v	=  z*x;
	r	=  S2+z*(S3+z*(S4+z*(S5+z*S6)));
	if(iy==0) return x+v*(S1+z*r);
	else      return x-((z*(k_half*y-v*r)-y)-v*S1);
}

/* kf_cos.c __kernel_cosf */
static inline __attribute__((always_inline)) float k_cosf(float x, float y)
{
	float a,hz,z,r,qx;
	__int32_t ix;
	GET_FLOAT_WORD(ix,x);
	ix &= 0x7fffffff;			/* ix = |x|'s high word*/
	if(ix<0x32000000) {			/* if x < 2**27 */
	    if(((int)x)==0) return one;		/* generate inexact */
	}
	z  = x*x;
	r  = z*(C1+z*(C2+z*(C3+z*(C4+z*(C5+z*C6)))));
	if(ix < 0x3e99999a) 			/* if |x| < 0.3 */
	    return one - ((float)0.5*z - (z*r - x*y));
	else {
	    if(ix > 0x3f480000) {		/* x > 0.78125 */
		qx = (float)0.28125;
	    } else {
	        SET_FLOAT_WORD(qx,ix-0x01000000);	/* x/4 */
	    }
	    hz = (float)0.5*z-qx;
	    a  = one-qx;
	    return a - (hz - (z*r-x*y));
	}
}

/* ef_rem_pio2.c __ieee754_rem_pio2f, callers' |x| > pi/4 already established */
static inline __attribute__((always_inline)) __int32_t rem_pio2f(float x, float *y)
{
	float z,w,t,r,fn;
	__int32_t i,j,n,ix,hx;
	GET_FLOAT_WORD(hx,x);
	ix = hx&0x7fffffff;
	if(ix<0x4016cbe4) {  /* |x| < 3pi/4, special case with n=+-1 */
	    if(hx>0) {
		z = x - pio2_1;
		if((ix&0xfffffff0)!=0x3fc90fd0) { /* 24+24 bit pi OK */
		    y[0] = z - pio2_1t;
		    y[1] = (z-y[0])-pio2_1t;
		} else {		/* near pi/2, use 24+24+24 bit pi */
		    z -= pio2_2;
		    y[0] = z - pio2_2t;
		    y[1] = (z-y[0])-pio2_2t;
		}
		return 1;
	    } else {	/* negative x */
		z = x + pio2_1;
		if((ix&0xfffffff0)!=0x3fc90fd0) { /* 24+24 bit pi OK */
		    y[0] = z + pio2_1t;
		    y[1] = (z-y[0])+pio2_1t;
		} else {		/* near pi/2, use 24+24+24 bit pi */
		    z += pio2_2;
		    y[0] = z + pio2_2t;
		    y[1] = (z-y[0])+pio2_2t;
		}
		return -1;
	    }
	}
	if(ix<=0x43490f80) { /* |x| ~<= 2^7*(pi/2), medium size */
	    t  = fabsf(x);
	    n  = (__int32_t) (t*invpio2+r_half);
	    fn = (float)n;
	    r  = t-fn*pio2_1;
	    w  = fn*pio2_1t;	/* 1st round good to 40 bit */
	    if(n<32&&(ix&0xffffff00)!=npio2_hw[n-1]) {
		y[0] = r-w;	/* quick check no cancellation */
	    } else {
	        __uint32_t high;
	        j  = ix>>23;
	        y[0] = r-w;
		GET_FLOAT_WORD(high,y[0]);
	        i = j-((high>>23)&0xff);
	        if(i>8) {  /* 2nd iteration needed, good to 57 */
		    t  = r;
		    w  = fn*pio2_2;
		    r  = t-w;
		    w  = fn*pio2_2t-((t-r)-w);
		    y[0] = r-w;
		    GET_FLOAT_WORD(high,y[0]);
		    i = j-((high>>23)&0xff);
		    if(i>25)  {	/* 3rd iteration need, 74 bits acc */
		    	t  = r;	/* will cover all possible cases */
		    	w  = fn*pio2_3;
		    	r  = t-w;
		    	w  = fn*pio2_3t-((t-r)-w);
		    	y[0] = r-w;
		    }
		}
	    }
	    y[1] = (r-y[0])-w;
	    if(hx<0) 	{y[0] = -y[0]; y[1] = -y[1]; return -n;}
	    else	 return n;
	}
	/* large arguments (and inf/NaN, excluded by the callers): the original, from x */
	return __ieee754_rem_pio2f(x,y);
}

/* sf_sin.c */
float sinf(float x)
{
	float y[2],z=0.0;
	__int32_t n,ix;
	GET_FLOAT_WORD(ix,x);
    /* |x| ~< pi/4 */
	ix &= 0x7fffffff;
	if(ix <= 0x3f490fd8) return k_sinf(x,z,0);
    /* sin(Inf or NaN) is NaN */
	else if (ix>=0x7f800000) return x-x;
    /* argument reduction needed */
	else {
	    n = rem_pio2f(x,y);
	    switch(n&3) {
		case 0: return  k_sinf(y[0],y[1],1);
		case 1: return  k_cosf(y[0],y[1]);
		case 2: return -k_sinf(y[0],y[1],1);
		default:
			return -k_cosf(y[0],y[1]);
	    }
	}
}

/* sf_cos.c */
float cosf(float x)
{
	float y[2],z=0.0;
	__int32_t n,ix;
	GET_FLOAT_WORD(ix,x);
    /* |x| ~< pi/4 */
	ix &= 0x7fffffff;
	if(ix <= 0x3f490fd8) return k_cosf(x,z);
    /* cos(Inf or NaN) is NaN */
	else if (ix>=0x7f800000) return x-x;
    /* argument reduction needed */
	else {
	    n = rem_pio2f(x,y);
	    switch(n&3) {
		case 0: return  k_cosf(y[0],y[1]);
		case 1: return -k_sinf(y[0],y[1],1);
		case 2: return -k_cosf(y[0],y[1]);
		default:
		        return  k_sinf(y[0],y[1],1);
	    }
	}
}

#if defined(RE4DC_SINCOS) && RE4DC_SINCOS
/* design-logic P6: *s = sinf(x), *c = cosf(x) (the two functions above, one argument reduction) */
void re4dc_sincosf(float x, float *s, float *c)
{
	float y[2],z=0.0;
	__int32_t n,ix;
	GET_FLOAT_WORD(ix,x);
	ix &= 0x7fffffff;
	if(ix <= 0x3f490fd8) {
	    *s = k_sinf(x,z,0);
	    *c = k_cosf(x,z);
	} else if (ix>=0x7f800000) {
	    *s = x-x;
	    *c = x-x;
	} else {
	    n = rem_pio2f(x,y);
	    switch(n&3) {
		case 0: *s =  k_sinf(y[0],y[1],1); *c =  k_cosf(y[0],y[1]); break;
		case 1: *s =  k_cosf(y[0],y[1]);   *c = -k_sinf(y[0],y[1],1); break;
		case 2: *s = -k_sinf(y[0],y[1],1); *c = -k_cosf(y[0],y[1]); break;
		default:
			*s = -k_cosf(y[0],y[1]);   *c =  k_sinf(y[0],y[1],1); break;
	    }
	}
}
#endif
