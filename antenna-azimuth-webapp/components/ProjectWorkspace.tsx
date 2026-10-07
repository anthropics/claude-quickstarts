"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import type { User } from "@supabase/supabase-js";
import { ArrowLeft, FileText, FolderOpen, Plus, RefreshCw, Trash2 } from "lucide-react";
import { getSupabaseClient } from "@/lib/supabase-client";
import { getDocumentUrl, listProjects, saveProject } from "@/lib/project-store";
import { emptyProject, emptySector, parseDecimal, validateProject, projectIsComplete, type MountingProject, type ProjectSector } from "@/lib/projects";
import { parseAssignmentPages } from "@/lib/pdf-import";
import { readAssignmentPdf } from "@/lib/read-pdf";

const inputClass = "min-h-12 w-full rounded-lg border border-input bg-background px-3 py-2 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
const buttonClass = "inline-flex min-h-12 items-center justify-center gap-2 rounded-lg border border-input px-4 py-2 text-base font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50";
const primaryClass = buttonClass + " bg-primary text-primary-foreground";
const errorText = (error: unknown) => error instanceof Error ? error.message : "Operace se nezdařila. Zkuste ji znovu.";

function NumberField({ id, label, value, onChange, required = false }: {
  id: string; label: string; value: number | null; onChange: (value: number | null) => void; required?: boolean;
}) {
  const [text, setText] = useState(value?.toString() ?? "");
  useEffect(() => setText(value?.toString() ?? ""), [value]);
  return <label htmlFor={id} className="block space-y-1 text-sm font-medium">
    <span>{label}</span>
    <input id={id} className={inputClass} inputMode="decimal" type="text" required={required}
      value={text} placeholder={required ? "Zadejte hodnotu" : "Neuvedeno"}
      onChange={event => {
        const raw = event.target.value;
        setText(raw);
        const parsed = parseDecimal(raw);
        event.target.setCustomValidity(raw.trim() && parsed === null ? "Zadejte číslo, například 4,5." : "");
        if (!raw.trim() || parsed !== null) onChange(parsed);
      }} />
  </label>;
}

