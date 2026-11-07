export function Spinner() {
  return (
    <svg className="size-4 shrink-0 animate-spin text-primary motion-reduce:animate-none" viewBox="0 0 24 24" aria-label="in progress" role="img">
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
