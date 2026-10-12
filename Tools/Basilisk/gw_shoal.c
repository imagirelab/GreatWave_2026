/**
# 孤立波が海底を上って巻く 2D の計算（空気と水の 2 相 NS ＋ VOF）

Feddersen, Hanson, Mostert & Fincham 2024（J. Fluid Mech. 1000, A48）の
風なしの算例の設定（作者が Basilisk の sandbox に公開した
`sandbox/ffeddersen/shoal_RE0_BO4000.c`）を元に、海底の形・波の大きさ・
表面張力・粘りを実行時の引数で変えられるようにした。

元の設定から変えた所：

- 元は、はじめに空気だけの段（風を育てる段、t = 0〜1001）を回してから水の段へ
  移る。風なしの算例なので、ここでは空気を静止させて水の段から始める。
  時刻 t は元の t − 1001 にあたる。
- 海底は区分線形の水深 d(x) で与える（`bathy=x1:d1,x2:d2,...`）。
  元の海底は `bathy=30:1,39.07513:0.37109375`。
- 表面張力は `bo<=0` で切る（`-DTENSION=0` で組んだ版を使う）。
  粘りは `re<=0` で切る（μ = 0）。
- 結果の書き出しは、波の頂を追う窓と、全体の横から見た図の 2 つを、
  水の割合 f と固体の割合 cs の 2 値の格子（uint8）で書く。

無次元：水深 h0 = 1、重力 g = 1、水の密度 1。時間は t√(g/h0)。

使い方（例）：

~~~bash
./gw_shoal level=10 x0=15 xl=0 lbox=60 bathy=30:1,39.07513:0.37109375 \
  re=40000 bo=4000 tend=24 out=runs/A_L10
~~~
*/
#include "embed.h"
#include "navier-stokes/centered.h"
#include "two-phase.h"
#ifndef TENSION
# define TENSION 1
#endif
#if TENSION
# include "tension.h"
#endif
#include "navier-stokes/conserving.h"
#include "reduced.h"

/** ## 実行時の引数（既定は論文の風なしの算例） */
int LEVEL = 10;          // 最も細かい格子の段
double A0 = 0.6;         // 孤立波の振幅 a0/h0
double XC0 = 15.;        // 孤立波の頂の初めの位置
double XL = 0.;          // 領域の左端
double LBOX = 60.;       // 領域の一辺（正方形。上端は y = YTOP）
double YTOP = 10.;       // 静かな水面から上の空気の厚さ
double RE = 4e4;         // 水の Re = √(g h0) h0 / ν_w（<=0 で粘りなし）
double BO = 4000.;       // Bo = ρ_w g h0² / σ（<=0 で表面張力なし）
double RHOR = 1./1020.;  // ρ_a/ρ_w（作者の設定の値）
double MUR = 0.0181;     // μ_a/μ_w（作者の設定の値）
double TEND = 24.;       // 打ち切りの時刻
double TAIL = 3.0;       // 覆いかぶさりを見つけてから、さらに回す時間
double DTC = 0.1;        // ふだんの書き出しの間隔
double DTF = 0.02;       // 巻く前後の細かい書き出しの間隔
double UERR = 4e-4, FERR = 0.01, CSERR = 0.03;  // 格子の細かさを決める誤差の許し
double WB = 6., WF = 4.5, WY0 = -0.7, WY1 = 1.5; // 窓：頂から後ろ・前、下・上
double DENSE_SLOPE = 50.; // 前の面がこの角度（度）を超えたら細かい書き出しに移る
double CKPT = 0.5;       // 途中の状態を保存する間隔（計算機が止まっても続きから回すため）
int MINLEVEL = 5;
char OUTDIR[512] = ".";
#define NBMAX 32
int NB = 0;
double BX[NBMAX], BD[NBMAX];

double bed_depth (double x)
{
  if (NB == 0) return 1.;
  if (x <= BX[0]) return BD[0];
  for (int k = 1; k < NB; k++)
    if (x <= BX[k])
      return BD[k-1] + (BD[k] - BD[k-1])*(x - BX[k-1])/(BX[k] - BX[k-1]);
  return BD[NB-1];
}

/** GN の孤立波（Mostert & Deike 2020、作者の設定と同じ式） */
double waveGN (double x, double y, double a0)
{
  double k = sqrt(3.*a0)/(2.*sqrt(1. + a0));
  return a0*sq(1./cosh(k*x)) - y;
}

