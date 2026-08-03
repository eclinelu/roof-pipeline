# ODM RUN HEALTH MONITOR AND SUPERVISOR.
#
#   one-shot check:
#     .venv/Scripts/python.exe scripts/monitor_odm.py <odm_log>
#   supervise a live run, checking every 60s and HALTING it on failure:
#     .venv/Scripts/python.exe scripts/monitor_odm.py <odm_log> --watch
#   prove the patterns work:
#     .venv/Scripts/python.exe scripts/monitor_odm.py --self-test
#
# ---------------------------------------------------------------------------
# WHY THIS EXISTS
#
# The 2026-07-30 big_house ultra attempt was reported HEALTHY three times while
# it was already dead. The signals used were CPU near 2500 percent, a climbing
# depth-map file count, and fresh file timestamps. All three were true. All
# three are LIVENESS: they say a process is consuming resources. None of them
# says the run is going to produce a cloud.
#
# What had already happened, in plain text in the log, unread:
#
#     Fused depth-maps 21 (9.01%, 31s, ETA 5m)...Killed
#     [WARNING] OpenMVS ran out of memory, we're going to turn on tiling ...
#
# The OOM kill was at roughly 18:17. Everything watched for the next two hours
# was ODM's tiling FALLBACK, which then segfaulted at 20:27. 130 minutes of
# compute was spent after the run was already lost.
#
# THE RULE THIS ENCODES: liveness is not health, and a busy process that has
# already failed over must never be reported as a healthy first pass.
#
# ---------------------------------------------------------------------------
# WHAT "HEALTHY" MEANS HERE, AND WHAT IT DOES NOT
#
# HEALTHY means: no KNOWN failure signature was found in the log. That is all.
# It is not a statement that the run is correct, that the cloud will be usable,
# or that the reconstruction is good. A novel failure mode, a silent
# degradation, or a subtly wrong result all read as HEALTHY here, because this
# monitor only knows the signatures listed below. Every report says so.
#
# ---------------------------------------------------------------------------
# FIXED INTERVAL, AND THE HALT
#
# Checking "when it seems worth checking" is what failed last time: the judgement
# about when to look was made by the same reasoning that was wrong about what to
# look at. `--watch` therefore polls on a FIXED interval (default 60s),
# independent of any judgement about how the run is going.
#
# WHAT CONSUMES THE EXIT CODE, AND HOW THE HALT HAPPENS:
#
#   one-shot mode  -> the process exit code is the verdict, for a shell or CI
#                     step to consume:  0 HEALTHY, 1 DEGRADED, 2 FAILED,
#                     3 UNKNOWN.
#   --watch mode   -> THE WATCH LOOP ITSELF consumes the verdict. It is the
#                     supervisor. On FAILED it does not merely print: it runs
#                     `docker stop` on the ODM container, verifies the container
#                     is gone, and exits 2. That `docker stop` IS the halt.
#
# So the halt is not advisory and does not depend on a human reading a message.
# A FAILED verdict kills the run within one interval. This is the specific thing
# that would have saved 130 minutes on 2026-07-30.
#
# TILING IS A FAILURE INDICATOR, NOT PROGRESS. ODM enables tiling only after
# OpenMVS has already been killed for running out of memory, so by the time
# `--sub-scene-area` appears a memory failure has already occurred. Tiling is
# reported as DEGRADED, loudly, and per instruction the run is NOT halted for it
# (a fallback may still succeed) but it is never called a healthy first pass.
#
# ---------------------------------------------------------------------------
# THE MEMORY THRESHOLD
#
# Printing used-against-cap is a number, not an alert. Memory pressure is
# actionable only while there is still headroom to act: lowering
# --max-concurrency trades runtime for peak memory and keeps the output at
# ultra, but it has to be decided BEFORE the OOM, not after. So this warns at 85
# percent of cap, and keeps printing the plain number below that.
#
# ---------------------------------------------------------------------------
# THE SELF-TEST (standing rule R4)
#
# A scanner reporting "no failures found" is indistinguishable from one silently
# matching nothing: wrong path, wrong encoding, empty file, patterns that never
# match. That null reads as health, the reassuring direction, which is the
# failure shape this project keeps hitting. So every check asserts a CONTROL
# STRING present in every ODM log. No control, no verdict: UNKNOWN, never
# HEALTHY. `--self-test` additionally runs the scanner against a synthetic log
# carrying each signature and fails loudly if any goes undetected.
# ---------------------------------------------------------------------------
import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HARD = [
    "Killed",
    "out of memory",
    "OOM",
    "Segmentation fault",
    "core dumped",
    "Child returned",
    "SubprocessException",
    "[ERROR]",
]

