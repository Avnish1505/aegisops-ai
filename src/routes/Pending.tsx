/** Screens not built yet on this branch; each is replaced by its own M3 commit. */
export function Pending({ title }: { title: string }) {
  return (
    <div className="p-6">
      <h1 className="text-lg font-semibold">{title}</h1>
      <p className="text-muted">Not built yet.</p>
    </div>
  )
}
