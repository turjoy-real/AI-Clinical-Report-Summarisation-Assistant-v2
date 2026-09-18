// Persistent disclaimer banner — on every page, not only color (icon + text).

import { DISCLAIMER } from "../types";

export default function Disclaimer() {
  return (
    <div
      role="note"
      aria-label="Clinical use disclaimer"
      className="bg-red-700 text-white"
      data-testid="disclaimer-banner"
    >
      <div className="mx-auto flex max-w-6xl items-center justify-center gap-2 px-4 py-2 text-sm font-semibold">
        <span aria-hidden="true">⚠</span>
        <span>
          {DISCLAIMER} Synthetic patients only.
        </span>
      </div>
    </div>
  );
}