TILING = [
    "turn on tiling",
    "sub-scene-area",
]

SOFT = ["[WARNING]"]

CONTROL = "Initializing ODM"

# POSITIVE evidence that the run reached the end. `--end-with
# odm_georeferencing` means this stage completing IS the run completing; it is
# also the stage that writes the .laz this pipeline reads.
DONE = ["Finished odm_georeferencing stage"]

NOISY = re.compile(r"\berrors?\b", re.I)

MEM_WARN_PCT = 85.0

HEALTHY_CAVEAT = ("HEALTHY means NO KNOWN FAILURE SIGNATURE WAS FOUND. It is "
                  "not a statement that the run is correct.")

EXIT = {"HEALTHY": 0, "DEGRADED": 1, "FAILED": 2, "UNKNOWN": 3,
        "INTERRUPTED": 4}


def scan(text):
    lines = text.splitlines()
    hits = {k: [] for k in ("hard", "tiling", "soft")}
    for i, ln in enumerate(lines, 1):
        for pat in HARD:
            if pat in ln:
                hits["hard"].append((i, pat, ln.strip()[:160]))
                break
        for pat in TILING:
            if pat in ln:
                hits["tiling"].append((i, pat, ln.strip()[:160]))
                break
        for pat in SOFT:
            if pat in ln:
                hits["soft"].append((i, pat, ln.strip()[:160]))
                break
    noisy = sum(1 for ln in lines if NOISY.search(ln))
    control = CONTROL in text
    if not control:
        verdict = "UNKNOWN"
    elif hits["hard"]:
        verdict = "FAILED"
    elif hits["tiling"]:
        verdict = "DEGRADED"
    else:
        verdict = "HEALTHY"
    return dict(verdict=verdict, control_found=control, n_lines=len(lines),
                hard=hits["hard"], tiling=hits["tiling"], soft=hits["soft"],
                noisy_error_word_lines=noisy,
                completed=any(d in text for d in DONE))


def _to_gb(v, unit):
    f = {"KB": 1e-6, "KiB": 2 ** -20, "MB": 1e-3, "MiB": 2 ** -10,
         "GB": 1.0, "GiB": 1.0, "TB": 1e3, "TiB": 1024.0}
    return round(v * f.get(unit, 1.0), 3)


def _docker(args, timeout=60):
    return subprocess.run(["docker"] + args, capture_output=True, text=True,
                          timeout=timeout)


def find_odm_container():
    """The running ODM container's id, or None."""
    try:
        out = _docker(["ps", "--filter", "ancestor=opendronemap/odm",
                       "--format", "{{.ID}}"]).stdout.strip()
    except Exception:
        return None
    return out.splitlines()[0].strip() if out else None


def container_memory():
    try:
        out = _docker(["stats", "--no-stream", "--format",
                       "{{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}"]
                      ).stdout.strip()
    except Exception as e:
        return dict(available=False, why=f"{type(e).__name__}: {e}")
    if not out:
        return dict(available=False, why="no running containers")
    rows = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        name, usage, pct, cpu = parts[:4]
        m = re.match(r"([\d.]+)\s*([KMGT]i?B)\s*/\s*([\d.]+)\s*([KMGT]i?B)",
                     usage.strip())
        used_gb = cap_gb = None
        if m:
            used_gb = _to_gb(float(m.group(1)), m.group(2))
            cap_gb = _to_gb(float(m.group(3)), m.group(4))
        rows.append(dict(name=name, usage=usage.strip(), mem_pct=pct.strip(),
                         cpu_pct=cpu.strip(), used_gb=used_gb, cap_gb=cap_gb))
    return dict(available=True, containers=rows)


