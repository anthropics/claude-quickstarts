/** The app mark: a pine on an ember square. Inline SVG so there is no asset to load. */
export function Mark({ size = 22 }: { size?: number }) {
  return (
    <svg className="mark" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <rect width="24" height="24" rx="6" fill="var(--accent)" />
      <path d="M12 4.2 16.4 11h-2.3l3.4 5.4H6.5L9.9 11H7.6Z" fill="var(--surface-0)" />
      <rect x="11.1" y="16.4" width="1.8" height="3.2" rx="0.6" fill="var(--surface-0)" />
    </svg>
  );
}
