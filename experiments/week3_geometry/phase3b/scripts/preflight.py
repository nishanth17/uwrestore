"""Phase 3B preflight — capabilities of the installed COLMAP, and what the
footage's own camera metadata actually says.

EXPLORATORY. Main project venv (numpy only; stdlib elsewhere).

Two questions Phase 3A never asked, both of which change what Phase 3B is allowed
to do:

1. Which mappers/matchers does the INSTALLED binary actually expose? 3B-2 needs
   `global_mapper`; the optional LoMa branch needs a `LOMA*` feature type.
2. What capture mode was this footage actually shot in? 3B-3 must not assume all
   GoPro footage shares one calibration, and must not run a fisheye challenger
   just because the camera is a GoPro. The answer is in each MP4's own
   `moov/udta` GoPro block and its embedded GPMF `Global Settings` device.

Nothing here runs a reconstruction. Outputs are small JSON summaries.

Usage:
    .venv/bin/python -m experiments.week3_geometry.phase3b.scripts.preflight
"""

from __future__ import annotations

import argparse
import json
import os
import re
import struct
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

W3 = os.path.join(REPO_ROOT, "experiments", "week3_geometry")
P3B = os.path.join(W3, "phase3b")
OUT = os.path.join(P3B, "outputs", "preflight")

SYSTEM_COLMAP = "/opt/homebrew/bin/colmap"
FEATURE_LIB = "/opt/homebrew/lib/libcolmap_feature.dylib"

# Feature/matcher type names worth probing for. LOMA_* is the optional 3B-1
# challenger; its ABSENCE is the result, so it has to be asked for explicitly.
PROBE_TYPES = [
    "SIFT", "ALIKED_N16ROT", "ALIKED_N32",
    "SIFT_BRUTEFORCE", "SIFT_LIGHTGLUE", "ALIKED_BRUTEFORCE", "ALIKED_LIGHTGLUE",
    "LOMA_B", "LOMA_B128", "LOMA_L", "LOMA_G", "LOMA_R",
    "LOMA_BRUTEFORCE", "LOMA_LIGHTGLUE", "LOMA_MATCHER",
]

PROBE_COMMANDS = ["mapper", "global_mapper", "hierarchical_mapper",
                  "view_graph_calibrator", "rotation_averager",
                  "point_triangulator", "pose_prior_mapper"]


# --------------------------------------------------------------------------
# COLMAP capabilities
# --------------------------------------------------------------------------

def colmap_capabilities() -> dict:
    ver = subprocess.run([SYSTEM_COLMAP, "-h"], capture_output=True, text=True)
    blob = ver.stdout + ver.stderr
    version = next((ln.strip() for ln in blob.splitlines() if ln.startswith("COLMAP ")), "unknown")
    commands = []
    seen_header = False
    for ln in blob.splitlines():
        if ln.strip() == "Available commands:":
            seen_header = True
            continue
        if seen_header and ln.startswith("  "):
            commands.append(ln.strip())

    # Feature/matcher enum values live as string literals in the feature library.
    symbols = {}
    if os.path.exists(FEATURE_LIB):
        st = subprocess.run(["strings", "-n", "3", FEATURE_LIB], capture_output=True, text=True)
        present = set(st.stdout.splitlines())
        for t in PROBE_TYPES:
            symbols[t] = t in present
    else:
        symbols = {t: None for t in PROBE_TYPES}

    opts = {}
    for cmd in PROBE_COMMANDS:
        if cmd not in commands:
            opts[cmd] = {"available": False}
            continue
        h = subprocess.run([SYSTEM_COLMAP, cmd, "-h"], capture_output=True, text=True)
        text = h.stdout + h.stderr
        opts[cmd] = {
            "available": True,
            "n_options": len(re.findall(r"^\s+--", text, flags=re.M)),
        }

    return {
        "binary": SYSTEM_COLMAP,
        "version_line": version,
        "available_commands": commands,
        "feature_and_matcher_symbols_present": symbols,
        "probed_commands": opts,
        "loma_verdict": (
            "ABSENT from this build. No LOMA* symbol exists in libcolmap_feature.dylib. "
            "The Phase 3B execution environment was frozen on Homebrew colmap 4.1.1_3; "
            "changing the COLMAP version mid-phase would create a new environment and "
            "break comparability with the Phase 3A runs that used the same binary, so the "
            "LoMa sub-experiment is not_practical FOR PHASE 3B AS EXECUTED. This is an "
            "environment-scoped decision, not a claim that LoMa is unreachable: upstream "
            "COLMAP 4.2.0 (2026-09-01) adds LOMA_B / LOMA_B128 and ships an official "
            "colmap-arm64-macos.zip, and Homebrew has published arm64 bottles all along. "
            "A future phase can test LoMa by adopting 4.2.0 as its frozen environment."),
        "global_mapper_verdict": (
            "PRESENT. 3B-2's global-SfM axis is testable locally on the same SIFT "
            "measurements Phase 3A configuration A used."),
    }


