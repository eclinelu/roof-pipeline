# SIGNED PLANE RESIDUALS OF EVERY MAIN FACET, AS AN IMAGE.
#
#   .venv/Scripts/python.exe scripts/render_facet_residuals.py C:/odm/datasets/big_house
#   .venv/Scripts/python.exe scripts/render_facet_residuals.py ... --spectrum
#
# Writes reports/big_house/facet-residuals-<date>.png     (the render, R6)
#        reports/big_house/facet-residuals-<date>.json    (the numbers, R2)
#        reports/big_house/facet-residuals-spectrum-<date>.png  (--spectrum)
#
# READ ONLY on canonical-2026-07-26-r2. Fits no new plane; uses the saved one.
#
# ---------------------------------------------------------------------------
# THE TEST, pre-registered in
# decisions/2026-07-29-preregistration-pitch-bias-mechanism.md
#
# The hypothesis is that the inclinometer read the SHINGLE FACES while the cloud
# sees the whole sawtooth and the plane fit follows the deck, producing a 1.83
# deg systematic offset in the observed direction.
#
# If that is right, the residuals to a single fitted plane are NOT random. They
# are STRIPES PARALLEL TO THE EAVE, alternating in sign, spaced at the shingle
# exposure, with peak-to-peak amplitude equal to the butt thickness.
#
# The cloud can resolve this: median point spacing is 0.21 in and an exposure is
# about 5 in, so a course spans roughly 24 point spacings.
#
# THE RENDER COMES FIRST AND THE SPECTRUM SECOND, deliberately. `--spectrum` is
# a separate flag so the images are read on their own terms before a number is
# attached to them. Standing rule R6: this is a claim about a physical roof
# surface, so it lives or dies on an image.
#
# ---------------------------------------------------------------------------
# PLANE COORDINATES, DEFINED HERE
#
#   n            the facet's saved unit normal
#   EAVE axis    the horizontal direction lying in the plane: normalise(n x Z).
#                An eave is horizontal by construction, and the cloud is
#                LEVELED, so world Z is true vertical and this is well defined.
#   SLOPE axis   n x eave, which completes the frame and points up the slope.
#   residual     (p - centroid) . n, signed, in inches
#
# Stripes from shingle courses must run ALONG THE EAVE AXIS and repeat ALONG THE
# SLOPE AXIS. That is what makes the prediction falsifiable: a periodicity in
# any other direction is not shingle courses.
#
# INDEPENDENT ASSERTIONS (standing rule 2026-07-27):
#   - the eave axis is horizontal to within 1e-9 (its Z component is zero) and
#     lies in the plane (dot with the normal is zero). If either fails, the
#     image is in the wrong frame and any stripe direction read off it is
#     meaningless.
#   - the mean residual is zero to within a tolerance, since residuals are taken
#     to the facet's own fitted plane through its own centroid
#   - the residual RMS reproduces the quality figure stored in the canonical
#     record, which was computed by different code at write time
# ---------------------------------------------------------------------------
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from canonical import load_canonical, scalar                       # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CANONICAL_STAMP = "2026-07-26-r2"
PIX_IN = 0.25              # image cell, inches. Half a point spacing is noise;
                           # 0.25 in gives about 20 cells across a 5 in course.
CLIP_IN = 0.30             # colour limits, inches. Set to the predicted butt
                           # thickness band (3-6 mm = 0.12-0.24 in) plus margin,
                           # so a real sawtooth saturates the map and noise does
                           # not. Fixed before the images were seen.

# THE ZOOM WINDOW, AND WHY IT IS THE ONLY VIEW THAT CAN TEST THE PREDICTION.
#
# The first version of this render drew each facet whole. Those panels span 300
# to 1500 inches and are drawn a few hundred pixels wide, so a 5 inch course is
# AT OR BELOW ONE PIXEL. "No stripes visible" in such an image is a statement
# about the resolution of the figure, not about the roof: it is a guaranteed
# false negative, and it is exactly the shape of silent failure the register
# already tracks (a test structurally blind to the thing it checks).
#
# So the test is run on a WINDOW: 48 x 48 inches at 0.25 in cells is about 190
# pixels square and holds roughly 9 shingle courses. Placed at the DENSEST part
# of the facet's main body, which keeps it away from eaves, dormer cut-outs and
# the M1a strays, all of which carry their own structure at other scales.
WINDOW_IN = 48.0


