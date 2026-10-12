// Small inline SVG icons (no emoji in UI chrome).
type P = { size?: number; className?: string }
const svg = (size: number, className: string | undefined, path: React.ReactNode) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
       strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">{path}</svg>
)
export const CheckIcon = ({ size = 14, className }: P) => svg(size, className, <path d="M20 6 9 17l-5-5" />)
export const ArrowIcon = ({ size = 14, className }: P) => svg(size, className, <path d="M5 12h14M13 6l6 6-6 6" />)
export const PlayIcon = ({ size = 14, className }: P) => svg(size, className, <path d="M7 4v16l13-8z" fill="currentColor" stroke="none" />)
export const AlertIcon = ({ size = 14, className }: P) => svg(size, className, <><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /></>)
export const ToolIcon = ({ size = 14, className }: P) => svg(size, className, <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z" />)
export const ResetIcon = ({ size = 14, className }: P) => svg(size, className, <><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /></>)
export const MailIcon = ({ size = 14, className }: P) => svg(size, className, <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></>)
