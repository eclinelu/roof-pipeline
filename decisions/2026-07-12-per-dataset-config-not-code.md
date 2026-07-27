### 2026-07-12: Site-specific numbers live in a per-dataset config file, not in code

**Decision:** Pipeline scripts are dataset-agnostic and take a dataset directory as an argument. All site-specific values (crop box, height cutoff, tuned filter cutoffs) live in `<dataset>\roofkit.json` next to the data. No dataset name appears in any module, script name, or constant.

**Why:** The pipeline must work for any cloud put into it. Site-specific numbers describe a dataset, not the algorithm, so they belong with the dataset. This is the io.py seam principle applied to configuration: swap the dataset, nothing in the code changes. It also keeps the repo holding only code, per the existing workspace split.

**Rejected:** Scripts named after and hardcoded to one dataset (the plan's first draft did this and was caught in review).

**Cost if wrong:** If a knob that is actually algorithmic gets pushed into per-dataset config, every dataset re-tunes something that should have one defended value. The config template documents which knobs are site-specific versus scale-derived to resist this.