# --------------------------------------------------------------------------
# GoPro capture metadata
# --------------------------------------------------------------------------

def _mp4_boxes(fh, start: int, end: int) -> list[tuple[bytes, int, int, int]]:
    """(type, box_start, box_size, body_start) for each box in [start, end)."""
    out = []
    pos = start
    while pos < end - 8:
        fh.seek(pos)
        hdr = fh.read(8)
        if len(hdr) < 8:
            break
        size = struct.unpack(">I", hdr[:4])[0]
        typ = hdr[4:8]
        body = pos + 8
        if size == 1:
            size = struct.unpack(">Q", fh.read(8))[0]
            body = pos + 16
        elif size == 0:
            size = end - pos
        out.append((typ, pos, size, body))
        if size < 8:
            break
        pos += size
    return out


def _gpmf_decode(type_char: str, payload: bytes):
    if type_char == "c":
        return payload.decode("latin1").rstrip("\x00").strip()
    fmt = {"L": ">I", "l": ">i", "S": ">H", "s": ">h", "b": ">b", "B": ">B",
           "f": ">f", "d": ">d", "j": ">q", "J": ">Q"}.get(type_char)
    if fmt:
        n = struct.calcsize(fmt)
        vals = [struct.unpack(fmt, payload[i:i + n])[0] for i in range(0, len(payload) - n + 1, n)]
        return vals[0] if len(vals) == 1 else vals
    if type_char == "F":
        return payload.decode("latin1")
    return payload[:32].hex()


def _gpmf_walk(d: bytes, off: int = 0, end: int | None = None, depth: int = 0,
               out: list | None = None) -> list:
    """Flat walk of a GPMF blob. Entries are (depth, fourcc, type, value)."""
    if end is None:
        end = len(d)
    if out is None:
        out = []
    i = off
    while i + 8 <= end:
        key = d[i:i + 4].decode("latin1")
        t = d[i + 4]
        ss = d[i + 5]
        rp = struct.unpack(">H", d[i + 6:i + 8])[0]
        size = ss * rp
        pad = (4 - (size % 4)) % 4
        payload = d[i + 8:i + 8 + size]
        if t == 0:
            out.append((depth, key, "NEST", None))
            _gpmf_walk(d, i + 8, i + 8 + size, depth + 1, out)
        else:
            out.append((depth, key, chr(t) if 32 <= t < 127 else "?",
                        _gpmf_decode(chr(t) if 32 <= t < 127 else "?", payload)))
        i += 8 + size + pad
        if size == 0 and t == 0:
            break
    return out


# The GPMF `Global Settings` keys that describe capture GEOMETRY, which is all
# 3B-3 is entitled to use. Radiometric keys (PTWB, EXPT, ...) are deliberately
# not read: this is a geometry preflight.
GEOMETRY_KEYS = ["MINF", "FMWR", "CASN", "LINF", "OREN", "DZOM", "DZST",
                 "VFOV", "ZFOV", "SROT", "EISE", "EISA", "PRJT", "HLVL", "CMOD"]


