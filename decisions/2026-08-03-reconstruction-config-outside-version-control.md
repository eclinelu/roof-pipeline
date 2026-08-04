### 2026-08-03: OPEN DEFECT: part of the reconstruction configuration lives OUTSIDE version control, and one success at 95.4 pct of the memory cap does not establish reproducibility

**Defect:** `C:\Users\eclin\.wslconfig` sets `memory=24GB` and `swap=32GB`. On
the evidence of three attempts it is decisive for whether an ultra
reconstruction completes at all, which makes it part of the reconstruction
configuration in the same sense as the ODM version. It is not in the repository,
and it cannot be, because WSL2 requires it at that path outside the project.

The repository therefore **cannot prove what the memory configuration was at
reconstruction time** for any cloud it holds. Confirmed for this entry:
`git ls-files` matches no `wslconfig` path.

**Why this is a defect and not a machine detail.** Every other input to a cloud
is pinned or recorded: the ODM version, the 91 options in `log.json`, the image
set, the stage list. This one is not, and it is not a minor one. The two failed
ultra attempts ran under 15.35 GiB RAM and 4 GiB swap, 19.4 GiB in total, and
both died at 9.01 pct of depth-map fusion. The successful run held **22.390 GiB
resident of a 23.470 GiB cap, 95.4 pct**, together with roughly **12.6 GiB of
swap concurrently**, a working set near **35 GiB**. An instruction to "use
`--pc-quality ultra`" followed on a machine with the old configuration
reproduces the failures, not the cloud. So the repository's description of how
to build the artifact is incomplete in a way that changes the outcome from
success to OOM.

**One success at 95.4 pct of cap does not establish reproducibility.** This is
the part most likely to be misread later, so it is stated flatly. Ultra has
completed **once**. It peaked at 95.4 pct of its RAM cap while also holding 12.6
GiB of swap. That is a **narrow margin, not headroom**. Nothing here shows the
next ultra run will fit, and several ordinary changes could push it over:
a larger image set, a different scene, an ODM version with different fusion
memory behaviour, or other processes holding RAM concurrently. A single
success under a near-ceiling peak is evidence that it CAN work, and is not
evidence that it WILL.

**Partial mitigation already in place, and its limit.** Runtime memory is now
reported by the monitor and quoted into decision entries, so the numbers survive
even though the file does not. That preserves the MEASUREMENT but not the
CONFIGURATION: a quoted peak tells you what the run used, not what the machine
allowed, and only the latter is what a future operator has to set. The gap is
narrowed, not closed.

**POWER CHECK, could this have come out the other way.** Yes, on both halves.
The version-control half is a direct check that could have returned a tracked
copy of the file and did not. The reproducibility half was genuinely at risk of
the opposite finding: had the peak come in at, say, 60 pct of cap, the same
three runs would have supported "ultra fits comfortably under this
configuration" and no margin warning would be warranted. The peak was measured,
not assumed, and 95.4 pct is what the measurement returned. A second successful
ultra run at a comparable peak would strengthen the reliability claim; a second
OOM would refute it outright.

**Cost if wrong:** low. Recording an environment dependency costs nothing and
withdraws no result. The cost of leaving it unrecorded is a cloud nobody can
rebuild, and a reliability assumption nobody knows they are making.

**Options noted, NONE adopted:** copy `.wslconfig` into the repo as a
non-authoritative reference with a note that the live file governs; have the
monitor record the configured cap alongside the observed peak; or state the
requirement in the ODM run procedure. Choosing among these is Emmett's call and
no change is made here.

**Not done here:** `.wslconfig` is not copied, moved or edited, no ODM run is
launched, and no reliability claim is made in either direction beyond what the
single run supports.

**Attribution.** The measurements are from the ultra reconstruction session. The
framing of the configuration gap and the insistence that one near-ceiling
success is not a reliability claim are Emmett's, stated in the task; the
argument that a quoted peak preserves the measurement but not the configuration
is mine.
