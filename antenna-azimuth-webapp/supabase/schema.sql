-- Applied schema snapshot via Supabase API; not a CLI-generated migration.
-- Only new azimuth-prefixed objects. Review existing policies before deployment.
begin;
create table public.azimuth_projects (
 id uuid primary key, owner_id uuid not null references auth.users(id) on delete cascade,
 name text not null check (char_length(btrim(name)) between 1 and 160),
 site_code text not null default '' check(char_length(site_code)<=100),
 latitude double precision check(latitude between -85 and 85),
 longitude double precision check(longitude between -180 and 180),
 revision bigint not null check(revision between 1 and 9007199254740991),
 updated_at timestamptz not null default now(),
 check((latitude is null) = (longitude is null))
);
create index azimuth_projects_owner_updated on public.azimuth_projects(owner_id,updated_at desc);
create table public.azimuth_project_sectors (
 project_id uuid not null references public.azimuth_projects(id) on delete cascade,
 id uuid not null, position integer not null check(position between 0 and 299),
 name text not null check(char_length(btrim(name)) between 1 and 160),
 azimuth_deg double precision not null check(azimuth_deg>=0 and azimuth_deg<360),
 mechanical_tilt_deg double precision check(mechanical_tilt_deg between -90 and 90),
 electrical_tilt_deg double precision check(electrical_tilt_deg between -90 and 90),
 source_page integer check(source_page between 1 and 10000),
 source_text text not null default '' check(char_length(source_text)<=100000),
 warnings jsonb not null default '[]' check(jsonb_typeof(warnings)='array' and jsonb_array_length(warnings)<=100),
 completed_at timestamptz check(completed_at is null or isfinite(completed_at)),
 primary key(project_id,id), unique(project_id,position)
);
create table public.azimuth_project_documents (
 project_id uuid primary key references public.azimuth_projects(id) on delete cascade,
 name text not null check(char_length(btrim(name)) between 1 and 255),
 path text not null unique, sha256 text not null check(sha256 ~ '^[a-f0-9]{64}$')
);
create table public.azimuth_project_revisions (
 project_id uuid not null references public.azimuth_projects(id) on delete cascade,
 revision bigint not null check(revision between 1 and 9007199254740991),
 snapshot jsonb not null check(jsonb_typeof(snapshot)='object'),
 created_at timestamptz not null default now(),
 primary key(project_id,revision)
);
alter table public.azimuth_projects enable row level security;
alter table public.azimuth_project_sectors enable row level security;
alter table public.azimuth_project_documents enable row level security;
alter table public.azimuth_project_revisions enable row level security;
revoke all on public.azimuth_projects,public.azimuth_project_sectors,public.azimuth_project_documents,public.azimuth_project_revisions from public,anon,authenticated;
grant select,insert,update on public.azimuth_projects to authenticated;
grant select,insert,delete on public.azimuth_project_sectors to authenticated;
grant select,insert,update,delete on public.azimuth_project_documents to authenticated;
grant select,insert on public.azimuth_project_revisions to authenticated;
create policy azimuth_projects_read on public.azimuth_projects for select to authenticated
 using(owner_id=(select auth.uid()) and not coalesce((select auth.jwt())->>'is_anonymous','false')::boolean);
create policy azimuth_projects_insert on public.azimuth_projects for insert to authenticated
 with check(owner_id=(select auth.uid()) and not coalesce((select auth.jwt())->>'is_anonymous','false')::boolean);
create policy azimuth_projects_update on public.azimuth_projects for update to authenticated
 using(owner_id=(select auth.uid()) and not coalesce((select auth.jwt())->>'is_anonymous','false')::boolean)
 with check(owner_id=(select auth.uid()) and not coalesce((select auth.jwt())->>'is_anonymous','false')::boolean);
create policy azimuth_sectors_read on public.azimuth_project_sectors for select to authenticated
 using(exists(select 1 from public.azimuth_projects p where p.id=project_id and p.owner_id=(select auth.uid())));
create policy azimuth_sectors_insert on public.azimuth_project_sectors for insert to authenticated
 with check(exists(select 1 from public.azimuth_projects p where p.id=project_id and p.owner_id=(select auth.uid())));
