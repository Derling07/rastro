"use client";

import {
  ACCESS_LINES,
  CARDINAL_LABEL,
  CARDINAL_LETTER,
  CARDINALS,
  countFor,
  outboundTotals,
  type Cardinal,
  type TurnMatrixData,
} from "@/lib/transito";

type Props = {
  /** Matriz origen→destino; vacía si sin corrida. */
  matrix: TurnMatrixData;
  empty?: boolean;
  /** Badge si los datos vinieran de mock (no cableamos mock hoy). */
  isMock?: boolean;
};

function Cell({
  value,
  empty,
}: {
  value: number | null;
  empty?: boolean;
}) {
  if (empty || value === null) {
    return <span className="text-muted/50">—</span>;
  }
  return <span className="font-display text-lg font-semibold text-pack">{value}</span>;
}

/**
 * Vista tránsito: brújula N/S/E/O + tabla OD de giros.
 * Sin corrida real → layout + «Sin corrida» (no inventar números).
 */
export function TurnMatrix({ matrix, empty, isMock }: Props) {
  const out = outboundTotals(matrix);

  return (
    <section
      className="rounded-lg border border-line bg-panel p-4"
      aria-labelledby="giros-h"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id="giros-h" className="text-sm font-bold text-muted">
          Turn matrix · N/S/E/W
        </h2>
        {empty ? (
          <span className="rounded-full bg-[var(--line)] px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-muted">
            No run yet
          </span>
        ) : isMock ? (
          <span className="rounded-full bg-[var(--line)] px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-muted">
            Mock
          </span>
        ) : (
          <span className="rounded-full bg-pack px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-ink">
            Measured
          </span>
        )}
      </div>

      {empty && (
        <p className="mb-3 text-sm text-muted">
          No run yet for this video. The approach layout is ready; counts fill in after a run.
        </p>
      )}

      {/* Brújula de accesos */}
      <div
        className="mx-auto mb-4 grid max-w-xs grid-cols-3 grid-rows-3 gap-2 text-center"
        role="img"
        aria-label="Intersection approaches: North, South, East, West"
      >
        <div />
        <AccessPad from="N" total={empty ? null : out.N} />
        <div />
        <AccessPad from="O" total={empty ? null : out.O} />
        <div
          className="flex items-center justify-center rounded border border-dashed border-line bg-ink/40"
          aria-hidden
        >
          <span className="font-display text-xs font-bold tracking-widest text-muted">
            ∩
          </span>
        </div>
        <AccessPad from="E" total={empty ? null : out.E} />
        <div />
        <AccessPad from="S" total={empty ? null : out.S} />
        <div />
      </div>

      <ul className="mb-4 flex flex-wrap gap-2 text-[11px] text-muted">
        {ACCESS_LINES.map((l) => (
          <li
            key={l.id}
            className="rounded border border-line px-2 py-0.5"
            title={`geometry.lines id=${l.id}`}
          >
            <span className="font-display text-pack">{CARDINAL_LETTER[l.from]}</span> · {l.label}
          </li>
        ))}
      </ul>

      {/* Tabla OD */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[240px] border-collapse text-sm">
          <caption className="sr-only">
            Turn counts from origin to destination
          </caption>
          <thead>
            <tr>
              <th
                scope="col"
                className="border-b border-line px-2 py-1 text-left text-[11px] font-bold uppercase text-muted"
              >
                From \ To
              </th>
              {CARDINALS.map((to) => (
                <th
                  key={to}
                  scope="col"
                  className="border-b border-line px-2 py-1 text-center text-[11px] font-bold text-pack"
                >
                  {CARDINAL_LETTER[to]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {CARDINALS.map((from) => (
              <tr key={from}>
                <th
                  scope="row"
                  className="border-b border-line/60 px-2 py-1.5 text-left font-display text-pack"
                >
                  {CARDINAL_LETTER[from]}
                  <span className="ml-1 hidden text-[10px] font-sans font-normal text-muted sm:inline">
                    {CARDINAL_LABEL[from]}
                  </span>
                </th>
                {CARDINALS.map((to) => {
                  const diag = from === to;
                  return (
                    <td
                      key={to}
                      className="border-b border-line/60 px-2 py-1.5 text-center"
                    >
                      {diag ? (
                        <span className="text-muted/30" aria-hidden>
                          ·
                        </span>
                      ) : (
                        <Cell
                          value={countFor(matrix, `${from}->${to}`)}
                          empty={empty}
                        />
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AccessPad({
  from,
  total,
}: {
  from: Cardinal;
  total: number | null;
}) {
  return (
    <div className="rounded border border-line bg-ink/30 px-2 py-3">
      <p className="font-display text-xl font-bold leading-none text-pack">{CARDINAL_LETTER[from]}</p>
      <p className="mt-0.5 text-[10px] uppercase tracking-wide text-muted">
        {CARDINAL_LABEL[from]}
      </p>
      <p className="mt-1 font-display text-2xl font-semibold tabular-nums text-[var(--text)]">
        {total === null ? (
          <span className="text-muted/40">—</span>
        ) : (
          total
        )}
      </p>
    </div>
  );
}