double detax (double x, double a0)
{
  double t1 = -sqrt(3.)*a0*sqrt(a0)/sqrt(1. + a0);
  double t2 = sqrt(3.*a0)/(2.*sqrt(1. + a0));
  return t1*sq(1./cosh(t2*x))*tanh(t2*x);
}

/** ## 境界の条件（作者の設定と同じ） */
p[right] = neumann(0.);
pf[right] = neumann(0.);
p[left] = dirichlet(0.);
pf[left] = dirichlet(0.);
u.n[right] = neumann(0.);
u.n[left] = neumann(0.);
u.n[top] = dirichlet(0.);
u.t[top] = neumann(0.);
u.n[bottom] = dirichlet(0.);
u.x[embed] = dirichlet(0.);
u.y[embed] = dirichlet(0.);

static void parse (int argc, char * argv[])
{
  for (int a = 1; a < argc; a++) {
    char * s = argv[a], * v = strchr (s, '=');
    if (!v) { fprintf (stderr, "引数の形が違う：%s\n", s); exit (1); }
    *v++ = '\0';
    if (!strcmp (s, "level")) LEVEL = atoi (v);
    else if (!strcmp (s, "minlevel")) MINLEVEL = atoi (v);
    else if (!strcmp (s, "a0")) A0 = atof (v);
    else if (!strcmp (s, "x0")) XC0 = atof (v);
    else if (!strcmp (s, "xl")) XL = atof (v);
    else if (!strcmp (s, "lbox")) LBOX = atof (v);
    else if (!strcmp (s, "ytop")) YTOP = atof (v);
    else if (!strcmp (s, "re")) RE = atof (v);
    else if (!strcmp (s, "bo")) BO = atof (v);
    else if (!strcmp (s, "rhor")) RHOR = atof (v);
    else if (!strcmp (s, "mur")) MUR = atof (v);
    else if (!strcmp (s, "tend")) TEND = atof (v);
    else if (!strcmp (s, "tail")) TAIL = atof (v);
    else if (!strcmp (s, "dtc")) DTC = atof (v);
    else if (!strcmp (s, "dtf")) DTF = atof (v);
    else if (!strcmp (s, "uerr")) UERR = atof (v);
    else if (!strcmp (s, "ferr")) FERR = atof (v);
    else if (!strcmp (s, "cserr")) CSERR = atof (v);
    else if (!strcmp (s, "wb")) WB = atof (v);
    else if (!strcmp (s, "wf")) WF = atof (v);
    else if (!strcmp (s, "wy0")) WY0 = atof (v);
    else if (!strcmp (s, "wy1")) WY1 = atof (v);
    else if (!strcmp (s, "dense_slope")) DENSE_SLOPE = atof (v);
    else if (!strcmp (s, "ckpt")) CKPT = atof (v);
    else if (!strcmp (s, "out")) { strncpy (OUTDIR, v, 511); OUTDIR[511] = '\0'; }
    else if (!strcmp (s, "bathy")) {
      NB = 0;
      char * tok = strtok (v, ",");
      while (tok && NB < NBMAX) {
        if (sscanf (tok, "%lf:%lf", &BX[NB], &BD[NB]) != 2) {
          fprintf (stderr, "bathy の形が違う：%s\n", tok); exit (1);
        }
        NB++;
        tok = strtok (NULL, ",");
      }
    }
    else { fprintf (stderr, "知らない引数：%s\n", s); exit (1); }
  }
}

FILE * logfp = NULL;
double xcrest = -1e30, ycrest = 0.;
double t_overturn = -1., t_dense = -1.;
int nframe = 0;
double wall0 = 0.;
int restarted = 0;
char ARGS[4096] = "";   // 引数（保存した状態が同じ条件の計算のものかを確かめる）
static double now () { return t; }  // event の中の t は写しなので、大域の時刻を読む

