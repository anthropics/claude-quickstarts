export default function TypeBadge({ type }: { type: string }) {
  switch (type) {
    case "appointment":
      return <span className="badge-blue">Appointment</span>;
    case "confirmation":
      return <span className="badge-green">Confirmation</span>;
    case "warning":
      return <span className="badge-red">Warning</span>;
    case "increase":
      return <span className="badge-yellow">Increase</span>;
    default:
      return <span className="badge-gray">General</span>;
  }
}
