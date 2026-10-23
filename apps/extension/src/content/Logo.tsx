export function LensLogo({ size = 24 }: { size?: number }) {
  return (
    <svg className="vtl-logo" width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <path d="M24.5 22.4A11.2 11.2 0 1 1 26.6 19l.9 6.2-5-2.9" stroke="url(#vtl-prism)" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="m10.5 14.5 4.1 3.7 7-7" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
      <defs><linearGradient id="vtl-prism" x1="5" y1="5" x2="27" y2="27"><stop stopColor="#7C5CFC"/><stop offset=".52" stopColor="#22D3EE"/><stop offset="1" stopColor="#A3E635"/></linearGradient></defs>
    </svg>
  );
}