int main (int argc, char * argv[])
{
  for (int a = 1; a < argc; a++)
    if (strncmp (argv[a], "out=", 4)) {
      strncat (ARGS, argv[a], sizeof(ARGS) - strlen(ARGS) - 2);
      strcat (ARGS, " ");
    }
  parse (argc, argv);
  char cmd[600];
  sprintf (cmd, "mkdir -p %s", OUTDIR);
  if (pid() == 0 && system (cmd) != 0) { fprintf (stderr, "%s に書けない\n", OUTDIR); exit (1); }

  rho1 = 1.;
  rho2 = RHOR;
  G.y = -1.;
  CFL = 0.5;
  if (RE > 0) { mu1 = 1./RE; mu2 = MUR/RE; }
  else { mu1 = 0.; mu2 = 0.; }
#if TENSION
  f.sigma = BO > 0 ? 1./BO : 0.;
#else
  if (BO > 0) { fprintf (stderr, "TENSION=0 で組んだ版に bo>0 が渡された\n"); exit (1); }
#endif
  size (LBOX);
  origin (XL, YTOP - LBOX);
  init_grid (1 << (LEVEL - 2 < 7 ? LEVEL - 2 : 7));
  run();
}

/** ## 初めの状態：海底、孤立波、水の中の流速（空気は静止） */
event init (i = 0)
{
  /** 保存した状態があれば続きから（作者の設定と同じく、固体の境界は作り直す） */
  char rf[600], af[600], old[4096] = "";
  sprintf (rf, "%s/restart", OUTDIR);
  sprintf (af, "%s/restart.args", OUTDIR);
  FILE * fa = fopen (af, "r");
  bool same = true;
  if (fa) {
    if (!fgets (old, sizeof(old), fa)) old[0] = '\0';
    fclose (fa);
    old[strcspn (old, "\n")] = '\0';
    same = !strcmp (old, ARGS);
    if (!same && pid() == 0)
      fprintf (stderr, "保存した状態は別の条件の計算のもの。初めから回す\n");
  }
  if (same && restore (file = rf)) {
    solid (cs, fs, y + bed_depth(x));
    char sf[600];
    sprintf (sf, "%s/restart.state", OUTDIR);
    FILE * fp = fopen (sf, "r");
    if (!fp || fscanf (fp, "%d %lf %lf %lf %lf", &nframe, &xcrest, &ycrest, &t_overturn, &t_dense) != 5) {
      fprintf (stderr, "restart.state が読めない\n"); exit (1);
    }
    fclose (fp);
    if (pid() == 0) {
      // log.txt から、保存の後に書いたコマの行を除く
      char ln[600], tmp[600], buf[1024];
      sprintf (ln, "%s/log.txt", OUTDIR);
      sprintf (tmp, "%s/log.txt.tmp", OUTDIR);
      FILE * in = fopen (ln, "r"), * out = fopen (tmp, "w");
      while (in && fgets (buf, sizeof(buf), in)) {
	int k;
	if (buf[0] == '#' || (sscanf (buf, "%d", &k) == 1 && k < nframe))
	  fputs (buf, out);
      }
      if (in) fclose (in);
      fclose (out);
      rename (tmp, ln);
      logfp = fopen (ln, "a");
      fprintf (stderr, "続きから：t = %g、コマ %d\n", now(), nframe);
      char rs[600];
      sprintf (rs, "%s/restarts.txt", OUTDIR);
      FILE * fr = fopen (rs, "a");
      fprintf (fr, "t=%.5f frame=%d\n", now(), nframe);
      fclose (fr);
    }
    restarted = 1;
    return 0;
  }
  double beta = sqrt(3.*A0/(4.*(1. + A0)));
  refine (((level < LEVEL - floor(fabs(x - XC0)*beta) && y > -1.05 && y <= A0)
	   || fabs(waveGN(x - XC0, y, A0)) < LBOX*pow(0.5, level - 1)
	   || fabs(y + bed_depth(x)) < LBOX*pow(0.5, level - 1))
	  && level < LEVEL);
  solid (cs, fs, y + bed_depth(x));
  fraction (f, waveGN(x - XC0, y, A0));
  double C = sqrt(1. + A0);
  foreach() {
    double eta = waveGN(x - XC0, 0, A0);
    double deta = detax(x - XC0, A0);
    u.x[] = C*eta/(1. + eta)*f[];
    u.y[] = -(y + 1.)*C*deta/(eta + 1.)*(1. - eta/(1. + eta))*f[];
  }
}

event adapt (i++)
{
  adapt_wavelet ({cs, f, u}, (double[]){CSERR, FERR, UERR, UERR}, maxlevel = LEVEL, minlevel = MINLEVEL);
}

/** ## 頂の追跡と書き出し */

