"use client";
import type { PdfTextPage } from "./pdf-import";

export async function readAssignmentPdf(file: File, progress: (message: string) => void): Promise<PdfTextPage[]> {
  if (file.size > 20 * 1024 * 1024) throw new Error("PDF může mít nejvýše 20 MB.");
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  if (String.fromCharCode(...bytes.slice(0, 5)) !== "%PDF-") throw new Error("Soubor není platné PDF.");
  const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
  pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
  const task = pdfjs.getDocument({ data: bytes });
  const timeout = window.setTimeout(() => { void task.destroy(); }, 60000);
  try {
    const document = await task.promise;
    if (document.numPages > 50) throw new Error("Zadání má více než 50 stran. Nahrajte výřez se sektory.");
    const pages: PdfTextPage[] = [];
    for (let n = 1; n <= document.numPages; n++) {
      progress("Čtu PDF: strana " + n + " z " + document.numPages + ".");
      const page = await document.getPage(n);
      const content = await page.getTextContent();
      if (content.items.length > 20000) throw new Error("Stránka je příliš složitá. Nahrajte výřez s tabulkou sektorů.");
      pages.push({ page: n, items: content.items.flatMap(item => "str" in item
        ? [{ text: item.str, x: item.transform[4], y: item.transform[5] }] : []) });
      page.cleanup();
    }
    if (pages.every(page => page.items.every(item => !item.text.trim()))) {
      throw new Error("PDF nemá čitelný text. Může jít o sken; nahrajte textové PDF nebo doplňte sektory ručně.");
    }
    return pages;
  } catch (error) {
    if (error instanceof Error && error.name === "PasswordException") throw new Error("PDF je chráněné heslem. Nahrajte odemčenou kopii.");
    throw error;
  } finally {
    window.clearTimeout(timeout);
    await task.destroy();
  }
}