def frame(normal):
    n = np.asarray(normal, float)
    n = n / np.linalg.norm(n)
    z = np.array([0.0, 0.0, 1.0])
    eave = np.cross(n, z)
    ne = np.linalg.norm(eave)
    if ne < 1e-12:                       # a perfectly flat facet has no eave
        return None
    eave = eave / ne
    slope = np.cross(n, eave)
    return n, eave, slope


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--stamp", default=str(date.today()))
    ap.add_argument("--spectrum", action="store_true")
    args = ap.parse_args()
    name = Path(args.dataset).name
    out = REPO / "reports" / name

    doc, points, facets, cfg = load_canonical(args.dataset, CANONICAL_STAMP)
    spacing = scalar(doc, "spacing_cu")
    in_per_cu = 40.4541
    sc = out / "comparison-2026-07-18-scored-2026-07-18.json"
    if sc.exists():
        in_per_cu = float(json.loads(sc.read_text())["scale"]["in_per_cu"])
    mains = [f for f in facets if f["kind"] == "main"]
    print(f"  point spacing {spacing * in_per_cu:.3f} in   "
          f"image cell {PIX_IN} in   {len(mains)} main facets")

    rows, checks, images = [], [], []
    for f in mains:
        fr = frame(f["normal"])
        pts = np.asarray(f["points"], float)
        c = pts.mean(axis=0)
        n, eave, slope = fr
        d = pts - c
        r_in = (d @ n) * in_per_cu               # signed residual, inches
        u_in = (d @ eave) * in_per_cu            # along the eave
        v_in = (d @ slope) * in_per_cu           # up the slope

        checks.append(dict(
            facet=f["facet"],
            check="eave axis is horizontal and lies in the plane",
            passed=bool(abs(eave[2]) < 1e-9 and abs(eave @ n) < 1e-9),
            detail=dict(eave_z=float(eave[2]), eave_dot_n=float(eave @ n))))
        checks.append(dict(
            facet=f["facet"],
            check="mean residual is zero (residuals are to the facet's own "
                  "plane through its own centroid)",
            passed=bool(abs(float(r_in.mean())) < 1e-6),
            detail=dict(mean_in=float(r_in.mean()))))

        # Place the window at the densest part of the body: coarse-bin at the
        # window size, take the fullest bin. Dense means many points, which
        # means well-captured body rather than a stray trail or a fringe.
        cu = ((u_in - u_in.min()) / WINDOW_IN).astype(np.int64)
        cvv = ((v_in - v_in.min()) / WINDOW_IN).astype(np.int64)
        key = cu * (cvv.max() + 1) + cvv
        best = int(np.argmax(np.bincount(key)))
        bu, bv = divmod(best, cvv.max() + 1)
        u0 = u_in.min() + bu * WINDOW_IN
        v0 = v_in.min() + bv * WINDOW_IN
        sel = ((u_in >= u0) & (u_in < u0 + WINDOW_IN) &
               (v_in >= v0) & (v_in < v0 + WINDOW_IN))

        nu = int(WINDOW_IN / PIX_IN)
        nv = int(WINDOW_IN / PIX_IN)
        iu = np.clip(((u_in[sel] - u0) / PIX_IN).astype(np.int64), 0, nu - 1)
        iv = np.clip(((v_in[sel] - v0) / PIX_IN).astype(np.int64), 0, nv - 1)
        flat = iu * nv + iv
        cnt = np.bincount(flat, minlength=nu * nv).astype(float)
        tot = np.bincount(flat, weights=r_in[sel], minlength=nu * nv)
        img = np.full(nu * nv, np.nan)
        nz = cnt > 0
        img[nz] = tot[nz] / cnt[nz]
        img = img.reshape(nu, nv)
        # Residuals INSIDE the window, re-centred: the facet-wide plane has
        # large-scale structure (sag, fit tilt) that would swamp a 0.15 in
        # sawtooth. Removing the window mean is not fitting anything to the
        # result; it is looking at the right spatial band.
        img = img - np.nanmean(img)
        images.append((f["facet"], img, u0, v0,
                       int(sel.sum()), float(np.nanstd(img))))

        rows.append(dict(
            facet=f["facet"], n_points=int(len(pts)),
            pitch_deg=round(float(f["pitch"]), 4),
            residual_rms_in=round(float(np.sqrt((r_in ** 2).mean())), 5),
            residual_p1_in=round(float(np.percentile(r_in, 1)), 5),
            residual_p99_in=round(float(np.percentile(r_in, 99)), 5),
            extent_along_eave_in=round(float(u_in.max() - u_in.min()), 2),
            extent_up_slope_in=round(float(v_in.max() - v_in.min()), 2),
            image_cells=[int(nu), int(nv)]))

    # RMS against the canonical quality figure, computed by different code
    for r, f in zip(rows, mains):
        want = float(f["quality"]) * spacing * in_per_cu
        checks.append(dict(
            facet=r["facet"],
            check="residual RMS is within 25 pct of quality x spacing recorded "
                  "in the canonical file (the two use different trims, so they "
                  "are not required to match exactly, only to agree in scale)",
            passed=bool(abs(r["residual_rms_in"] - want) < 0.25 * max(want, 1e-9)),
            detail=dict(rms_in=r["residual_rms_in"],
                        quality_x_spacing_in=round(want, 5))))

    # ---- THE RENDER -------------------------------------------------------
    fig, axes = plt.subplots(2, 4, figsize=(19, 10.5))
    for ax, (fid, img, u0, v0, npt, sd) in zip(axes.ravel(), images):
        ext = [0, WINDOW_IN, 0, WINDOW_IN]
        clip = min(CLIP_IN, max(3.0 * sd, 0.02))
        im = ax.imshow(img, origin="lower", extent=ext, cmap="RdBu_r",
                       vmin=-clip, vmax=clip, interpolation="nearest",
                       aspect="equal")
        row = next(r for r in rows if r["facet"] == fid)
        ax.set_title(f"facet {fid}   pitch {row['pitch_deg']:.2f} deg   "
                     f"{npt:,} pts   clip +/-{clip:.3f} in", fontsize=9)
        ax.set_xlabel("UP THE SLOPE (in)", fontsize=8)
        ax.set_ylabel("ALONG THE EAVE (in)", fontsize=8)
        ax.tick_params(labelsize=7)
        # 5 in exposure ticks on the slope axis: if courses are there, the
        # stripes line up with these.
        for xt in np.arange(0, WINDOW_IN + 0.1, 5.0):
            ax.plot([xt, xt], [0, 1.6], color="k", lw=1.0)
        ax.plot([0, 5.0], [WINDOW_IN - 2.5, WINDOW_IN - 2.5], color="k", lw=2.5)
        ax.text(0.5, WINDOW_IN - 5.0, "5 in", fontsize=7)
        fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    fig.suptitle(
        f"SIGNED PLANE RESIDUALS, {WINDOW_IN:.0f} x {WINDOW_IN:.0f} in window "
        f"at the densest part of each main facet body, 0.25 in cells.\n"
        "Sawtooth predicts STRIPES RUNNING VERTICALLY in these panels "
        "(parallel to the eave), repeating every ~5 in along the slope axis "
        "(the horizontal axis), amplitude 0.12 to 0.24 in.\n"
        "Ticks on the bottom axis are at 5 in. Colour is per-panel, clipped at "
        "3 sigma of that window.", fontsize=11)
    png = out / f"facet-residuals-{args.stamp}.png"
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(png, dpi=120, facecolor="white")
    plt.close(fig)

    docout = dict(
        task="signed plane residuals per main facet, in plane coordinates: does "
             "the shingle sawtooth show as stripes?",
        dataset=name, date=args.stamp,
        status="READ ONLY. No plane refitted, nothing adopted.",
        preregistration="decisions/2026-07-29-preregistration-pitch-bias-mechanism.md",
        frame=dict(eave_axis="normalise(n x Z), horizontal and in-plane; the "
                             "cloud is leveled so Z is true vertical",
                   slope_axis="n x eave",
                   residual="(p - centroid) . n, signed, inches"),
        image=dict(cell_in=PIX_IN, colour_clip_in=CLIP_IN, window_in=WINDOW_IN,
                   point_spacing_in=round(float(spacing * in_per_cu), 4),
                   points_per_5in_exposure=round(5.0 / (spacing * in_per_cu), 1)),
        rows=rows, cross_checks=checks, render=png.name)
    p = out / f"facet-residuals-{args.stamp}.json"
    p.write_text(json.dumps(docout, indent=2, default=float))

    print(f"\n{'f':>2} {'pitch':>8} {'RMS in':>9} {'p1 in':>9} {'p99 in':>9} "
          f"{'eave ext in':>12} {'slope ext in':>13}")
    for r in rows:
        print(f"{r['facet']:>2} {r['pitch_deg']:>8.2f} "
              f"{r['residual_rms_in']:>9.4f} {r['residual_p1_in']:>9.4f} "
              f"{r['residual_p99_in']:>9.4f} {r['extent_along_eave_in']:>12.1f} "
              f"{r['extent_up_slope_in']:>13.1f}")
    bad = [c for c in checks if not c["passed"]]
    print(f"\n  {len(checks) - len(bad)}/{len(checks)} checks PASS")
    for c in bad:
        print(f"  CHECK FAIL facet {c['facet']}: {c['check'][:70]}  {c['detail']}")
    print(f"  wrote {png}")
    print(f"  wrote {p}")

    if not args.spectrum:
        print("\n  spectrum NOT computed. Re-run with --spectrum after the "
              "images have been read, per the pre-registration.")
        return

    # =====================================================================
    # THE SPECTRUM, run only after the images have been read.
    #
    # A 2D spectrum, not a 1D profile along the slope. A 1D profile requires
    # averaging along the eave axis, which assumes the courses are EXACTLY
    # parallel to the computed eave direction; a 1 degree misalignment over a
    # 48 in window smears 0.8 in, and over a longer strip it would wash a 5 in
    # period out entirely. The 2D spectrum makes no such assumption: it finds
    # periodicity in ANY direction and reports the direction it found, which is
    # itself part of the test, because shingle courses must repeat ALONG THE
    # SLOPE and not in some other direction.
    #
    # A Hann window is applied first. Without it the sharp edges of a square
    # patch put a cross of spectral leakage through the origin, which lands in
    # exactly the band being tested.
    # =====================================================================
    spec_rows = []
    fig2, axes2 = plt.subplots(2, 4, figsize=(19, 9))
    for ax, (fid, img, u0, v0, npt, sd) in zip(axes2.ravel(), images):
        a = np.nan_to_num(img, nan=0.0)
        a = a - a.mean()
        w = np.hanning(a.shape[0])[:, None] * np.hanning(a.shape[1])[None, :]
        P = np.abs(np.fft.fftshift(np.fft.fft2(a * w))) ** 2
        n0, n1 = a.shape
        f0 = np.fft.fftshift(np.fft.fftfreq(n0, d=PIX_IN))     # cycles/inch
        f1 = np.fft.fftshift(np.fft.fftfreq(n1, d=PIX_IN))
        F0, F1 = np.meshgrid(f0, f1, indexing="ij")
        R = np.hypot(F0, F1)
        with np.errstate(divide="ignore"):
            lam = 1.0 / R                                       # wavelength, in
        band = (lam >= 4.0) & (lam <= 7.0)
        # background: the wavelengths either side of the tested band
        bg = ((lam >= 2.5) & (lam < 4.0)) | ((lam > 7.0) & (lam <= 12.0))
        peak = float(P[band].max()) if band.any() else 0.0
        bgmed = float(np.median(P[bg])) if bg.any() else 1.0

        # THE NAIVE RATIO IS INVALID AND IS KEPT ONLY TO SHOW WHY.
        # These spectra are RED: power rises monotonically with wavelength from
        # 2 in to 12 in. So max(4-7 in) sits at the long-wavelength edge of the
        # band while the median of a flank that INCLUDES 2.5-4 in sits near the
        # bottom of the rise. The ratio then measures the SLOPE OF THE
        # BACKGROUND and returns a large number whether or not a peak exists.
        # It reported 318 on facet 0, which has no peak at all.
        # This is the same failure class as silent-failure rows 7 and 8: a
        # statistic aligned with the structure it is supposed to see past.
        naive_ratio = peak / max(bgmed, 1e-30)

        # THE VALID TEST: fit the background trend in log-log ACROSS the band
        # using only the flanks, then ask whether the band sits ABOVE that
        # trend. A sawtooth is an EXCESS over the local continuum, not a large
        # absolute value.
        def radial_mean(mask_lam_lo, mask_lam_hi, nb=24):
            e = np.geomspace(mask_lam_lo, mask_lam_hi, nb + 1)
            xs, ys = [], []
            for q in range(nb):
                m = (lam >= e[q]) & (lam < e[q + 1])
                if m.any():
                    xs.append(0.5 * (e[q] + e[q + 1]))
                    ys.append(float(P[m].mean()))
            return np.array(xs), np.array(ys)
        lx, ly = radial_mean(2.5, 12.0)
        flank = (lx < 4.0) | (lx > 7.0)
        inband = (lx >= 4.0) & (lx <= 7.0)
        if flank.sum() >= 3 and inband.any():
            cf = np.polyfit(np.log(lx[flank]), np.log(ly[flank]), 1)
            trend = np.exp(np.polyval(cf, np.log(lx[inband])))
            excess_db = float(10.0 * np.log10(
                np.max(ly[inband] / trend)))
            excess_ratio = float(np.max(ly[inband] / trend))
        else:
            excess_db, excess_ratio = 0.0, 1.0
        ratio = excess_ratio
        # where the peak sits, and in what direction
        idx = np.argmax(np.where(band, P, -np.inf))
        i0, i1 = np.unravel_index(idx, P.shape)
        lam_pk = float(lam[i0, i1])
        # angle of the wavevector measured from the SLOPE axis (axis 1 of the
        # image). A shingle course repeats along the slope, so a real course
        # peak has its wavevector along the slope, i.e. angle near 0.
        ang = float(np.degrees(np.arctan2(F0[i0, i1], F1[i0, i1])))
        ang = abs(((ang + 90) % 180) - 90)
        # amplitude of that component, in inches (Parseval-ish, approximate)
        amp = float(2.0 * np.sqrt(peak) / (w.sum()))
        spec_rows.append(dict(
            facet=fid, peak_wavelength_in=round(lam_pk, 3),
            excess_over_trend=round(excess_ratio, 3),
            excess_db=round(excess_db, 2),
            naive_ratio_INVALID=round(naive_ratio, 2),
            wavevector_angle_from_slope_deg=round(ang, 1),
            approx_amplitude_in=round(amp, 5),
            window_sigma_in=round(sd, 5)))
        # radial power profile for the figure
        edges = np.linspace(2.0, 20.0, 60)
        prof = []
        for k in range(len(edges) - 1):
            m = (lam >= edges[k]) & (lam < edges[k + 1])
            prof.append(P[m].mean() if m.any() else np.nan)
        ctr = 0.5 * (edges[:-1] + edges[1:])
        ax.loglog(ctr, prof, lw=1.2)
        if flank.sum() >= 3:
            ax.loglog(lx, np.exp(np.polyval(cf, np.log(lx))), "k--", lw=1.0,
                      label="flank trend")
            ax.legend(fontsize=6)
        ax.axvspan(4.0, 7.0, color="orange", alpha=0.25)
        ax.set_title(f"facet {fid}   excess over trend in 4-7 in = "
                     f"{excess_db:+.1f} dB", fontsize=9)
        ax.set_xlabel("wavelength (in)", fontsize=8)
        ax.set_ylabel("mean power", fontsize=8)
        ax.tick_params(labelsize=7)
    fig2.suptitle(
        "1D RADIAL POWER SPECTRUM of the residual windows. Orange band is the "
        "pre-registered 4 to 7 in shingle-exposure band.\n"
        "A shingle sawtooth would appear as a PEAK inside the orange band with "
        "its wavevector pointing ALONG THE SLOPE.", fontsize=11)
    fig2.tight_layout(rect=[0, 0, 1, 0.90])
    png2 = out / f"facet-residuals-spectrum-{args.stamp}.png"
    fig2.savefig(png2, dpi=120, facecolor="white")
    plt.close(fig2)

    docout["spectrum"] = dict(
        method="2D FFT of the Hann-windowed residual image; peak power in the "
               "pre-registered 4-7 in wavelength band against the median power "
               "in the 2.5-4 and 7-12 in flanks",
        band_in=[4.0, 7.0],
        criterion="a peak-over-background ratio near 1 is NO PEAK. The "
                  "wavevector angle must also be near 0 deg from the slope "
                  "axis, because shingle courses repeat along the slope.",
        rows=spec_rows, render=png2.name)
    p.write_text(json.dumps(docout, indent=2, default=float))
    print(f"\n{'f':>2} {'peak lam in':>12} {'peak/bg':>9} "
          f"{'angle from slope':>17} {'approx amp in':>14}")
    for s in spec_rows:
        print(f"{s['facet']:>2} {s['peak_wavelength_in']:>12.2f} "
              f"{s['excess_db']:>+9.2f} "
              f"{s['wavevector_angle_from_slope_deg']:>17.1f} "
              f"{s['approx_amplitude_in']:>14.5f}")
    print(f"  wrote {png2}")


if __name__ == "__main__":
    main()
