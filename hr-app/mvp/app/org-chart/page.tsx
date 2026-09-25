import Link from "next/link";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

interface Person {
  id: number;
  name: string;
  job_title: string;
  department: string | null;
  manager_id: number | null;
}

interface TreeNode extends Person {
  children: TreeNode[];
}

function buildTree(people: Person[]): TreeNode[] {
  const nodes: TreeNode[] = people.map((p) => ({ ...p, children: [] }));
  const ids = new Set(nodes.map((n) => n.id));
  const roots: TreeNode[] = [];
  const attached = new Set<number>();

  for (const node of nodes) {
    if (node.manager_id === null || !ids.has(node.manager_id)) {
      roots.push(node);
      attached.add(node.id);
    }
  }

  // Attach children breadth-first from the roots so cycles in bad data are
  // simply left out rather than causing infinite recursion.
  const queue = [...roots];
  while (queue.length > 0) {
    const current = queue.shift()!;
    for (const node of nodes) {
      if (node.manager_id === current.id && !attached.has(node.id)) {
        current.children.push(node);
        attached.add(node.id);
        queue.push(node);
      }
    }
    current.children.sort((a, b) => a.name.localeCompare(b.name));
  }

  return roots.sort((a, b) => a.name.localeCompare(b.name));
}

function PersonCard({ node }: { node: TreeNode }) {
  return (
    <Link
      href={`/employees/${node.id}`}
      className="card inline-flex flex-col px-4 py-3 transition-colors hover:border-brand-500"
    >
      <span className="font-medium">{node.name}</span>
      <span className="text-sm text-gray-600">{node.job_title}</span>
      {node.department && <span className="mt-0.5 text-xs text-gray-400">{node.department}</span>}
    </Link>
  );
}

function TreeBranch({ node }: { node: TreeNode }) {
  return (
    <li>
      <PersonCard node={node} />
      {node.children.length > 0 && (
        <ul className="ml-5 mt-3 space-y-3 border-l-2 border-gray-200 pl-6">
          {node.children.map((child) => (
            <TreeBranch key={child.id} node={child} />
          ))}
        </ul>
      )}
    </li>
  );
}

export default function OrgChartPage() {
  const db = getDb();
  const people = db
    .prepare(
      `SELECT e.id, e.first_name || ' ' || e.last_name AS name, e.job_title, e.manager_id,
              d.name AS department
       FROM employees e
       LEFT JOIN departments d ON d.id = e.department_id
       WHERE e.status != 'terminated'
       ORDER BY e.first_name, e.last_name`
    )
    .all() as Person[];

  const roots = buildTree(people);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Org Chart</h1>
        <p className="text-sm text-gray-500">Reporting lines across {people.length} people. Click anyone to view their profile.</p>
      </div>

      {roots.length === 0 ? (
        <div className="card text-sm text-gray-500">No employees to display.</div>
      ) : (
        <ul className="space-y-6">
          {roots.map((root) => (
            <TreeBranch key={root.id} node={root} />
          ))}
        </ul>
      )}
    </div>
  );
}