static void find_crest ()
{
  if (xcrest < -1e29) xcrest = XC0;
  double ym = -1e30;
  double xprev = xcrest;
  foreach (reduction(max:ym))
    if (cs[] > 0.5 && f[] > 1e-3 && f[] < 1. - 1e-3 && fabs(x - xprev) < 3.) {
      double ys = y + (f[] - 0.5)*Delta;
      if (ys > ym) ym = ys;
    }
  double xm = -1e30;
  foreach (reduction(max:xm))
    if (cs[] > 0.5 && f[] > 1e-3 && f[] < 1. - 1e-3 && fabs(x - xprev) < 3.) {
      double ys = y + (f[] - 0.5)*Delta;
      if (ys >= ym - 0.5*Delta && x > xm) xm = x;
    }
  if (ym > -1e29) { ycrest = ym; xcrest = xm; }
}

/** 正方形の格子に f と cs を書く（作者の output_field と同じ回り方）。
戻り値：pid 0 で、f の配列（呼んだ側で free）。 */
static double * sample (double bx0, double by0, double dx, int nx, int ny,
			const char * fname, int write)
{
  coord box1[2] = {{bx0 - dx/2., by0 - dx/2.}, {bx0 + (nx - 0.5)*dx, by0 + (ny - 0.5)*dx}};
  coord cn = {nx, ny}, p;
  int len = 2;
  double ** field = (double **) matrix_new (nx, ny, len*sizeof(double)), * v = field[0];
  for (int k = 0; k < nx*ny*len; k++, v++)
    *v = nodata;
#if _MPI
  v = field[0];
  foreach_region (p, box1, cn, reduction(min:v[:nx*ny*len]))
#else
  foreach_region (p, box1, cn, cpu)
#endif
  {
    double ** alias = field;
    int i = (p.x - box1[0].x)/(box1[1].x - box1[0].x)*cn.x;
    int j = (p.y - box1[0].y)/(box1[1].y - box1[0].y)*cn.y;
    alias[i][len*j] = interpolate_linear (point, f, p.x, p.y, p.z);
    alias[i][len*j + 1] = interpolate_linear (point, cs, p.x, p.y, p.z);
  }
  double * fa = NULL;
  if (pid() == 0) {
    fa = (double *) malloc (sizeof(double)*nx*ny);
    unsigned char * bf = (unsigned char *) malloc (nx*ny), * bc = (unsigned char *) malloc (nx*ny);
    for (int j = 0; j < ny; j++)
      for (int i = 0; i < nx; i++) {
	double fv = field[i][len*j], cv = field[i][len*j + 1];
	if (fv == nodata) fv = 0.;
	if (cv == nodata) cv = 1.;
	fv = clamp (fv, 0., 1.); cv = clamp (cv, 0., 1.);
	fa[j*nx + i] = fv;
	bf[j*nx + i] = (unsigned char) lrint (254.*fv);
	bc[j*nx + i] = (unsigned char) lrint (254.*cv);
      }
    if (write) {
      FILE * fp = fopen (fname, "wb");
      double hd[5] = {t, bx0, by0, dx, xcrest};
      int ni[2] = {nx, ny};
      fwrite ("GWS1", 1, 4, fp);
      fwrite (hd, sizeof(double), 5, fp);
      fwrite (ni, sizeof(int), 2, fp);
      fwrite (bf, 1, nx*ny, fp);
      fwrite (bc, 1, nx*ny, fp);
      fclose (fp);
    }
    free (bf); free (bc);
  }
  matrix_free (field);
  return fa;
}

/** 窓の f から：覆いかぶさった列の数、前の面のいちばん急な角度（度） */
static void overturn_check (double * fa, int nx, int ny, double dx, int * nov, double * slope)
{
  int n = 0;
  double * top = (double *) malloc (sizeof(double)*nx);
  for (int i = 0; i < nx; i++) {
    int st = 0, jt = -1;
    for (int j = ny - 1; j >= 0; j--) {
      int w = fa[j*nx + i] > 0.5;
      if (st == 0 && w) { st = 1; jt = j; }
      else if (st == 1 && !w) st = 2;
      else if (st == 2 && w) { st = 3; break; }
    }
    if (st == 3) n++;
    top[i] = jt;
  }
  double smax = 0.;
  int w = 2;
  for (int i = w; i < nx - w; i++)
    if (top[i - w] >= 0 && top[i + w] >= 0) {
      double s = (top[i - w] - top[i + w])/(2.*w);  // 前（右）へ下がる向きが正
      if (s > smax) smax = s;
    }
  free (top);
  *nov = n;
  *slope = atan (smax)*180./pi;
}

