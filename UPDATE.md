# UPDATE — 2026-09-26

Cleanup pass over the ndlite NMR viewing app, committed as `f34d4f4`
(authored `21tesla`) and pushed to `origin/main`. No functional behavior was
changed for supported formats; the changes remove dead code, fix two latent
bugs, and add missing packaging hygiene.

## 1. Removed duplicate `SettingsDialog` (src/ndlite/ui/main_window.py)

A second copy of `SettingsDialog` existed in `main_window.py` while the live
one lives in `src/ndlite/ui/dialogs.py`. `io_controller.py` imports the
`dialogs.py` version; the `main_window.py` copy was never constructed.

**Why it mattered:** the two had already drifted (the `dialogs.py` copy carries
`help_text`/`HelpDialog`; the `main_window.py` copy is a newer self-contained
table editor). Any future settings edit would need to be made twice or only one
copy gets updated -> silent divergence. Removed the `main_window.py` copy;
`dialogs.py` remains the single owner.

## 2. Removed dead imports in `main_window.py`

Confirmed unused per symbol grep:
- `sys`, `nmrglue`, `json`
- `ssl`, `certifi`, `urllib.request`, `urlopen`, `Request`, `webbrowser`
  (the SSL/GitHub update networking actually lives in `core/updater.py`)
- `scipy.signal.hilbert`, `scipy.optimize.curve_fit`
  (used in `core/data_handler.py`, not here)
- Qt symbols used only by the deleted dialog: `QApplication`, `QScrollArea`,
  `QColorDialog`, `QCheckBox`, `QDialog`, `QTableWidget`, `QTableWidgetItem`,
  `QHeaderView`, `QDialogButtonBox`, `QMouseEvent`, `QAction`, `QPainterPath`,
  `QColor`, `QFont`
- `qInstallMessageHandler`, `QtMsgType`, `QEvent`
- the dead `GLOBAL_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())`
- the unused `PhaseControlWidget` import (never instantiated; the app hand-builds
  `grp_phase` with a `QGridLayout`)

`os` (locale env vars), `QTransform`, `QTimer`, `Qt`, `np`, `pg`, `ng`-dependent
imports retained where still used.

## 3. Fixed silent data loss in `peak_controller.py` `load_peaks()`

The non-`.tab` branch did `import pandas as pd; df = pd.read_csv(...); pass`
— it opened the dialog, parsed *nothing*, then reported success (data gone).
`pandas` is also not a declared dependency in `pyproject.toml`.

Now: `raise ValueError("Unsupported peak file format: only NMRdraw .tab
files are supported.")` — explicit failure instead of silent discard. Removes
the phantom pandas dependency.

## 4. Fixed `remove_spectrum()` active-index bookkeeping (io_controller.py)

`active_index` was not decremented when the removed spectrum sat *above* the
active one, so the pointer could land past the shifted list.

Now: `if index < self.mw.active_index: self.mw.active_index -= 1` before the
index clamp.

## 5. Strengthened flip-axis assertion in `tests/test_overlay.py`

The old check only compared `ppm_x` to `ppm_x_list[0]` — tautological. Now it
captures `ppm_x`/`ppm_y` before `flip_axes()` and asserts they actually *swap*
(`ppm_x == old_y`, `ppm_y == old_x`), plus that the per-spectrum lists
(`ppm_x_list[1]`, `ppm_y_list[1]`) swap too.

## 6. Packaging hygiene

- Added `*.egg-info/` to `.gitignore`; untracked the committed
  `src/ndlite.egg-info/` (editable-install build artifact).
- Added `LICENSE` (MIT) — `pyproject.toml` declares `license = "MIT"` but no
  LICENSE file existed.

## Verification

Ran with the base conda python + `PYTHONPATH=src` (no `ndlite` conda env
exists on this machine; `main.py`'s shebang points at a macOS `/opt/homebrew`
path):

```
PYTHONPATH=src /home/logan/software/anaconda3/bin/python -m pytest tests/ -v
-> 1 passed (26 warnings, all nmrglue numpy-2.0 deprecations)
```

Both edited modules import cleanly and AST-parse validates.

## Not touched (deferred)

- `README.md` shows a Python 3.12 badge while `requires-python = ">=3.10"`
- `main.py` hard-codes `/opt/homebrew/.../miniconda` shebang (author-machine only)
- No CI config, no `pytest.ini`; only one test file
- `FitController` stale `fit_*` keys on re-pick not cleared