create policy azimuth_sectors_delete on public.azimuth_project_sectors for delete to authenticated
 using(exists(select 1 from public.azimuth_projects p where p.id=project_id and p.owner_id=(select auth.uid())));
create policy azimuth_documents_read on public.azimuth_project_documents for select to authenticated
 using(exists(select 1 from public.azimuth_projects p where p.id=project_id and p.owner_id=(select auth.uid())));
create policy azimuth_documents_insert on public.azimuth_project_documents for insert to authenticated
 with check(exists(select 1 from public.azimuth_projects p where p.id=project_id and p.owner_id=(select auth.uid())) and path like (select auth.uid())::text||'/'||project_id::text||'/%');
create policy azimuth_documents_update on public.azimuth_project_documents for update to authenticated
 using(exists(select 1 from public.azimuth_projects p where p.id=project_id and p.owner_id=(select auth.uid())))
 with check(exists(select 1 from public.azimuth_projects p where p.id=project_id and p.owner_id=(select auth.uid())) and path like (select auth.uid())::text||'/'||project_id::text||'/%');
create policy azimuth_documents_delete on public.azimuth_project_documents for delete to authenticated
 using(exists(select 1 from public.azimuth_projects p where p.id=project_id and p.owner_id=(select auth.uid())));
create policy azimuth_revisions_read on public.azimuth_project_revisions for select to authenticated
 using(exists(select 1 from public.azimuth_projects p where p.id=project_id and p.owner_id=(select auth.uid())));
create policy azimuth_revisions_insert on public.azimuth_project_revisions for insert to authenticated
 with check(exists(select 1 from public.azimuth_projects p where p.id=project_id and p.owner_id=(select auth.uid())));

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
 values('azimuth-assignments','azimuth-assignments',false,20971520,array['application/pdf']);
create policy azimuth_pdf_read on storage.objects for select to authenticated using(
 bucket_id='azimuth-assignments' and (storage.foldername(name))[1]=(select auth.uid())::text
 and not coalesce((select auth.jwt())->>'is_anonymous','false')::boolean);
create policy azimuth_pdf_upload on storage.objects for insert to authenticated with check(
 bucket_id='azimuth-assignments' and name ~ ('^'||(select auth.uid())::text||'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.pdf$')
 and not coalesce((select auth.jwt())->>'is_anonymous','false')::boolean);
create policy azimuth_pdf_cleanup on storage.objects for delete to authenticated using(
 bucket_id='azimuth-assignments' and (storage.foldername(name))[1]=(select auth.uid())::text
 and not coalesce((select auth.jwt())->>'is_anonymous','false')::boolean
 and not exists(select 1 from public.azimuth_project_documents d where d.path=storage.objects.name)
 and not exists(select 1 from public.azimuth_project_revisions r where r.snapshot->'document'->>'path'=storage.objects.name));

create function public.save_azimuth_project(p_project jsonb,p_expected_revision bigint)
returns jsonb language plpgsql security invoker set search_path='' as $function$
declare
 uid uuid := auth.uid();
 pid uuid;
 saved public.azimuth_projects%rowtype;
 sector jsonb;
 doc jsonb;
 result jsonb;
 sector_position integer := 0;
