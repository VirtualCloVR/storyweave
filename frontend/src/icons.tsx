import type { ReactNode, SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement> & { size?: number }
const icon = (path: ReactNode, { size = 18, ...props }: IconProps = {}) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{path}</svg>
export const MenuIcon = (p: IconProps) => icon(<><path d="M4 6h16M4 12h16M4 18h16" /></>, p)
export const PlusIcon = (p: IconProps) => icon(<><path d="M12 5v14M5 12h14" /></>, p)
export const SearchIcon = (p: IconProps) => icon(<><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 4.2 4.2" /></>, p)
export const PinIcon = (p: IconProps) => icon(<><path d="m8 3 8 0 1 5-2.5 2.5V17l-2.5-1.5L9.5 17v-6.5L7 8z" /><path d="M12 17v4" /></>, p)
export const ArchiveIcon = (p: IconProps) => icon(<><path d="M4 7h16v13H4zM3 4h18v3H3zM9 12h6" /></>, p)
export const ChevronIcon = (p: IconProps) => icon(<path d="m7 9 5 5 5-5" />, p)
export const SendIcon = (p: IconProps) => icon(<><path d="m21 3-7.2 18-3.7-7.1L3 10.2z" /><path d="M10.1 13.9 21 3" /></>, p)
export const SparkleIcon = (p: IconProps) => icon(<><path d="m12 3 1.3 5.7L19 10l-5.7 1.3L12 17l-1.3-5.7L5 10l5.7-1.3z" /><path d="m19 16 .6 2.4L22 19l-2.4.6L19 22l-.6-2.4L16 19l2.4-.6z" /></>, p)
export const CloseIcon = (p: IconProps) => icon(<><path d="m6 6 12 12M18 6 6 18" /></>, p)
export const MoreIcon = (p: IconProps) => icon(<><circle cx="5" cy="12" r="1" fill="currentColor" /><circle cx="12" cy="12" r="1" fill="currentColor" /><circle cx="19" cy="12" r="1" fill="currentColor" /></>, p)
export const CheckIcon = (p: IconProps) => icon(<path d="m5 12 4 4L19 6" />, p)
export const SunIcon = (p: IconProps) => icon(<><circle cx="12" cy="12" r="3.4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>, p)