event output (t = 0; t <= TEND + 1e-9; t += DTF)
{
  find_crest();
  bool dense = (t_dense >= 0.);
  bool coarse_time = fabs(remainder(t, DTC)) < 1e-6;
  if (!dense && !coarse_time)
    return 0;
  double dmin = LBOX/(1 << LEVEL);
  int nx = (int) ((WB + WF)/dmin) + 1, ny = (int) ((WY1 - WY0)/dmin) + 1;
  double wx0 = xcrest - WB;
  char name[600];
  sprintf (name, "%s/win_%05d.bin", OUTDIR, nframe);
  double * fa = sample (wx0, WY0, dmin, nx, ny, name, 1);
  // 全体を横から：x は領域全体、y は -1.1〜1.5
  int nfx = 1600, nfy;
  double dfx = LBOX/nfx;
  nfy = (int) (2.6/dfx) + 1;
  sprintf (name, "%s/full_%05d.bin", OUTDIR, nframe);
  double * fb = sample (XL + dfx/2., -1.1, dfx, nfx, nfy, name, 1);
  int nov = 0; double slope = 0.;
  if (pid() == 0) {
    overturn_check (fa, nx, ny, dmin, &nov, &slope);
    free (fa); free (fb);
  }
#if _MPI
  MPI_Bcast (&nov, 1, MPI_INT, 0, MPI_COMM_WORLD);
  MPI_Bcast (&slope, 1, MPI_DOUBLE, 0, MPI_COMM_WORLD);
#endif
  if (t_dense < 0. && (slope > DENSE_SLOPE || nov >= 2))
    t_dense = t;
  if (t_overturn < 0. && nov >= 2)
    t_overturn = t;
  // 量の記録
  double ke = 0., pe = 0., vol = 0.;
  foreach (reduction(+:ke) reduction(+:pe) reduction(+:vol)) {
    double dvv = dv();  // embed では dv() に cs が入っている（Δ²·cs）
    vol += f[]*dvv;
    ke += 0.5*rho(f[])*(sq(u.x[]) + sq(u.y[]))*dvv;
    pe += rho(f[])*y*dvv;
  }
  long nc = 0;
  foreach (reduction(+:nc))
    nc++;
  if (pid() == 0) {
    if (!logfp) {
      char ln[600];
      sprintf (ln, "%s/log.txt", OUTDIR);
      logfp = fopen (ln, "w");
      fprintf (logfp, "# frame t ycrest xcrest ncells vol ke pe n_overturn_cols front_slope_deg dense wall_s dt\n");
      wall0 = 0.;
    }
    fprintf (logfp, "%d %.5f %.6f %.6f %ld %.8e %.8e %.8e %d %.3f %d %.1f %.3e\n",
	     nframe, t, ycrest, xcrest, nc, vol, ke, pe, nov, slope, t_dense >= 0., perf.t, dt);
    fflush (logfp);
  }
  nframe++;
  if (t_overturn >= 0. && t > t_overturn + TAIL)
    return 1;
  return 0;
}

/** 途中の状態の保存（output の後に置く。同じ時刻のコマを書いた後の状態を保存する） */
event checkpoint (t = CKPT; t <= TEND; t += CKPT)
{
  char rf[600], tmp[600], sf[600];
  sprintf (rf, "%s/restart", OUTDIR);
  sprintf (tmp, "%s/restart.tmp", OUTDIR);
  sprintf (sf, "%s/restart.state", OUTDIR);
  dump (file = tmp);
  if (pid() == 0) {
    rename (tmp, rf);
    FILE * fp = fopen (sf, "w");
    fprintf (fp, "%d %.17g %.17g %.17g %.17g\n", nframe, xcrest, ycrest, t_overturn, t_dense);
    fclose (fp);
    char af[600];
    sprintf (af, "%s/restart.args", OUTDIR);
    fp = fopen (af, "w");
    fprintf (fp, "%s\n", ARGS);
    fclose (fp);
  }
}

event stop (t = TEND)
{
  return 1;
}
