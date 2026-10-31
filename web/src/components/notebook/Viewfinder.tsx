import type { ReactNode } from "react";

export function Viewfinder({
  label = "Simulated camera",
  children,
}: {
  label?: string;
  children: ReactNode;
}) {
  return (
    <div className="viewfinder">
      <div className="viewfinder-hud">
        <span>{label}</span>
        <span aria-hidden="true">viewfinder</span>
      </div>
      <div className="viewfinder-screen">
        <span className="vf-corner tl" aria-hidden="true" />
        <span className="vf-corner tr" aria-hidden="true" />
        <span className="vf-corner bl" aria-hidden="true" />
        <span className="vf-corner br" aria-hidden="true" />
        {children}
      </div>
    </div>
  );
}
