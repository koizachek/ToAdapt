// Handgezeichnete Icons (Vectorly „Ultimate Notion Icons", lizenziert —
// siehe public/icons/README.md). Dekorativ: aria-hidden, alt leer.
export default function NotionIcon({
  name,
  size = 28,
  className = '',
}: {
  name: string
  size?: number
  className?: string
}) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`/icons/${name}.svg`}
      width={size}
      height={size}
      alt=""
      aria-hidden
      draggable={false}
      className={`inline-block select-none align-middle ${className}`}
    />
  )
}