def completion_evidence(logpath, expect_cloud):
    """Two INDEPENDENT positive checks that the run actually finished.

    One is textual (ODM said it finished the stage), one is on the filesystem
    (the artifact that stage writes exists and is non-trivial). Both must hold.
    A log line without a file means ODM claimed something it did not deliver; a
    file without the log line means a stale artifact from an earlier run.
    """
    why = []
    p = Path(logpath)
    said = False
    if p.exists():
        text = p.read_text(encoding="utf-8", errors="replace")
        said = any(d in text for d in DONE)
    why.append(f"log says {DONE[0]!r}: {said}")

    if not expect_cloud:
        why.append("no --expect-cloud given, so the filesystem check is SKIPPED "
                   "and completion rests on the log line alone")
        return said, why
    cp = Path(expect_cloud)
    exists = cp.exists()
    size = cp.stat().st_size if exists else 0
    big = size > 1_000_000
    why.append(f"cloud {cp}: exists={exists} bytes={size:,} (>1MB: {big})")
    return (said and big), why


def halt(container, why):
    """THE HALT. Not advisory: stops the ODM container and verifies it is gone."""
    print(f"  !!! HALTING THE RUN: {why}")
    if not container:
        print("  !!! no ODM container found to stop; it may already be dead.")
        return False
    print(f"  !!! docker stop {container}")
    try:
        r = _docker(["stop", container], timeout=180)
        print(f"  !!! docker stop rc={r.returncode} {r.stdout.strip()}"
              f"{r.stderr.strip()}")
    except Exception as e:
        print(f"  !!! docker stop raised {type(e).__name__}: {e}")
        return False
    still = find_odm_container()
    if still:
        print(f"  !!! VERIFY FAILED: container {still} is STILL RUNNING.")
        return False
    print("  !!! VERIFIED: no ODM container is running. Run halted.")
    return True


def report(logpath, statef, mem_warn_pct):
    """One check. Prints the report, returns (verdict, mem_pct_of_cap|None)."""
    now = datetime.now().strftime("%H:%M:%S")
    p = Path(logpath)
    if not p.exists():
        print(f"[{now}] VERDICT UNKNOWN: log {p} does not exist")
        return "UNKNOWN", None
    r = scan(p.read_text(encoding="utf-8", errors="replace"))
    mem = container_memory()

    peak = 0.0
    if statef.exists():
        try:
            peak = float(json.loads(statef.read_text()).get("peak_gb", 0.0))
        except Exception:
            peak = 0.0
    cur = cap = None
    if mem.get("available"):
        for c in mem["containers"]:
            if c["used_gb"] is not None:
                cur = c["used_gb"] if cur is None else max(cur, c["used_gb"])
                cap = c["cap_gb"]
    if cur is not None and cur > peak:
        peak = cur
        statef.write_text(json.dumps(dict(peak_gb=peak, at=now)))

    mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%H:%M:%S")
    print(f"[{now}] VERDICT {r['verdict']}   "
          f"(log {r['n_lines']:,} lines, last written {mtime})")
    if r["verdict"] == "HEALTHY":
        print(f"  {HEALTHY_CAVEAT}")
    print(f"  control string seen: {r['control_found']}  "
          f"<- if False this monitor is not reading the run and says nothing")

    if r["verdict"] == "FAILED":
        print("  *** THE RUN HAS ALREADY FAILED. This is not a slow stage. ***")
        for i, pat, ln in r["hard"][:8]:
            print(f"    line {i}: [{pat}] {ln}")
    if r["tiling"]:
        print("  *** TILING IS ON. A MEMORY FAILURE HAS ALREADY HAPPENED. ***")
        print("      ODM enables tiling only after OpenMVS was killed for OOM.")
        print("      This run is a FALLBACK ATTEMPT, not a healthy first pass.")
        for i, pat, ln in r["tiling"][:3]:
            print(f"    line {i}: [{pat}] {ln}")
    if r["soft"]:
        print(f"  {len(r['soft'])} [WARNING] line(s), most recent:")
        for i, pat, ln in r["soft"][-3:]:
            print(f"    line {i}: {ln}")
    print(f"  lines containing the word 'error': "
          f"{r['noisy_error_word_lines']} (counted, not escalated)")

    mem_pct = None
    if mem.get("available"):
        for c in mem["containers"]:
            extra = ""
            if c["used_gb"] is not None and c["cap_gb"]:
                pct = 100.0 * c["used_gb"] / c["cap_gb"]
                extra = f"  = {pct:.1f}% of cap"
                mem_pct = pct if mem_pct is None else max(mem_pct, pct)
            print(f"  MEM {c['name']}: {c['usage']} ({c['mem_pct']}){extra}"
                  f"   CPU {c['cpu_pct']}")
        if cap:
            ppct = 100.0 * peak / cap
            print(f"  PEAK observed: {peak:.3f} of {cap:.3f} GiB cap "
                  f"({ppct:.1f}%)")
            if ppct >= mem_warn_pct:
                print(f"  *** MEMORY WARNING: peak {ppct:.1f}% >= "
                      f"{mem_warn_pct:.0f}% of cap. ***")
                print(f"      Rising pressure, and lowering --max-concurrency "
                      f"is still an option WHILE there is headroom. It trades "
                      f"runtime for peak memory and keeps the output at ultra. "
                      f"After an OOM it is too late.")
    else:
        print(f"  MEM unavailable: {mem.get('why')}")

    print("  NOTE: CPU load, file counts and fresh timestamps are LIVENESS, "
          "not health. The verdict above is the health signal.")
    return r["verdict"], mem_pct