begin
 if uid is null or coalesce(auth.jwt()->>'is_anonymous','false')::boolean then
   raise exception 'Přihlášení je vyžadováno.' using errcode='42501';
 end if;
 if p_project is null or jsonb_typeof(p_project)<>'object' or octet_length(p_project::text)>4194304 then
   raise exception 'Neplatná nebo příliš velká data projektu.' using errcode='22023';
 end if;
 if p_expected_revision is null or p_expected_revision<0 or p_expected_revision>=9007199254740991 or
   (p_project->>'revision')::bigint is distinct from p_expected_revision then
   raise exception 'Neplatná revize projektu.' using errcode='22023';
 end if;
 pid := (p_project->>'id')::uuid;
 if pid is null or jsonb_typeof(p_project->'name') is distinct from 'string' or jsonb_typeof(p_project->'siteCode') is distinct from 'string' or
   jsonb_typeof(p_project->'sectors') is distinct from 'array' or jsonb_array_length(p_project->'sectors') not between 1 and 300 then
   raise exception 'Neplatný název, kód nebo sektory projektu.' using errcode='22023';
 end if;
 if p_expected_revision=0 then
   insert into public.azimuth_projects(id,owner_id,name,site_code,latitude,longitude,revision)
    values(pid,uid,p_project->>'name',p_project->>'siteCode',(p_project->>'latitude')::double precision,(p_project->>'longitude')::double precision,1)
    on conflict(id) do nothing returning * into saved;
 else
   update public.azimuth_projects set name=p_project->>'name',site_code=p_project->>'siteCode',
    latitude=(p_project->>'latitude')::double precision,longitude=(p_project->>'longitude')::double precision,
    revision=revision+1,updated_at=clock_timestamp()
    where id=pid and owner_id=uid and revision=p_expected_revision returning * into saved;
 end if;
 if saved.id is null then raise exception 'Projekt změnilo jiné zařízení. Obnov seznam.' using errcode='PT409'; end if;
 delete from public.azimuth_project_sectors where project_id=pid;
 for sector in select value from jsonb_array_elements(p_project->'sectors') loop
   if jsonb_typeof(sector)<>'object' or jsonb_typeof(sector->'name') is distinct from 'string' or
      jsonb_typeof(sector->'sourceText') is distinct from 'string' or jsonb_typeof(sector->'warnings') is distinct from 'array' or
      jsonb_array_length(sector->'warnings')>100 or exists(
       select 1 from jsonb_array_elements(sector->'warnings') w where jsonb_typeof(w.value)<>'string' or char_length(w.value#>>'{}')>2000) then
     raise exception 'Neplatný sektor nebo původní text.' using errcode='22023';
   end if;
   insert into public.azimuth_project_sectors(project_id,id,position,name,azimuth_deg,mechanical_tilt_deg,electrical_tilt_deg,source_page,source_text,warnings,completed_at)
    values(pid,(sector->>'id')::uuid,sector_position,sector->>'name',(sector->>'azimuthDeg')::double precision,
     (sector->>'mechanicalTiltDeg')::double precision,(sector->>'electricalTiltDeg')::double precision,
     (sector->>'sourcePage')::integer,sector->>'sourceText',sector->'warnings',(sector->>'completedAt')::timestamptz);
   sector_position := sector_position+1;
 end loop;
 doc := p_project->'document';
 if doc is null or doc='null'::jsonb then
   delete from public.azimuth_project_documents where project_id=pid;
 else
   if jsonb_typeof(doc)<>'object' or jsonb_typeof(doc->'name') is distinct from 'string' or
      (doc->>'path') is null or (doc->>'path') !~ ('^'||uid::text||'/'||pid::text||'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.pdf$') or
      not exists(select 1 from storage.objects o where o.bucket_id='azimuth-assignments' and o.name=doc->>'path') then
     raise exception 'Původní PDF není platné nebo není uložené.' using errcode='22023';
   end if;
   insert into public.azimuth_project_documents(project_id,name,path,sha256)
    values(pid,doc->>'name',doc->>'path',doc->>'sha256')
    on conflict(project_id) do update set name=excluded.name,path=excluded.path,sha256=excluded.sha256;
 end if;
 select jsonb_build_object('id',saved.id,'name',saved.name,'siteCode',saved.site_code,'latitude',saved.latitude,'longitude',saved.longitude,
   'revision',saved.revision,'updatedAt',saved.updated_at,'sectors',coalesce((
     select jsonb_agg(jsonb_build_object('id',s.id,'name',s.name,'azimuthDeg',s.azimuth_deg,'mechanicalTiltDeg',s.mechanical_tilt_deg,
       'electricalTiltDeg',s.electrical_tilt_deg,'sourcePage',s.source_page,'sourceText',s.source_text,'warnings',s.warnings,'completedAt',s.completed_at) order by s.position)
     from public.azimuth_project_sectors s where s.project_id=pid),'[]'::jsonb),
   'document',(select jsonb_build_object('name',d.name,'path',d.path,'sha256',d.sha256) from public.azimuth_project_documents d where d.project_id=pid)) into result;
 insert into public.azimuth_project_revisions(project_id,revision,snapshot) values(pid,saved.revision,result);
 return result;
end
$function$;
revoke all on function public.save_azimuth_project(jsonb,bigint) from public,anon;
grant execute on function public.save_azimuth_project(jsonb,bigint) to authenticated;
commit;
