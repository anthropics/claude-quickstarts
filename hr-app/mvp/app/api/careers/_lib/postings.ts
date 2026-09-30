import { getDb } from "@/lib/db";
import type { JobPosting } from "@/lib/types";
import { generateSlug } from "./validate";

export type PublicPosting = JobPosting & {
  public_slug: string | null;
  department_name: string | null;
};

/**
 * Ensures every open posting has a public_slug. Slugs are normally minted when
 * a posting is published (PATCH /api/recruitment/postings/[id]); this lazy
 * backfill covers postings that were opened before slugs existed (seed data).
 */
export function ensurePublicSlugs(): void {
  const db = getDb();
  const missing = db
    .prepare("SELECT id, title FROM job_postings WHERE status = 'open' AND (public_slug IS NULL OR public_slug = '')")
    .all() as { id: number; title: string }[];
  if (missing.length === 0) return;
  const update = db.prepare("UPDATE job_postings SET public_slug = ? WHERE id = ?");
  for (const p of missing) update.run(generateSlug(p.title, p.id), p.id);
}

/** Open postings for the public careers list, newest first. */
export function listOpenPostings(): PublicPosting[] {
  ensurePublicSlugs();
  return getDb()
    .prepare(
      `SELECT jp.*, d.name AS department_name
       FROM job_postings jp
       LEFT JOIN departments d ON d.id = jp.department_id
       WHERE jp.status = 'open'
       ORDER BY jp.posted_at DESC, jp.id DESC`
    )
    .all() as PublicPosting[];
}

/** Resolves a public slug to its OPEN posting, or null. */
export function getOpenPostingBySlug(slug: string): PublicPosting | null {
  ensurePublicSlugs();
  const posting = getDb()
    .prepare(
      `SELECT jp.*, d.name AS department_name
       FROM job_postings jp
       LEFT JOIN departments d ON d.id = jp.department_id
       WHERE jp.public_slug = ? AND jp.status = 'open'`
    )
    .get(slug) as PublicPosting | undefined;
  return posting ?? null;
}
