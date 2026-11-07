"use client";
import { getSupabaseClient } from "./supabase-client";
import { validateProject, type MountingProject, type ProjectSector } from "./projects";

const BUCKET = "azimuth-assignments";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export class ProjectStoreError extends Error {
  constructor(public code: string, message: string) { super(message); this.name = "ProjectStoreError"; }
}
async function context() {
  const client = getSupabaseClient();
  if (!client) throw new ProjectStoreError("CONFIGURATION", "Synchronizace není nakonfigurovaná.");
  const { data, error } = await client.auth.getUser();
  if (error || !data.user || data.user.is_anonymous) throw new ProjectStoreError("AUTH", "Pro práci s projekty se přihlas.");
  return { client, userId: data.user.id };
}
function validPath(path: string, uid: string, projectId?: string) {
  const parts = path.split("/");
  return parts.length === 3 && parts[0] === uid && UUID.test(parts[1]) &&
    (!projectId || parts[1] === projectId) && UUID.test(parts[2].replace(/\.pdf$/, "")) && parts[2].endsWith(".pdf");
}
function validate(project: MountingProject, uid: string) {
  const errors = validateProject(project);
  if (!UUID.test(project.id) || !Number.isSafeInteger(project.revision) || project.revision < 0) errors.push("Neplatný identifikátor nebo revize projektu.");
  if (!project.name.trim() || project.name.length > 160 || project.siteCode.length > 100) errors.push("Název projektu nebo kód lokality je příliš dlouhý.");
  if (project.sectors.length > 300 || new Set(project.sectors.map(s => s.id)).size !== project.sectors.length) errors.push("Neplatný počet či opakované identifikátory sektorů.");
  for (const sector of project.sectors) {
    if (!UUID.test(sector.id) || !sector.name.trim() || sector.name.length > 160 || sector.sourceText.length > 100000 ||
      sector.warnings.length > 100 || sector.warnings.some(w => w.length > 2000) ||
      (sector.sourcePage !== null && (!Number.isInteger(sector.sourcePage) || sector.sourcePage < 1 || sector.sourcePage > 10000)) ||
      (sector.completedAt != null && !Number.isFinite(Date.parse(sector.completedAt)))) errors.push("Neplatná data sektoru " + sector.name + ".");
  }
  if (project.document && (!validPath(project.document.path, uid, project.id) || !/^[a-f0-9]{64}$/.test(project.document.sha256) ||
    !project.document.name.trim() || project.document.name.length > 255)) errors.push("Neplatný odkaz na původní PDF.");
  if (new TextEncoder().encode(JSON.stringify(project)).byteLength > 4*1024*1024) errors.push("Projekt překračuje limit 4 MB textových dat.");
  if (errors.length) throw new ProjectStoreError("VALIDATION", errors.join(" "));
}
type SectorRow = {
 id:string; name:string; azimuth_deg:number|null; mechanical_tilt_deg:number|null; electrical_tilt_deg:number|null;
 source_page:number|null; source_text:string; warnings:string[]; position:number; completed_at:string|null;
};
type ProjectRow = {
 id:string; name:string; site_code:string; latitude:number|null; longitude:number|null; revision:number; updated_at:string;
 azimuth_project_sectors:SectorRow[];
 azimuth_project_documents:{name:string;path:string;sha256:string}[]|{name:string;path:string;sha256:string}|null;
};
function fromRow(row: ProjectRow): MountingProject {
 const sectors: ProjectSector[] = [...row.azimuth_project_sectors].sort((a,b)=>a.position-b.position).map(s=>({
   id:s.id,name:s.name,azimuthDeg:s.azimuth_deg,mechanicalTiltDeg:s.mechanical_tilt_deg,electricalTiltDeg:s.electrical_tilt_deg,
   sourcePage:s.source_page,sourceText:s.source_text,warnings:s.warnings,completedAt:s.completed_at
 }));
 const document = Array.isArray(row.azimuth_project_documents) ? row.azimuth_project_documents[0] ?? null : row.azimuth_project_documents;
 return {id:row.id,name:row.name,siteCode:row.site_code,latitude:row.latitude,longitude:row.longitude,sectors,document,revision:row.revision,updatedAt:row.updated_at};
}
export async function listProjects(): Promise<MountingProject[]> {
 const {client,userId} = await context();
 const results: MountingProject[] = [];
 for (let offset=0;;offset+=100) {
   const {data,error} = await client.from("azimuth_projects").select("id,name,site_code,latitude,longitude,revision,updated_at,azimuth_project_sectors(id,name,azimuth_deg,mechanical_tilt_deg,electrical_tilt_deg,source_page,source_text,warnings,position,completed_at),azimuth_project_documents(name,path,sha256)")
     .order("updated_at",{ascending:false}).order("id").range(offset,offset+99);
   if(error) throw new ProjectStoreError("REMOTE","Projekty se nepodařilo načíst. " + error.message);
   const rows = (data ?? []) as unknown as ProjectRow[];
   for(const row of rows) { const project = fromRow(row); validate(project,userId); results.push(project); }
   if(rows.length<100) return results;
 }
}
export async function saveProject(project: MountingProject, pdfFile?: File): Promise<MountingProject> {
 const {client,userId} = await context();
 validate(project,userId);
 let uploaded: string | null = null;
 let document = project.document;
 if(pdfFile) {
   if(pdfFile.size===0 || pdfFile.size>20*1024*1024 || pdfFile.name.length>255) throw new ProjectStoreError("VALIDATION","PDF musí mít nejvýše 20 MB a platný název.");
   const bytes = await pdfFile.arrayBuffer();
   if(!new TextDecoder("latin1").decode(bytes.slice(0,1024)).includes("%PDF-")) throw new ProjectStoreError("VALIDATION","Soubor není rozpoznané PDF.");
   const digest = await crypto.subtle.digest("SHA-256",bytes);
   const sha256 = Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,"0")).join("");
   const path = userId+"/"+project.id+"/"+crypto.randomUUID()+".pdf";
   const {error} = await client.storage.from(BUCKET).upload(path,new Blob([bytes],{type:"application/pdf"}),{upsert:false,contentType:"application/pdf"});
   if(error) throw new ProjectStoreError("REMOTE","Původní PDF se nepodařilo uložit. " + error.message);
   uploaded=path; document={name:pdfFile.name,path,sha256};
 }
 const controller = new AbortController();
 const timeout = setTimeout(() => controller.abort(), 30000);
 let response;
 try { response = await client.rpc("save_azimuth_project",{p_project:{...project,document},p_expected_revision:project.revision}).retry(false).abortSignal(controller.signal); }
 catch { throw new ProjectStoreError("SAVE_UNCERTAIN","Spojení při ukládání vypadlo. Obnov seznam projektů před dalším pokusem; PDF mohlo být uloženo."); }
 finally { clearTimeout(timeout); }
 if(response.error) {
   const definitive = /^(?:[0-9A-Z]{5}|PGRST[0-9]+)$/.test(response.error.code ?? "");
   if(!definitive) throw new ProjectStoreError("SAVE_UNCERTAIN","Výsledek uložení není potvrzený. Obnov seznam projektů před dalším pokusem.");
   if(uploaded) {
     const cleanup = await client.storage.from(BUCKET).remove([uploaded]).catch(()=>({error:true}));
     if(cleanup.error) throw new ProjectStoreError("STORAGE_ORPHAN","Projekt nebyl uložen a nepodařilo se odstranit nové PDF: "+uploaded+". Obnov projekty a prověř tento soubor.");
   }
   if(["PT409","40001","23505"].includes(response.error.code)) throw new ProjectStoreError("CONFLICT","Projekt mezitím změnilo jiné zařízení. Obnov seznam a znovu zkontroluj své změny.");
   throw new ProjectStoreError("REMOTE","Projekt se nepodařilo uložit. "+response.error.message);
 }
 const saved = response.data as MountingProject;
 try { validate(saved,userId); } catch { throw new ProjectStoreError("SAVE_UNCERTAIN","Server vrátil neplatné potvrzení. Obnov seznam projektů; uložení mohlo proběhnout."); }
 return saved;
}
export async function getDocumentUrl(path:string):Promise<string> {
 const {client,userId}=await context();
 if(!validPath(path,userId)) throw new ProjectStoreError("VALIDATION","Neplatný odkaz na PDF.");
 const {data,error}=await client.storage.from(BUCKET).createSignedUrl(path,60);
 if(error || !data) throw new ProjectStoreError("REMOTE","PDF se nepodařilo otevřít.");
 return data.signedUrl;
}
