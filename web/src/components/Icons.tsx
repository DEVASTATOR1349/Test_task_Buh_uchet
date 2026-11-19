import type { ReactNode } from 'react';

// Один набор иконок: 16×16, линия 1.5, скруглённые концы.

interface IconProps {
  className?: string;
}

function Icon({ className, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      className={className}
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export function ChevronLeft(props: IconProps) {
  return <Icon {...props}><path d="M10 3.5 5.5 8l4.5 4.5" /></Icon>;
}

export function ChevronRight(props: IconProps) {
  return <Icon {...props}><path d="M6 3.5 10.5 8 6 12.5" /></Icon>;
}

export function Alert(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M8 2.2 14.3 13H1.7L8 2.2Z" />
      <path d="M8 6.5v3" />
      <path d="M8 11.4v.1" />
    </Icon>
  );
}

export function Mark({ className }: IconProps) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect width="32" height="32" rx="7" fill="currentColor" />
      <path d="M9 11h14M9 16h14M9 21h8" stroke="var(--surface)" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}
