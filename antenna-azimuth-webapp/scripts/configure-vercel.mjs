import fs from 'node:fs';
const token=process.env.VERCEL_DEPLOY_TOKEN;if(!token)throw Error('Vercel deployment token missing');
const host='antenna-azimuth-webapp-sigma.vercel.app';
async function request(path,method='GET',body){const r=await fetch('https://api.vercel.com'+path,{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(20000)});const d=await r.json();return {status:r.status,data:d};}
let scopes=[null,process.env.VERCEL_ORG_ID];const teams=await request('/v2/teams');if(teams.status===200)scopes.push(...teams.data.teams.map(x=>x.id));scopes=[...new Set(scopes.filter(x=>x===null||x))];
let target;
for(const scope of scopes){const q=scope?'?teamId='+encodeURIComponent(scope):'';const a=await request('/v4/aliases/'+host+q);console.log(JSON.stringify({scope:scope||'personal',aliasStatus:a.status,errorCode:a.data.error?.code}));if(a.status===200&&a.data.alias===host&&a.data.projectId){const p=await request('/v9/projects/'+a.data.projectId+q);if(p.status===200){target={scope,project:p.data};break;}}}
if(!target)throw Error('The authorized token cannot access the project serving '+host);
const {project,scope}=target;console.log(JSON.stringify({target:host,project:project.name,projectId:project.id,accountId:project.accountId,nodeVersion:project.nodeVersion,rootDirectory:project.rootDirectory}));
const q=scope?'?teamId='+encodeURIComponent(scope):'';
if(project.nodeVersion!=='24.x'){const p=await request('/v9/projects/'+project.id+q,'PATCH',{nodeVersion:'24.x'});if(p.status!==200)throw Error('Runtime update failed: HTTP '+p.status+' '+p.data.error?.code);}
const env=['NEXT_PUBLIC_SUPABASE_URL','NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY'].map(key=>({key,value:process.env[key],type:'plain',target:['production']}));if(env.some(x=>!x.value))throw Error('Publishable database configuration missing');
const p=await request('/v10/projects/'+project.id+'/env?upsert=true'+(scope?'&teamId='+encodeURIComponent(scope):''),'POST',env);if(p.status!==200&&p.status!==201)throw Error('Environment update failed: HTTP '+p.status+' '+p.data.error?.code);
fs.appendFileSync(process.env.GITHUB_ENV,'VERCEL_ORG_ID='+project.accountId+'\nVERCEL_PROJECT_ID='+project.id+'\n');console.log('Existing project verified; runtime and production database configured');
