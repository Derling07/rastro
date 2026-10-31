"use client";

type Props = {
  /** Solo mostrar si el campo está presente y es true. */
  partial?: boolean;
};

/**
 * Banner global (todos los packs) cuando el motor reporta conteo parcial
 * por tope de objetos/frame.
 */
export function PartialBanner({ partial }: Props) {
  if (partial !== true) return null;
  return (
    <div
      className="rounded-lg border border-amber-700 bg-amber-100 px-3 py-2 text-sm text-amber-900"
      role="status"
    >
      Partial count: more than 16 objects in a frame.
    </div>
  );
}
