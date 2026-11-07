# Bond Wire for Fusion

Creates a wire-bond loop between two points or faces. Pick the die pad, pick the landing pad, set the
wire diameter and loop height, and the add-in builds the wire as a solid body. The shapes follow
EIA/JEDEC Standard No. 59 (JESD59, *Bond Wire Modeling Standard*, 1997); the standard itself is not
included here and can be obtained from JEDEC.

## Install

1. Download this repo (**Code → Download ZIP**, or clone it) and extract it.
2. In Fusion: **Utilities → Add-Ins** (or `Shift+S`) → **Add-Ins** tab → **+** next to *My Add-Ins* →
   select the **`BondWire` folder inside the repo** (not the repo folder itself) → **Run**.
3. The **Bond Wire** button appears in **Solid → Create**.

## Use

1. Open Bond Wire.
2. Pick the **start** point, then the **end** point. The first pick is the ball-bond end (the vertical
   neck, normally the die); the second is the stitch end.
3. Set the options and press OK.

| Option | Meaning |
|---|---|
| Wire diameter | Default 0.025 mm |
| Loop height (h1) | Height of the loop top above the **first pick** (the bond pad), as in JESD59. Must be above both points. Default 0.2 mm |
| Profile | *Smooth curve* (default), *JEDEC 4-point* or *JEDEC 5-point*, see below |
| Pad angle (alpha), Lead angle (beta) | Smooth curve and JEDEC 5-point. Angle of the wire at the bond pad and at the lead. Defaults 90° and 15° |
| Material | Gold, Copper, Aluminum, Silver (Polished appearance, Satin if unavailable) |
| Join wire to | None, Face 1 body, Face 2 body, or Both (this fuses the two bodies into one) |
| Live preview | Builds the wire as you change inputs. Turn off for heavy designs |

**What you can pick:** vertices, construction points, sketch points, faces, edges, sketch curves and
profiles. Circles and arcs resolve to their **center**, lines to their **midpoint**, and planar faces to
their **center** (centroid).

**For reverse bonding** (ball on the substrate, stitch on the die), pick the substrate first.

## Profiles

All profiles lie in the vertical plane through the two points. In JESD59 terms, *d* is the horizontal
distance between them, *h1* is the loop height above the bond pad and *h2* is the height difference to
the lead (the picture in the dialog calls it *dz*).

| Profile | Geometry |
|---|---|
| **Smooth curve** (default) | The rounded version of the 5-point path: a cubic B-spline whose control polygon is the JEDEC 5-point path, so it leaves the pad at *alpha* and lands at *beta*. The crest height is solved so the apex sits exactly at *h1*. Rounding the corners keeps it within about 0.03-0.04 mm (one to two wire diameters) of the standard's polyline for a 0.2 mm loop. |
| **JEDEC 4-point** | The standard's simplified polyline: vertical rise to *h1*, a flat top of *d*/8, then one straight run to the lead. Sharp corners, exact lengths. |
| **JEDEC 5-point** | The standard's preferred polyline with the pad angle *alpha* and lead angle *beta*; the fourth point sits at *d*/2. |

Angle combinations that don't make a valid loop are rejected with a message. With the lead higher than
the bond pad the default *beta* is usually too steep, because the standard's point at *d*/2 would end up
above the loop top; lower *beta*.

The status line shows the path length; for the JEDEC profiles it equals the standard's length sum.
*Smooth* is sampled into a 17-point fitted spline and swept with a pipe.

When the **second pick is a planar face**, the wire is extended straight into the pad and split at the
face, so it ends flat and flush on the face instead of touching at one point.

## Requirements and limits

- **Parametric designs only** (Capture Design History on). Direct-modeling designs are not supported.
- The flush landing needs the second pick to be a **planar face**. Other picks end exactly at the point.
- The JEDEC profiles have sharp corners, so they look blockier than a real wire. Use *Smooth curve*
  when appearance matters more than matching the standard's path exactly.
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
