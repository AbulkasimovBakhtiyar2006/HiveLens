# HiveLens visual versions

Two live palettes share the same application and data:

- Forest (original green): http://127.0.0.1:8502/?palette=forest#welcome
- Honey (yellow and white): http://127.0.0.1:8502/?palette=honey#welcome

Use **Settings → Appearance** to choose Honey or Forest. Honey is the default for new visitors. The choice is stored in this browser; an explicit URL parameter takes precedence. No additional model calls or page reload are required when switching. Both palettes use the same compact typography and sidebar icons.

`forest-original/` is a source snapshot of the UI immediately before the Honey version was introduced. It includes the HTML, application scripts, styles and bee SVG. It is a backup, not a separate server; live versions use the existing HiveLens Python server and its image/data APIs. Honey color overrides are scoped to `data-palette="honey"` in `hivelens/static/app.css`.

Status colours and photo annotations retain their meaning in both versions.


## Six interface structures

Open [the comparison gallery](http://127.0.0.1:8502/designs). The six opt-in layouts use `?layout=focus|registry|panorama|notebook|triage|fieldbook`; omit `layout` to keep the current interface. Sources and layout rationale: [STRUCTURE-STUDIES.md](STRUCTURE-STUDIES.md).


## Second set: 07–12

Six additional layouts: `board`, `atlas`, `chronicle`, `workbench`, `folio`, `dispatch`. The comparison gallery opens the new set first, with switches for the original six or all twelve. All twelve are available in the side-by-side selectors.


## Main interface: Atlas

Atlas is the default at `/`. First-time visitors see the introduction; returning visitors can open the overview. Desktop navigation expands on hover or keyboard focus, smoothly resizing the workspace alongside it. Reduced-motion preferences disable the transition. The overview distinguishes measured and demo hives, and groups flagged records under Inspection review. Statuses and stored results are unchanged. The pre-study frontend remains at `/?layout=classic`. Explicit `?layout=...` links retain the comparison toolbar.
