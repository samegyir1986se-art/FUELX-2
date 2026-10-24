'use strict';
// FUELX ENERGY GHANA LIMITED - station management backend. No npm packages needed (Node 18+).
const http=require('http'),fs=require('fs'),path=require('path'),crypto=require('crypto');
const PORT=process.env.PORT||3000,DIR=process.env.DATA_DIR||path.join(__dirname,'data'),FILE=path.join(DIR,'db.json');
const STN=['Kasoa','Asumura','Tagina','Hiayeya','Nyamebekyere','Kobro','Appiankwanta'];
const RN={ceo:'Chief Executive Officer',ops:'Operations Head',acc:'Accountant',mgr:'Station Manager'};
const MAP={staff:'staff',st:'stations',sales:'sales',deliv:'deliveries',dips:'dips',exp:'expenses',bank:'banking',log:'audit',cfg:'config'};
// who may add / delete in each collection (enforced here, on the server)
const RULE={sales:{add:'mgr ops ceo',del:'ceo',sc:1},deliveries:{add:'mgr ops ceo',del:'ceo',sc:1},dips:{add:'mgr ops ceo',del:'ceo',sc:1},
expenses:{add:'mgr acc ceo',del:'ceo acc',sc:1},banking:{add:'mgr acc ceo',del:'ceo',sc:1},stations:{add:'ops ceo',del:'',sc:1},config:{add:'ops ceo',del:''},audit:{add:'mgr ops acc ceo',del:''}};
const FIELDS={deliveries:'st date pr l sup inv cpl',dips:'st pr date dip v',expenses:'st date cat desc amt',banking:'st date amt ref',stations:'tanks meters',config:'Petrol Diesel'};
fs.mkdirSync(DIR,{recursive:true});
let DB={users:{},docs:{},sessions:{},fails:{},ver:1};
try{DB=Object.assign(DB,JSON.parse(fs.readFileSync(FILE,'utf8')))}catch(e){}
Object.values(MAP).forEach(c=>{if(c!='staff')DB.docs[c]=DB.docs[c]||{}});
try{if(fs.existsSync(FILE)){const b=path.join(DIR,'backup-'+new Date().toISOString().slice(0,10)+'.json');if(!fs.existsSync(b))fs.copyFileSync(FILE,b)}}catch(e){}
const save=()=>{DB.ver++;const t=FILE+'.tmp';fs.writeFileSync(t,JSON.stringify(DB));fs.renameSync(t,FILE)};
const hash=(pw,salt)=>crypto.scryptSync(pw,salt,32).toString('hex'),sha=s=>crypto.createHash('sha256').update(s).digest('hex'),rid=()=>crypto.randomBytes(8).toString('hex');
const eq=(a,b)=>{a=Buffer.from(a);b=Buffer.from(b);return a.length==b.length&&crypto.timingSafeEqual(a,b)};
const pub=u=>({id:u.id,username:u.username,name:u.name,phone:u.phone,role:u.role,station:u.station,status:u.status,created:u.created});
const send=(res,c,o)=>{res.writeHead(c,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(o))};
const num=x=>{x=Number(x);return Number.isFinite(x)?x:0},str=x=>String(x==null?'':x).slice(0,200),DATE=/^\d{4}-\d\d-\d\d$/;
function auth(req){const t=(req.headers.authorization||'').slice(7);if(!t)return null;const s=DB.sessions[sha(t)];if(!s||s.exp<Date.now())return null;const u=DB.users[s.uid];return u&&u.status=='active'?u:null}
function kill(uid){Object.keys(DB.sessions).forEach(k=>{if(DB.sessions[k].uid==uid)delete DB.sessions[k]})}
function body(req){return new Promise((ok,no)=>{let b='';req.on('data',d=>{b+=d;if(b.length>2e5){req.destroy();no()}});req.on('end',()=>{try{ok(b?JSON.parse(b):{})}catch(e){ok({})}})})}
const okRole=(l,U)=>l.split(' ').includes(U.role);
function sales(o,U,id){ // server recalculates every figure so clients cannot fake totals
 if(!STN.includes(o.st)||!DATE.test(o.date)||id!=o.st+'_'+o.date)return'Invalid station or date';
 const pr=DB.docs.config.prices;if(!pr||!pr.Petrol?.sell||!pr.Diesel?.sell)return'Fuel prices are not set';
 if(!Array.isArray(o.lines)||o.lines.length!=4)return'Four pump readings are required';
 const L={Petrol:0,Diesel:0};let v=0,cg=0;const lines=[];
 for(const x of o.lines){const p=['P1','P2','P3'].concat('P4').includes(x.p)?x.p:null,r=['P1','P2'].includes(p)?'Petrol':'Diesel',op=num(x.o),c=num(x.c);if(!p||c<op)return'Bad meter reading for '+x.p;const l=c-op;lines.push({p,pr:r,o:op,c,l});L[r]+=l;v+=l*pr[r].sell;cg+=l*pr[r].cost}
 const pay={};['cash','momo','card','credit'].forEach(k=>pay[k]=Math.max(0,num(o.pay&&o.pay[k])));const col=pay.cash+pay.momo+pay.card+pay.credit;
 return{st:o.st,date:o.date,lines,L,sales:v,cogs:cg,pay,collected:col,diff:col-v,verified:false}}
