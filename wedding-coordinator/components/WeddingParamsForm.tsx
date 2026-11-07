"use client";

import { useState } from "react";
import { WeddingParams } from "@/types/wedding";

interface FieldConfig {
  key: keyof WeddingParams;
  label: string;
  placeholder: string;
  textarea?: boolean;
}

const FIELDS: FieldConfig[] = [
  {
    key: "date",
    label: "Termín svatby",
    placeholder: "např. 12. září 2026",
  },
  {
    key: "venue",
    label: "Lokalita / Typ místa",
    placeholder: "např. zámek Loučeň, historická stodola, zahrada",
  },
  {
    key: "budget",
    label: "Přibližný rozpočet",
    placeholder: "např. 1 500 000 CZK",
  },
  {
    key: "guestCount",
    label: "Počet hostů",
    placeholder: "např. 80",
  },
  {
    key: "style",
    label: "Styl / Vize svatby",
    placeholder: "např. elegantní minimalismus, boho, black tie",
  },
  {
    key: "priorities",
    label: "Specifické požadavky / Priority",
    placeholder:
      "např. dokonalé jídlo, živá hudba, žádný stres, bezlepkové menu pro 10 hostů",
    textarea: true,
  },
];

const EMPTY_PARAMS: WeddingParams = {
  date: "",
  venue: "",
  budget: "",
  guestCount: "",
  style: "",
  priorities: "",
};

export default function WeddingParamsForm({
  onSubmit,
}: {
  onSubmit: (params: WeddingParams) => void;
}) {
  const [params, setParams] = useState<WeddingParams>(EMPTY_PARAMS);

  const handleChange = (key: keyof WeddingParams, value: string) => {
    setParams((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(params);
  };

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-6 py-16">
      <div className="mb-10 text-center animate-fade-in-up">
        <p className="mb-2 text-xs uppercase tracking-[0.35em] text-gold">
          Claude Quickstart
        </p>
        <h1 className="font-serif text-3xl text-ivory sm:text-4xl">
          Vaše svatební koordinátorka
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted">
          Sdělte mi klíčové parametry vaší svatby a připravím ucelený plán
          realizace, harmonogram příprav, rozpad rozpočtu a šablony pro
          komunikaci s dodavateli.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="animate-fade-in-up space-y-5 rounded-2xl border border-gold/20 bg-surface/80 p-8 shadow-2xl shadow-black/40"
      >
        {FIELDS.map((field) => (
          <div key={field.key}>
            <label
              htmlFor={field.key}
              className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-gold-light/90"
            >
              {field.label}
            </label>
            {field.textarea ? (
              <textarea
                id={field.key}
                value={params[field.key]}
                onChange={(e) => handleChange(field.key, e.target.value)}
                placeholder={field.placeholder}
                rows={3}
                className="w-full resize-none rounded-lg border border-gold/20 bg-ink/60 px-3.5 py-2.5 text-sm text-ivory placeholder:text-muted/60 focus:border-gold/60 focus:outline-none focus:ring-1 focus:ring-gold/40"
              />
            ) : (
              <input
                id={field.key}
                type="text"
                value={params[field.key]}
                onChange={(e) => handleChange(field.key, e.target.value)}
                placeholder={field.placeholder}
                className="w-full rounded-lg border border-gold/20 bg-ink/60 px-3.5 py-2.5 text-sm text-ivory placeholder:text-muted/60 focus:border-gold/60 focus:outline-none focus:ring-1 focus:ring-gold/40"
              />
            )}
          </div>
        ))}

        <button
          type="submit"
          className="mt-2 w-full rounded-lg bg-gradient-to-r from-gold-dark via-gold to-gold-light px-4 py-3 text-sm font-semibold uppercase tracking-wider text-ink transition hover:brightness-110 active:brightness-95"
        >
          Sestavit svatební plán
        </button>
        <p className="text-center text-xs text-muted/70">
          Pole můžete nechat prázdná — koordinátorka se na chybějící údaje
          doptá v konverzaci.
        </p>
      </form>
    </div>
  );
}