def self_test():
    ok = True
    base = "[INFO] Initializing ODM 3.6.0\n"
    cases = [
        ("Killed", "Fused depth-maps 21 (9.01%, 31s, ETA 5m)...Killed", "FAILED"),
        ("out of memory",
         "[WARNING] OpenMVS ran out of memory, we're going to turn on tiling", "FAILED"),
        ("Segmentation fault", "Segmentation fault (core dumped)", "FAILED"),
        ("core dumped", "Segmentation fault (core dumped)", "FAILED"),
        ("Child returned", "Child returned 139", "FAILED"),
        ("[ERROR]", "[ERROR]   Uh oh! Processing stopped", "FAILED"),
        ("sub-scene-area",
         "running DensifyPointCloud scene.mvs --sub-scene-area 660000", "DEGRADED"),
    ]
    print("  SELF-TEST: every pattern must be detected")
    for pat, line, want in cases:
        got = scan(base + line + "\n")["verdict"]
        good = (got == want)
        ok = ok and good
        print(f"    {'PASS' if good else 'FAIL'}  {pat:22s} -> {got:9s} "
              f"(want {want})")
    clean = scan(base + "[INFO] Running dataset stage\n"
                        "[INFO] Reprojection error: 0.42\n")
    good = clean["verdict"] == "HEALTHY"
    ok = ok and good
    print(f"    {'PASS' if good else 'FAIL'}  clean log              -> "
          f"{clean['verdict']:9s} (want HEALTHY)")
    print(f"      (the word 'error' appeared on "
          f"{clean['noisy_error_word_lines']} line(s) and correctly did NOT "
          f"escalate)")
    nc = scan("some text with no ODM banner\nKilled\n")
    good = nc["verdict"] == "UNKNOWN"
    ok = ok and good
    print(f"    {'PASS' if good else 'FAIL'}  no control string      -> "
          f"{nc['verdict']:9s} (want UNKNOWN, never HEALTHY)")
    # The threshold is arithmetic, but assert it rather than trust it.
    for used, cap, want in ((21.0, 24.0, True), (20.0, 24.0, False)):
        got = (100.0 * used / cap) >= MEM_WARN_PCT
        good = (got == want)
        ok = ok and good
        print(f"    {'PASS' if good else 'FAIL'}  mem {used}/{cap} GiB "
              f"({100.0 * used / cap:.1f}%) warn={got} (want {want})")
    # THE 2026-07-30 DEFECT, reproduced. The supervisor printed
    # "no ODM container running; the run has ended. Final verdict HEALTHY."
    # and exited 0 for a run stopped by hand that produced no cloud. A killed
    # run must never be able to exit with a success code.
    import tempfile
    td = Path(tempfile.mkdtemp())
    killed = td / "killed.txt"
    killed.write_text(base + "[INFO] Running openmvs stage\n"
                             "Estimated depth-maps 39 (16.7%)\n")
    finished = td / "finished.txt"
    finished.write_text(base + "[INFO] Finished odm_georeferencing stage\n")
    cloud = td / "model.laz"
    cloud.write_bytes(b"\0" * 2_000_000)
    missing = td / "nope.laz"
    comp_cases = [
        ("killed run, no cloud", killed, cloud, False),
        ("killed run, log only", killed, None, False),
        ("finished, cloud present", finished, cloud, True),
        ("finished, cloud MISSING", finished, missing, False),
        ("finished, log only", finished, None, True),
    ]
    for name, lp, cp, want in comp_cases:
        got, _ = completion_evidence(lp, str(cp) if cp else None)
        good = (got == want)
        ok = ok and good
        print(f"    {'PASS' if good else 'FAIL'}  completion: {name:26s} -> "
              f"{got} (want {want})")
    # And the exit code that carries it must not be a success code.
    good = EXIT["INTERRUPTED"] != 0
    ok = ok and good
    print(f"    {'PASS' if good else 'FAIL'}  INTERRUPTED exit code is "
          f"{EXIT['INTERRUPTED']} (want non-zero)")
    print(f"  SELF-TEST {'PASSED' if ok else 'FAILED'}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logfile", nargs="?")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--watch", action="store_true",
                    help="supervise on a fixed interval and HALT on FAILED")
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument("--mem-warn-pct", type=float, default=MEM_WARN_PCT)
    ap.add_argument("--state", default=None)
    ap.add_argument("--expect-cloud", default=None,
                    help="path the finished run must have written; used as the "
                         "filesystem half of the completion check")
    args = ap.parse_args()

    if args.self_test:
        sys.exit(0 if self_test() else 1)
    if not args.logfile:
        sys.exit("need a logfile (or --self-test)")

    p = Path(args.logfile)
    statef = (Path(args.state) if args.state
              else p.with_suffix(p.suffix + ".peak.json"))

    if not args.watch:
        verdict, _ = report(args.logfile, statef, args.mem_warn_pct)
        sys.exit(EXIT[verdict])

    print(f"SUPERVISING {p.name} every {args.interval:g}s. "
          f"A FAILED verdict HALTS the run via `docker stop`.")
    print(f"Memory warning at {args.mem_warn_pct:.0f}% of cap. "
          f"{HEALTHY_CAVEAT}")
    announced_tiling = False
    while True:
        verdict, _ = report(args.logfile, statef, args.mem_warn_pct)
        if verdict == "FAILED":
            halt(find_odm_container(),
                 "a known failure signature is present in the ODM log")
            print("STOPPING per the pass's stop conditions. Not retrying, not "
                  "raising memory, not falling back to high.")
            sys.exit(EXIT["FAILED"])
        if verdict == "DEGRADED" and not announced_tiling:
            announced_tiling = True
            print("  (continuing under instruction: tiling is reported, not "
                  "halted, but the first pass has already failed)")
        c = find_odm_container()
        if not c:
            # THE CONTAINER VANISHING IS NOT EVIDENCE OF SUCCESS. It is equally
            # consistent with finishing, being killed by hand, and crashing hard
            # enough to take the container with it. Absence of a failure
            # signature must never be promoted to "completed"; that is the
            # null-reads-as-success shape this monitor exists to prevent. So
            # require POSITIVE completion evidence, and say INTERRUPTED when
            # there is none.
            ok, why = completion_evidence(args.logfile, args.expect_cloud)
            now = datetime.now().strftime("%H:%M:%S")
            print(f"[{now}] no ODM container running.")
            for line in why:
                print(f"    {line}")
            if ok:
                print(f"[{now}] RUN COMPLETED. Final verdict {verdict}.")
                sys.exit(EXIT[verdict])
            print(f"[{now}] VERDICT INTERRUPTED: the container is gone but the "
                  f"run did NOT reach the end. No cloud should be assumed.")
            sys.exit(EXIT["INTERRUPTED"])
        print(f"  ... next check in {args.interval:g}s\n", flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