const server=http.createServer(async(req,res)=>{try{
 const u=new URL(req.url,'http://x'),p=u.pathname,m=req.method;
 res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('X-Frame-Options','DENY');
 if(!p.startsWith('/api/')){if(p=='/'||p=='/index.html'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-cache'});return res.end(fs.readFileSync(path.join(__dirname,'public','index.html')))}res.writeHead(404);return res.end('Not found')}
 if(m=='GET'&&p=='/api/status')return send(res,200,{first:!Object.keys(DB.users).length});
 const b=m=='GET'?{}:await body(req);
 if(m=='POST'&&p=='/api/register'){const un=str(b.username).toLowerCase().trim(),pw=String(b.password||'');
  if(!/^[a-z0-9._-]{3,30}$/.test(un))return send(res,400,{error:'Username: 3-30 letters, numbers, . _ -'});
  if(pw.length<4||pw.length>64)return send(res,400,{error:'PIN / password must be 4-64 characters'});
  if(!str(b.name).trim())return send(res,400,{error:'Enter your full name'});
  if(Object.values(DB.users).some(x=>x.username==un))return send(res,409,{error:'That username is taken'});
  const first=!Object.keys(DB.users).length,role=first?'ceo':b.role;if(!RN[role]||role=='ceo'&&!first)return send(res,400,{error:'Choose a valid role'});
  if(role=='mgr'&&!STN.includes(b.station))return send(res,400,{error:'Choose your station'});
  const salt=rid(),id=rid();DB.users[id]={id,username:un,name:str(b.name).trim(),phone:str(b.phone),role,station:role=='mgr'?b.station:'',status:first?'active':'pending',salt,hash:hash(pw,salt),created:Date.now()};save();
  return send(res,200,{ok:1,status:DB.users[id].status})}
 if(m=='POST'&&p=='/api/login'){const un=str(b.username).toLowerCase().trim(),f=DB.fails[un]||{n:0,t:0},user=Object.values(DB.users).find(x=>x.username==un);
  if(f.t>Date.now())return send(res,429,{error:'Too many wrong attempts. Try again in a few minutes.'});
  if(!user||!eq(user.hash,hash(String(b.password||''),user.salt))){DB.fails[un]={n:f.n+1,t:f.n+1>=5?Date.now()+6e5:0};if(DB.fails[un].t)DB.fails[un].n=0;return send(res,401,{error:'Wrong username or PIN / password'})}
  if(user.status!='active')return send(res,403,{error:user.status=='pending'?'Your account is waiting for CEO approval':'Your account is suspended. Contact the CEO.'});
  delete DB.fails[un];const tok=crypto.randomBytes(32).toString('hex');DB.sessions[sha(tok)]={uid:user.id,exp:Date.now()+12*36e5};save();return send(res,200,{token:tok,user:pub(user)})}
 const U=auth(req);if(!U)return send(res,401,{error:'Please log in'});
 if(m=='POST'&&p=='/api/logout'){delete DB.sessions[sha((req.headers.authorization||'').slice(7))];save();return send(res,200,{ok:1})}
 if(m=='GET'&&p=='/api/me')return send(res,200,{user:pub(U)});
 if(m=='POST'&&p=='/api/password'){if(!eq(U.hash,hash(String(b.old||''),U.salt)))return send(res,403,{error:'Current PIN is wrong'});const n=String(b.pw||'');if(n.length<4||n.length>64)return send(res,400,{error:'New PIN must be 4-64 characters'});U.salt=rid();U.hash=hash(n,U.salt);save();return send(res,200,{ok:1})}
 if(m=='GET'&&p=='/api/data'){const v=+u.searchParams.get('v');if(v==DB.ver)return send(res,200,{same:1,v});const o={v:DB.ver};
  for(const[k,c]of Object.entries(MAP)){let a;if(c=='staff')a=U.role=='ceo'?Object.values(DB.users).map(pub):[pub(U)];else if(c=='audit'&&!['ceo','ops'].includes(U.role))a=[];else a=Object.entries(DB.docs[c]).map(([id,d])=>Object.assign({id},d));
   if(U.role=='mgr'&&RULE[c]&&RULE[c].sc)a=a.filter(d=>(c=='stations'?d.id:d.st)==U.station);o[k]=a}return send(res,200,o)}
 if(m=='GET'&&p=='/api/backup'){if(U.role!='ceo')return send(res,403,{error:'CEO only'});return send(res,200,{docs:DB.docs,users:Object.values(DB.users).map(pub)})}
 const[,,coll,id,act]=p.split('/');
 if(coll=='staff'){if(U.role!='ceo')return send(res,403,{error:'CEO only'});const T=DB.users[id];if(!T)return send(res,404,{error:'No such user'});
  if(m=='POST'&&act=='reset'){const n=String(b.password||'');if(n.length<4||n.length>64)return send(res,400,{error:'PIN must be 4-64 characters'});T.salt=rid();T.hash=hash(n,T.salt);kill(T.id);save();return send(res,200,{ok:1})}
  if(m=='PATCH'){if(id==U.id)return send(res,400,{error:'You cannot change your own role or status'});if(b.role!==undefined){if(!RN[b.role])return send(res,400,{error:'Bad role'});T.role=b.role}
   if(b.station!==undefined){if(b.station&&!STN.includes(b.station))return send(res,400,{error:'Bad station'});T.station=b.station}
   if(b.status!==undefined){if(!['active','suspended','pending'].includes(b.status))return send(res,400,{error:'Bad status'});T.status=b.status;if(b.status!='active')kill(T.id)}
   if(T.role=='mgr'&&!T.station)T.status='pending';save();return send(res,200,{ok:1})}
  return send(res,405,{error:'Not allowed'})}
 const R=RULE[coll];if(!R)return send(res,404,{error:'Unknown'});const D=DB.docs[coll],stamp=o=>{o.by=U.id;o.byName=U.name+' ('+RN[U.role]+')';o.ts=Date.now();return o};
 if(m=='POST'||m=='PUT'){if(!okRole(R.add,U))return send(res,403,{error:'Your role cannot add this'});let nid=id||rid(),o;
  if(coll=='audit'){D[nid]={ts:Date.now(),u:U.name+' ('+RN[U.role]+')',a:str(b.a)+''};save();return send(res,200,{ok:1})}
  if(m=='PUT'&&!['sales','stations','config'].includes(coll))return send(res,405,{error:'Not allowed'});
  if(R.sc){const st=coll=='stations'?id:b.st;if(!STN.includes(st))return send(res,400,{error:'Invalid station'});if(U.role=='mgr'&&st!=U.station)return send(res,403,{error:'You can only enter data for your own station'})}
  if(coll=='sales'){if(D[id])return send(res,409,{error:'A record for this station and date already exists'});o=sales(b,U,id);if(typeof o=='string')return send(res,400,{error:o})}
  else if(coll=='config'){if(id!='prices')return send(res,400,{error:'Bad id'});o={};['Petrol','Diesel'].forEach(k=>o[k]={sell:Math.max(0,num(b[k]&&b[k].sell)),cost:Math.max(0,num(b[k]&&b[k].cost))})}
  else if(coll=='stations'){o={tanks:{},meters:{}};['Petrol','Diesel'].forEach(k=>o.tanks[k]={cap:Math.max(0,num(b.tanks&&b.tanks[k]&&b.tanks[k].cap)),open:Math.max(0,num(b.tanks&&b.tanks[k]&&b.tanks[k].open))});['P1','P2','P3','P4'].forEach(k=>o.meters[k]=Math.max(0,num(b.meters&&b.meters[k])))}
  else{o={};FIELDS[coll].split(' ').forEach(k=>{const v=b[k];o[k]=['l','cpl','dip','v','amt'].includes(k)?num(v):str(v)});if(!DATE.test(o.date))return send(res,400,{error:'Invalid date'});if(['l','amt'].some(k=>k in o&&o[k]<=0))return send(res,400,{error:'Amount must be above zero'});if(o.pr&&!['Petrol','Diesel'].includes(o.pr))return send(res,400,{error:'Bad product'})}
  D[nid]=stamp(o);save();return send(res,200,{ok:1,id:nid})}
 if(m=='PATCH'&&coll=='sales'&&id){if(!okRole('acc ops ceo',U)||!D[id])return send(res,403,{error:'Not allowed'});D[id].verified=true;D[id].vname=U.name;D[id].vts=Date.now();save();return send(res,200,{ok:1})}
 if(m=='DELETE'&&id){if(!okRole(R.del,U)||!D[id])return send(res,403,{error:'Not allowed'});if(U.role=='acc'&&D[id].by!=U.id)return send(res,403,{error:'You can only delete your own entries'});delete D[id];save();return send(res,200,{ok:1})}
 send(res,405,{error:'Not allowed'})}catch(e){console.error(e);send(res,500,{error:'Server error'})}});
server.listen(PORT,()=>console.log('FUELX server running on port '+PORT));
