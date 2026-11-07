# Bond Wire for Fusion

Creates a realistic wire-bond loop between two points or faces. Pick the die pad, pick the landing
pad, set the wire diameter and loop height, and the add-in builds the wire as a solid body.

## Install

1. Download this repo (**Code → Download ZIP**, or clone it) and extract it.
2. **Rename the folder to `BondWire`.** Fusion requires the add-in folder name to match `BondWire.py`,
   and GitHub names the folder after the repo.
3. In Fusion: **Utilities → Add-Ins** (or `Shift+S`) → **Add-Ins** tab → **+** next to *My Add-Ins* →
   select the `BondWire` folder → **Run**.
4. The **Bond Wire** button appears in **Solid → Create**.

## Use

1. Open Bond Wire.
2. Pick the **start** point, then the **end** point. The first pick is the ball-bond end (the vertical
   neck, normally the die); the second is the stitch end.
3. Set the options and press OK.

| Option | Meaning |
|---|---|
| Wire diameter | Default 0.025 mm |
| Loop height (h1) | Apex height above the *higher* of the two points. Default 0.2 mm |
| Material | Gold, Copper, Aluminum, Silver (Polished appearance, Satin if unavailable) |
| Join wire to | None, Face 1 body, Face 2 body, or Both (this fuses the two bodies into one) |
| Live preview | Builds the wire as you change inputs. Turn off for heavy designs |

**What you can pick:** vertices, construction points, sketch points, faces, edges, sketch curves and
profiles. Circles and arcs resolve to their **center**, lines to their **midpoint**, and planar faces to
their **center** (centroid).

**For reverse bonding** (ball on the substrate, stitch on the die), pick the substrate first.

## How the shape is built

A cubic Bezier in the vertical plane through the two points, modelled on the JEDEC 4-point wire:
vertical rise, short crest (D/8), then a straight descent onto the stitch. The apex is solved so it sits
exactly at *h1*. The curve is sampled into an 11-point fitted spline and swept with a pipe.

When the **second pick is a planar face**, the wire is extended straight into the pad and split at the
face's plane, so it ends flat and flush on the face instead of touching at one point.

## Requirements and limits

- **Parametric designs only** (Capture Design History on). Direct-modeling designs are not supported.
- The flush landing needs the second pick to be a **planar face**. Other picks end exactly at the point.
- The add-in temporarily turns on Fusion's *Allow 3D sketching* preference to draw the 3D spline and
  restores your setting afterwards.
- Each wire adds a sketch, a pipe feature, and (when landing on a face) split / remove / delete-face
  features to the timeline.

## Troubleshooting

- **Old icon after an update:** Fusion caches icons for the session. Restart Fusion.
- **Two Bond Wire buttons:** stop the add-in and run it again; a stale button from an earlier crash
  can be left behind.

## License

MIT, see `LICENSE`.
