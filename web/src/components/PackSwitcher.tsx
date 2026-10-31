"use client";

import { PACKS, type PackKey, type PackMeta } from "@/lib/result";

type Props = {
  active: PackKey;
  /** null mientras el índice aún no cargó → chip «cargando». */
  packStatus: Record<
    string,
    { has_run: boolean; _sin_corrida?: boolean }
  > | null;
  onChange: (key: PackKey) => void;
};

/**
 * Chips de paquete — momento clave del demo.
 * Tri-estado por chip: cargando | sin corrida | (con corrida, sin sufijo).
 */
export function PackSwitcher({ active, packStatus, onChange }: Props) {
  const indexReady = packStatus !== null;

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div
        className="chips flex gap-1.5"
        role="group"
        aria-label="Paquete activo"
      >
        {PACKS.map((p: PackMeta) => {
          const pressed = p.key === active;
          let suffix: string | null = null;
          if (!indexReady) {
            suffix = "· cargando";
          } else {
            const st = packStatus[p.key];
            const has = Boolean(st?.has_run) && !st?._sin_corrida;
            if (!has) suffix = "· sin corrida";
          }
          return (
            <button
              key={p.key}
              type="button"
              className={
                "rounded-full border px-3.5 py-1.5 text-sm transition-colors " +
                (pressed
                  ? "chip border-pack"
                  : "border-line text-muted hover:border-pack hover:text-[var(--text)]")
              }
              aria-pressed={pressed}
              aria-describedby={`pack-file-${p.key}`}
              onClick={() => onChange(p.key)}
              onKeyDown={(e) => {
                if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
                e.preventDefault();
                const i = PACKS.findIndex((x) => x.key === active);
                const next =
                  e.key === "ArrowRight"
                    ? PACKS[(i + 1) % PACKS.length]
                    : PACKS[(i - 1 + PACKS.length) % PACKS.length];
                onChange(next.key);
              }}
            >
              {p.label}
              {suffix && (
                <span className="ml-1 text-[10px] opacity-70">{suffix}</span>
              )}
            </button>
          );
        })}
      </div>
      <p
        id={`pack-file-${active}`}
        className="font-display text-xl font-semibold text-pack"
        aria-live="polite"
      >
        {PACKS.find((p) => p.key === active)?.file ?? "—"}
      </p>
    </div>
  );
}
