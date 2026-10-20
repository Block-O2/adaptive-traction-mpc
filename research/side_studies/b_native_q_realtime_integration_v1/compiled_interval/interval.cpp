
#include <cmath>
#include <algorithm>
#include <limits>
#include <stdexcept>
static double dn(double x){return std::nextafter(x,-INFINITY);}
static double up(double x){return std::nextafter(x,INFINITY);}
struct I {
 double lo,hi;
 I(double a):lo(a),hi(a){check();}
 I(double a,double b):lo(a),hi(b){check();}
 void check(){if(!(std::isfinite(lo)&&std::isfinite(hi)&&lo<=hi))throw 1;}
 I operator+(I b)const{return I(dn(lo+b.lo),up(hi+b.hi));}
 I operator-()const{return I(-hi,-lo);}
 I operator-(I b)const{return *this+(-b);}
 I operator*(I b)const{double p[]={lo*b.lo,lo*b.hi,hi*b.lo,hi*b.hi};double a=p[0],z=p[0];for(int j=1;j<4;j++){a=std::min(a,p[j]);z=std::max(z,p[j]);}return I(dn(a),up(z));}
 I abs()const{return I(lo<=0.&&0.<=hi?0.:std::min(std::fabs(lo),std::fabs(hi)),std::max(std::fabs(lo),std::fabs(hi)));}
};
static I minimum(I a,I b){return I(std::min(a.lo,b.lo),std::min(a.hi,b.hi));}
static I sqrtn(I a){return I(std::max(0.,dn(std::sqrt(std::max(0.,a.lo)))),up(std::sqrt(std::max(0.,a.hi))));}
static I trig(I x,bool cosine,const double*t){
 if(x.abs().hi>4.)throw 1;
 const double*c=t+(cosine?36:0);I square=x*x;I value(c[34],c[35]);
 for(int j=16;j>=0;j--)value=I(c[2*j],c[2*j+1])+square*value;
 if(!cosine)value=x*value;double rem=t[cosine?73:72];value=value+I(-rem,rem);
 return I(std::max(-1.,value.lo),std::min(1.,value.hi));
}
static void endpoint(const double*v,const double*t,I q0,I q1,I*out){
 I shank=trig(q0-q1,false,t),radial=trig(q0-q1,true,t);
 I knee=I(v[17])+I(v[18])+I(v[14])*trig(q0,false,t);
 I cuff=knee+I(v[15])*shank+I(v[19]);
 out[0]=I(v[20]);
 out[1]=minimum(knee,knee+I(v[16])*shank)-I(v[25])-I(v[26])-I(v[21]);
 I sr=sqrtn(I(1.)-shank*shank);
 out[2]=cuff-I(v[23])*shank.abs()-I(v[24])*sr-I(v[26]);
 out[3]=cuff-I(.5*v[27])*shank.abs()-I(v[28])*sr-I(v[26]);
 out[4]=minimum(cuff+I(v[22])*radial,cuff+I(v[24])*radial)-I(.018)*sqrtn(I(1.)-radial*radial)-I(v[26]);
}
static double hypotup(double a,double b){I square=I(a)*I(a)+I(b)*I(b);return up(std::sqrt(square.hi));}
extern "C" int certificate(const double*v,const double*t,double*out){
 try{
 I q0[]={I(v[0]),I(v[6])},delta[]={I(v[12]),I(v[13])};
 I q1[]={q0[0]+delta[0],q0[1]+delta[1]};
 double canonical[]={0.,0.,0.,10.,-15.,6.};
 I residual[2][6]={{I(0.),I(0.),I(0.),I(0.),I(0.),I(0.)},{I(0.),I(0.),I(0.),I(0.),I(0.),I(0.)}};
 for(int j=0;j<2;j++)for(int k=0;k<6;k++)residual[j][k]=I(v[j*6+k])-(k==0?q0[j]:delta[j]*I(canonical[k]));
 I e1i(0.),ephii(0.);for(int k=0;k<6;k++){e1i=e1i+residual[0][k].abs();ephii=ephii+(residual[0][k]-residual[1][k]).abs();}
 double e1=e1i.hi,ephi=ephii.hi;
 if(std::max(e1,ephi)>1e-10)return 0;
 double lo=std::min(q0[0].lo,q1[0].lo),hi=std::max(q0[0].hi,q1[0].hi);
 if(lo<0.||hi>v[29])return 0;
 if(std::max((q0[0]-q0[1]).abs().hi,(q1[0]-q1[1]).abs().hi)>4.)return 0;
 double coslo=trig(I(hi),true,t).lo,coshi=trig(I(lo),true,t).hi;
 I k=I(v[14])*delta[0]*I(coslo,coshi),dphi=(delta[0]-delta[1]).abs();
 I radii[]={I(v[16]),I(v[15])+I(hypotup(v[23],v[24])),I(v[15])+I(hypotup(.5*v[27],v[28])),I(v[15])+I(v[22])+I(.018)};
 I ends[2][5]={{I(0.),I(0.),I(0.),I(0.),I(0.)},{I(0.),I(0.),I(0.),I(0.),I(0.)}};
 endpoint(v,t,q0[0],q0[1],ends[0]);endpoint(v,t,q1[0],q1[1],ends[1]);
 out[0]=1.;out[1]=e1;out[2]=ephi;out[3]=k.lo;out[4]=k.hi;out[5]=dphi.lo;out[6]=dphi.hi;
 for(int b=0;b<4;b++){
  I rd=radii[b]*dphi;I derivative(k.lo-rd.hi,k.hi+rd.hi);derivative=I(dn(derivative.lo),up(derivative.hi));
  int which=derivative.lo>=0.?0:(derivative.hi<=0.?1:-1);
  I loss=I(v[14])*I(e1)+radii[b]*I(ephi);int a=7+b*8;
  out[a]=derivative.lo;out[a+1]=derivative.hi;out[a+2]=radii[b].hi;out[a+3]=which;out[a+4]=loss.hi;
  if(which>=0){out[a+5]=ends[which][b+1].lo;out[a+6]=ends[which][b+1].hi;out[a+7]=(ends[which][b+1]-loss).lo;}
 }
 out[39]=(I(lo)-I(e1)).lo>=0.&&(I(hi)+I(e1)).hi<=v[29]?1.:0.;return 1;
 }catch(...){return -1;}
}