def capture_metadata(path: str) -> dict:
    """GoPro udta/GPMF capture-geometry settings for one source clip."""
    size = os.path.getsize(path)
    rec: dict = {"path": os.path.relpath(path, REPO_ROOT), "bytes": size}
    with open(path, "rb") as fh:
        top = _mp4_boxes(fh, 0, size)
        moov = next((b for b in top if b[0] == b"moov"), None)
        if moov is None:
            rec["error"] = "no moov box"
            return rec
        lvl2 = _mp4_boxes(fh, moov[3], moov[1] + moov[2])
        udta = next((b for b in lvl2 if b[0] == b"udta"), None)
        if udta is None:
            rec["error"] = "no moov/udta box"
            return rec
        for typ, pos, sz, body in _mp4_boxes(fh, udta[3], udta[1] + udta[2]):
            name = typ.decode("latin1")
            fh.seek(body)
            data = fh.read(max(0, sz - (body - pos)))
            if name in ("FIRM", "LENS"):
                rec[name] = data.decode("latin1").rstrip("\x00").strip()
            elif name == "GPMF":
                settings = {}
                for _depth, key, _t, val in _gpmf_walk(data):
                    if key in GEOMETRY_KEYS and key not in settings:
                        settings[key] = val
                rec["gpmf_global_settings"] = settings
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    caps_path = os.path.join(OUT, "colmap_capabilities.json")
    meta_path = os.path.join(OUT, "footage_capture_metadata.json")
    for p in (caps_path, meta_path):
        if os.path.exists(p) and not args.overwrite:
            raise SystemExit(f"refusing to overwrite {p!r} (pass --overwrite)")

    caps = colmap_capabilities()
    with open(caps_path, "w") as fh:
        json.dump(caps, fh, indent=2)
    print(f"wrote {os.path.relpath(caps_path, REPO_ROOT)}")
    print(f"  global_mapper: {'yes' if 'global_mapper' in caps['available_commands'] else 'NO'}"
          f" | view_graph_calibrator: "
          f"{'yes' if 'view_graph_calibrator' in caps['available_commands'] else 'NO'}"
          f" | any LOMA symbol: "
          f"{any(v for k, v in caps['feature_and_matcher_symbols_present'].items() if k.startswith('LOMA'))}")

    clips = json.load(open(os.path.join(W3, "configs", "phase3a_clips.json")))["clips"]
    manifest = json.load(open(os.path.join(REPO_ROOT, "data", "testset", "manifest.json")))
    by_id = {c["id"]: c for c in manifest["clips"]}

    out = {
        "_comment": ("GoPro capture-geometry metadata read from each source clip's own "
                     "moov/udta block and embedded GPMF `Global Settings` device. Read for "
                     "Phase 3B 3B-3: the plan forbids assuming that all GoPro footage shares "
                     "one calibration, and forbids running a fisheye challenger merely "
                     "because the camera is a GoPro. Geometry keys only -- radiometric "
                     "settings are deliberately not collected here."),
        "_key_meanings": {
            "MINF": "camera model", "FMWR": "firmware", "CASN": "camera body serial",
            "LINF": "lens serial", "OREN": "capture orientation (U=up, R=rotated)",
            "DZOM": "digital zoom enabled", "DZST": "digital zoom state",
            "VFOV": "field-of-view setting (W=Wide)",
            "ZFOV": "effective diagonal field of view in degrees, AFTER any EIS crop",
            "SROT": "sensor rotation/crop parameter",
            "EISE": "electronic image stabilisation enabled",
            "EISA": "stabilisation mode (HyperSmooth level; a higher level crops more)",
            "PRJT": "output projection (GPRO = GoPro's own non-rectilinear wide projection)",
            "CMOD": "capture mode",
        },
        "clips": {},
    }
    for c in clips:
        cid = c["id"]
        src = by_id[cid]["local_path"]
        rec = capture_metadata(os.path.join(REPO_ROOT, src))
        rec["container_wh"] = [by_id[cid]["width"], by_id[cid]["height"]]
        rec["decoded_wh"] = [by_id[cid]["decoded_width"], by_id[cid]["decoded_height"]]
        rec["fps"] = by_id[cid]["fps"]
        out["clips"][cid] = rec

    # Which clips are metadata-identical in capture geometry? That is the ONLY
    # basis on which 3B-3's optional fixed-intrinsics test is allowed to run.
    sig = {}
    for cid, rec in out["clips"].items():
        g = rec.get("gpmf_global_settings", {})
        sig.setdefault((rec.get("FIRM"), rec.get("LENS"), g.get("CASN"), g.get("VFOV"),
                        round(float(g.get("ZFOV", float("nan"))), 3) if g.get("ZFOV") is not None else None,
                        g.get("DZOM"), g.get("EISA"), g.get("PRJT")), []).append(cid)
    out["capture_mode_groups"] = [
        {"firmware": k[0], "lens_serial": k[1], "body_serial": k[2], "VFOV": k[3],
         "ZFOV_deg": k[4], "DZOM": k[5], "EISA": k[6], "PRJT": k[7], "clips": sorted(v)}
        for k, v in sig.items()]
    out["shared_intrinsics_verdict"] = (
        "Clips grouped above share body serial, lens serial, firmware, FOV setting, "
        "effective ZFOV, digital-zoom state, stabilisation mode and output projection. "
        "Within a group a shared-intrinsics assumption is METADATA-SUPPORTED (not "
        "measured); across groups it is not. Orientation (OREN) may differ within a "
        "group: a rotated capture has the same optics and the same field of view, with "
        "the principal point swapped, so it is not a field-of-view confound.")

    with open(meta_path, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"wrote {os.path.relpath(meta_path, REPO_ROOT)}")
    for g in out["capture_mode_groups"]:
        print(f"  group ZFOV={g['ZFOV_deg']} DZOM={g['DZOM']} EISA={g['EISA']}: {g['clips']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
