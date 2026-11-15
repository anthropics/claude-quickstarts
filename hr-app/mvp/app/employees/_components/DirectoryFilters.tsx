"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

interface Props {
  departments: { id: number; name: string }[];
  initialQ: string;
  initialDept: string;
}

export default function DirectoryFilters({ departments, initialQ, initialDept }: Props) {
  const router = useRouter();
  const [q, setQ] = useState(initialQ);
  const [dept, setDept] = useState(initialDept);

  function apply(nextQ: string, nextDept: string) {
    const params = new URLSearchParams();
    if (nextQ.trim()) params.set("q", nextQ.trim());
    if (nextDept) params.set("dept", nextDept);
    const qs = params.toString();
    router.push(qs ? `/employees?${qs}` : "/employees");
  }

  return (
    <form
      className="flex flex-col gap-3 sm:flex-row sm:items-center"
      onSubmit={(e) => {
        e.preventDefault();
        apply(q, dept);
      }}
    >
      <input
        type="search"
        className="input sm:max-w-xs"
        placeholder="Search by name…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        aria-label="Search employees by name"
      />
      <select
        className="input sm:w-56"
        value={dept}
        onChange={(e) => {
          setDept(e.target.value);
          apply(q, e.target.value);
        }}
        aria-label="Filter by department"
      >
        <option value="">All departments</option>
        {departments.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name}
          </option>
        ))}
      </select>
      <button type="submit" className="btn-secondary">
        Search
      </button>
    </form>
  );
}