export function ProjectWorkspace({ onOpen, onClose, initialFilter = "active" }: {
  onOpen: (project: MountingProject) => void; onClose: () => void; initialFilter?: "active" | "completed";
}) {
  const client = useMemo(() => getSupabaseClient(), []);
  const [user, setUser] = useState<User | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [filter, setFilter] = useState<"active" | "completed">(initialFilter);
  const [projects, setProjects] = useState<MountingProject[]>([]);
  const [draft, setDraft] = useState<MountingProject | null>(null);
  const [pdf, setPdf] = useState<File | undefined>();
  const [sourceUrl, setSourceUrl] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const editor = useRef<HTMLHeadingElement>(null);
  const createButton = useRef<HTMLButtonElement>(null);
  const localPdfUrl = useMemo(() => pdf ? URL.createObjectURL(pdf) : "", [pdf]);
  useEffect(() => () => { if (localPdfUrl) URL.revokeObjectURL(localPdfUrl); }, [localPdfUrl]);

  useEffect(() => {
    if (!client) { setAuthReady(true); return; }
    let mounted = true;
    client.auth.getSession().then(({ data, error }) => {
      if (!mounted) return;
      setUser(data.session?.user ?? null); setAuthReady(true);
      if (error) setErrors(["Přihlášení se nepodařilo ověřit. Přihlaste se znovu."]);
    }).catch(() => {
      if (mounted) { setUser(null); setErrors(["Přihlášení se nepodařilo ověřit. Přihlaste se znovu."]); }
    }).finally(() => { if (mounted) setAuthReady(true); });
    const { data } = client.auth.onAuthStateChange((_event, session) => {
      if (mounted) { setUser(session?.user ?? null); setAuthReady(true); }
    });
    return () => { mounted = false; data.subscription.unsubscribe(); };
  }, [client]);

  const refresh = useCallback(async () => {
    try { setProjects(await listProjects()); }
    catch (error) { setErrors([errorText(error)]); }
  }, []);
  useEffect(() => {
    if (!user) { setProjects([]); return; }
    void refresh();
    const onFocus = () => { void refresh(); };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [user, refresh]);

  const begin = (project?: MountingProject) => {
    setDraft(project ? structuredClone(project) : emptyProject());
    setPdf(undefined); setSourceUrl(""); setWarnings([]); setErrors([]); setReviewed(false); setMessage("");
    window.setTimeout(() => editor.current?.focus(), 0);
  };
  const edit = (change: Partial<MountingProject>) => {
    setDraft(current => current ? { ...current, ...change, sectors: ("latitude" in change || "longitude" in change) ? current.sectors.map(sector => ({ ...sector, completedAt: null })) : change.sectors ?? current.sectors } : current);
    setReviewed(false);
  };
  const editSector = (id: string, change: Partial<ProjectSector>) => {
    setDraft(current => current ? { ...current, sectors: current.sectors.map(sector => sector.id === id ? { ...sector, ...change, completedAt: null } : sector) } : current);
    setReviewed(false);
  };

  const authenticate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!client) return;
    const action = (event.nativeEvent as SubmitEvent).submitter?.getAttribute("value");
    setBusy(true); setErrors([]);
    try {
      const result = action === "register"
        ? await client.auth.signUp({ email, password, options: { emailRedirectTo: window.location.origin + window.location.pathname } })
        : await client.auth.signInWithPassword({ email, password });
      if (result.error) throw new Error(action === "register"
        ? "Účet se nepodařilo vytvořit. " + result.error.message
        : "Přihlášení se nezdařilo. Zkontrolujte e-mail, heslo a potvrzení e-mailu.");
      setPassword("");
      setMessage(action === "register" && !result.data.session
        ? "Zkontrolujte e-mail a potvrďte účet. Potom se zde přihlaste heslem."
        : "Přihlášeno. Projekty se ukládají do vašeho účtu.");
    } catch (error) { setErrors([errorText(error)]); }
    finally { setBusy(false); }
  };

  const importPdf = async (file: File) => {
    setBusy(true); setErrors([]); setReviewed(false); setMessage("Načítám zadání…");
    try {
      const pages = await readAssignmentPdf(file, setMessage);
      const result = parseAssignmentPages(pages);
      setDraft(current => {
        const next = current ?? emptyProject();
        return { ...next, name: result.name || next.name || file.name.replace(/\.pdf$/i, ""),
          siteCode: result.siteCode || next.siteCode,
          latitude: result.latitude ?? null, longitude: result.longitude ?? null,
          sectors: result.sectors.length ? result.sectors.map(sector => ({ ...sector, id: crypto.randomUUID(), completedAt: null })) : [emptySector()] };
      });
      setPdf(file); setSourceUrl(""); setWarnings(result.warnings);
      setMessage(result.sectors.length ? "Nalezeno položek: " + result.sectors.length + ". Zkontrolujte údaje proti PDF."
        : "Tabulku se nepodařilo bezpečně rozpoznat. Údaje můžete doplnit ručně podle PDF.");
      window.setTimeout(() => editor.current?.focus(), 0);
    } catch (error) { setMessage(""); setErrors([errorText(error)]); }
    finally { setBusy(false); }
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!draft) return;
    const problems = validateProject(draft);
    if (!reviewed) problems.push("Nejprve potvrďte kontrolu údajů proti zadání.");
    if (!user) problems.push("Pro synchronizaci projektu se přihlaste.");
    if (problems.length) { setErrors(problems); return; }
    setBusy(true); setErrors([]); setMessage("Ukládám projekt a zadání…");
    try {
      const saved = await saveProject(draft, pdf);
      setDraft(saved); setPdf(undefined);
      setProjects(current => [saved, ...current.filter(project => project.id !== saved.id)]);
      setMessage("Projekt uložen. Stejné údaje otevřete po přihlášení na telefonu i počítači.");
      setReviewed(true);
      onOpen(saved);
    } catch (error) { setMessage(""); setErrors([errorText(error)]); }
    finally { setBusy(false); }
  };

  const openMap = (project: MountingProject) => {
    const problems = validateProject(project);
    if (problems.length) { setErrors(problems); return; }
    onOpen(project);
  };

  return <main className="min-h-dvh bg-background text-foreground" lang="cs">
    <div className="mx-auto max-w-5xl space-y-6 p-4 pb-12 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div><p className="text-sm font-medium text-muted-foreground">Azimuth · montážní podklady</p><h1 className="text-2xl font-bold">Moje projekty</h1></div>
        <button type="button" className={buttonClass} onClick={onClose} disabled={busy}><ArrowLeft aria-hidden className="h-5 w-5" />Zpět na mapu</button>
      </header>
      <p className="max-w-3xl">Nahrajte PDF zadání, zkontrolujte sektory a uložte projekt. Azimuty se pak načtou do mapy; náklony zůstanou viditelné jako požadované hodnoty pro montáž.</p>

      {!client && <p role="status" className="rounded-xl border border-border bg-card p-4">Synchronizace zatím není připojená. PDF můžete načíst a zkontrolovat; uložení do účtu bude dostupné po připojení databáze.</p>}
      {client && !authReady && <p role="status">Ověřuji přihlášení…</p>}
      {client && authReady && !user && <form onSubmit={authenticate} className="space-y-3 rounded-xl border border-border bg-card p-4">
        <h2 className="text-lg font-semibold">Přihlášení pro synchronizaci</h2>
        <p className="text-sm text-muted-foreground">Na telefonu i počítači použijte stejný účet. Při prvním použití zvolte Vytvořit účet.</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="space-y-1" htmlFor="project-email"><span>E-mail</span><input id="project-email" className={inputClass} type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} /></label>
          <label className="space-y-1" htmlFor="project-password"><span>Heslo</span><input id="project-password" className={inputClass} type="password" autoComplete="current-password" required minLength={8} value={password} onChange={event => setPassword(event.target.value)} /></label>
        </div>
        <div className="flex flex-wrap gap-2"><button className={primaryClass} value="login" disabled={busy}>Přihlásit se</button><button className={buttonClass} value="register" disabled={busy}>Vytvořit účet</button></div>
      </form>}
      {user && <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border bg-card p-3">
        <p className="min-w-0 break-all text-sm">Přihlášeno: {user.email}</p>
        <button className={buttonClass} type="button" disabled={busy} onClick={async () => {
          if (!client) return; setBusy(true); setErrors([]);
          try {
            const { error } = await client.auth.signOut();
            if (error) throw error;
            setDraft(null); setPdf(undefined); setProjects([]); setMessage("Odhlášeno.");
          } catch { setErrors(["Odhlášení se nezdařilo. Zkuste to znovu."]); }
          finally { setBusy(false); }
        }}>Odhlásit se</button>
      </div>}

      <p role="status" aria-atomic="true" className="text-base">{message}</p>
      {errors.length > 0 && <div role="alert" className="rounded-xl border-2 border-destructive bg-card p-4"><p className="font-semibold">Je potřeba opravit:</p><ul className="list-inside list-disc">{errors.map((error, i) => <li key={i}>{error}</li>)}</ul></div>}

      {!draft && <section className="space-y-4" aria-labelledby="library-title">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="library-title" className="text-xl font-semibold">Uložené projekty</h2>
          <div className="flex flex-wrap gap-2">
            {user && <button type="button" className={buttonClass} disabled={busy} onClick={() => void refresh()}><RefreshCw aria-hidden className="h-5 w-5" />Obnovit</button>}
            <button ref={createButton} type="button" className={primaryClass} onClick={() => begin()}><Plus aria-hidden className="h-5 w-5" />Nový projekt / nahrát PDF</button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2" aria-label="Stav projektů">
          <button type="button" className={filter === "active" ? primaryClass : buttonClass} aria-pressed={filter === "active"} onClick={() => setFilter("active")}>Rozpracované ({projects.filter(project => !projectIsComplete(project)).length})</button>
          <button type="button" className={filter === "completed" ? primaryClass : buttonClass} aria-pressed={filter === "completed"} onClick={() => setFilter("completed")}>Hotové ({projects.filter(projectIsComplete).length})</button>
        </div>
        {!projects.length && <p className="rounded-xl border border-dashed border-border p-6 text-muted-foreground">{user ? "Zatím nemáte uložený projekt. Začněte nahráním zadání." : "Pro zobrazení uložených projektů se přihlaste. Nové zadání můžete připravit už teď."}</p>}
        <div className="grid gap-3 sm:grid-cols-2">{projects.filter(project => projectIsComplete(project) === (filter === "completed")).map(project => <article key={project.id} className="space-y-3 rounded-xl border border-border bg-card p-4">
          <h3 className="break-words text-lg font-semibold">{project.name}</h3>
          <p className="text-sm text-muted-foreground">{project.siteCode || "Bez kódu lokality"} · {project.sectors.filter(sector => sector.completedAt).length}/{project.sectors.length} hotovo · revize {project.revision}</p>
          <div className="flex flex-wrap gap-2"><button type="button" className={primaryClass} onClick={() => openMap(project)}><FolderOpen aria-hidden className="h-5 w-5" />Otevřít v mapě</button><button type="button" className={buttonClass} onClick={() => begin(project)}>Zadání a úpravy</button></div>
        </article>)}</div>
      </section>}

      {draft && <form onSubmit={save} className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h2 ref={editor} tabIndex={-1} className="text-xl font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">{draft.revision ? "Úprava projektu" : "Nový projekt"}</h2>
          <button type="button" className={buttonClass} disabled={busy} onClick={() => {
            if ((!reviewed || pdf) && !window.confirm("Zahodit rozpracované změny a vrátit se k projektům?")) return;
            setDraft(null); setPdf(undefined); setErrors([]); setMessage("");
            window.setTimeout(() => createButton.current?.focus(), 0);
          }}>Zavřít zadání</button>
        </div>
        <section className="space-y-3 rounded-xl border border-border bg-card p-4" aria-labelledby="upload-title">
          <h3 id="upload-title" className="text-lg font-semibold">1. Nahrát montážní zadání</h3>
          <p id="pdf-help" className="text-sm text-muted-foreground">Textové PDF, nejvýše 20 MB a 50 stran. Skeny zatím vyžadují ruční doplnění. Nové PDF před uložením nahradí návrh sektorů, uloženou revizi nezmění.</p>
          <input id="assignment-pdf" type="file" accept=".pdf,application/pdf" aria-label="Montážní zadání v PDF" aria-describedby="pdf-help" className="min-h-12 max-w-full text-base file:mr-3 file:min-h-12 file:rounded-lg file:border-0 file:bg-primary file:px-4 file:text-primary-foreground" disabled={busy}
            onChange={event => { const file = event.target.files?.[0]; if (file) void importPdf(file); event.target.value = ""; }} />
          {(pdf || draft.document) && <p className="break-all text-sm"><FileText className="mr-1 inline h-4 w-4" aria-hidden />{pdf?.name ?? draft.document?.name}</p>}
          {(localPdfUrl || sourceUrl) && <a className={buttonClass} href={localPdfUrl || sourceUrl} target="_blank" rel="noopener noreferrer">Otevřít původní PDF</a>}
          {!pdf && draft.document && !sourceUrl && <button type="button" className={buttonClass} disabled={busy} onClick={async () => {
            if (!draft.document) return;
            try { setSourceUrl(await getDocumentUrl(draft.document.path)); setMessage("Odkaz na PDF je připravený. Otevřete původní PDF tlačítkem."); }
            catch (error) { setErrors([errorText(error)]); }
          }}>Připravit původní PDF</button>}
        </section>

        <section className="space-y-4 rounded-xl border border-border bg-card p-4" aria-labelledby="review-title">
          <h3 id="review-title" className="text-lg font-semibold">2. Zkontrolovat projekt a sektory</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <label htmlFor="project-name" className="space-y-1"><span>Název projektu</span><input id="project-name" className={inputClass} value={draft.name} required maxLength={160} onChange={event => edit({ name: event.target.value })} /></label>
            <label htmlFor="project-site" className="space-y-1"><span>Kód lokality</span><input id="project-site" className={inputClass} value={draft.siteCode} maxLength={100} onChange={event => edit({ siteCode: event.target.value })} /></label>
            <NumberField id="project-latitude" label="Zeměpisná šířka (WGS 84)" value={draft.latitude} onChange={value => edit({ latitude: value })} />
            <NumberField id="project-longitude" label="Zeměpisná délka (WGS 84)" value={draft.longitude} onChange={value => edit({ longitude: value })} />
          </div>
          <p className="text-sm text-muted-foreground">Souřadnice jsou volitelné. Bez nich je po otevření projektu potřeba nastavit místo montáže. Náklony jsou hodnoty ze zadání, telefon je neměří.</p>
          {warnings.length > 0 && <div className="rounded-lg border border-border bg-background p-3"><p className="font-medium">Ke kontrole v PDF:</p><ul className="list-inside list-disc text-sm">{warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul></div>}
          {draft.sectors.map((sector, index) => <fieldset key={sector.id} className="min-w-0 space-y-3 rounded-xl border border-border p-3">
            <legend className="px-1 font-semibold">Anténa / sektor {index + 1}</legend>
            <label className="block space-y-1" htmlFor={"sector-name-" + sector.id}><span>Označení sektoru, antény nebo pásma</span><input id={"sector-name-" + sector.id} className={inputClass} required maxLength={160} value={sector.name} onChange={event => editSector(sector.id, { name: event.target.value })} /></label>
            <div className="grid gap-3 sm:grid-cols-3">
              <NumberField id={"azimuth-" + sector.id} label="Azimut (°)" value={sector.azimuthDeg} required onChange={value => editSector(sector.id, { azimuthDeg: value })} />
              <NumberField id={"mechanical-" + sector.id} label="Mechanický náklon (°)" value={sector.mechanicalTiltDeg} onChange={value => editSector(sector.id, { mechanicalTiltDeg: value })} />
              <NumberField id={"electrical-" + sector.id} label="Elektrický náklon / RET (°)" value={sector.electricalTiltDeg} onChange={value => editSector(sector.id, { electricalTiltDeg: value })} />
            </div>
            {sector.warnings.length > 0 && <ul className="list-inside list-disc text-sm">{sector.warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul>}
            {sector.sourceText && <details className="text-sm"><summary className="min-h-12 cursor-pointer py-3 font-medium">Zdroj v PDF{sector.sourcePage ? " · strana " + sector.sourcePage : ""}</summary><p className="whitespace-pre-wrap break-words rounded-md bg-background p-3">{sector.sourceText}</p></details>}
            <button type="button" className={buttonClass} aria-label={"Odebrat anténu " + (index + 1)} onClick={() => {
              edit({ sectors: draft.sectors.filter(item => item.id !== sector.id) });
              window.setTimeout(() => document.getElementById("add-sector")?.focus(), 0);
            }}><Trash2 className="h-5 w-5" aria-hidden />Odebrat</button>
          </fieldset>)}
          <button id="add-sector" type="button" className={buttonClass} disabled={draft.sectors.length >= 300} onClick={() => {
            const sector = emptySector(); edit({ sectors: [...draft.sectors, sector] });
            window.setTimeout(() => document.getElementById("sector-name-" + sector.id)?.focus(), 0);
          }}><Plus className="h-5 w-5" aria-hidden />Přidat anténu ručně</button>
        </section>

        <section className="space-y-4 rounded-xl border border-border bg-card p-4">
          <h3 className="text-lg font-semibold">3. Potvrdit a uložit</h3>
          <label className="flex min-h-12 items-start gap-3 py-2"><input type="checkbox" className="mt-1 h-6 w-6 flex-none accent-current" checked={reviewed} required onChange={event => setReviewed(event.target.checked)} /><span>Zkontroloval(a) jsem hodnoty proti zadání. Prázdné náklony jsou neuvedené údaje, nikoliv nula.</span></label>
          <div className="flex flex-wrap gap-3">
            <button className={primaryClass} type="submit" disabled={busy || !user}>{busy ? "Zpracovávám…" : "Potvrdit, uložit a načíst do mapy"}</button>

          </div>
          {!user && <p className="text-sm">Pro uložení a synchronizaci se přihlaste výše. Rozpracované PDF zatím zůstává v tomto okně.</p>}
        </section>
      </form>}
    </div>
  </main>;
}
