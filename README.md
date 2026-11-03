# Supply Chain Optimization Engine

Work in progress. All data is synthetic; every number reported here will be
computed by the code in this repository.

## Status

- [x] v1: synthetic data generator and nearest-warehouse baseline
- [x] v2: transportation LP (PuLP) and fair capacity-aware baseline
- [x] v3: facility-location MILP (which warehouses to open)
- [ ] v4: simulation and sensitivity analysis
- [ ] v5: figures, results, write-up

## Run

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest
python run_stage1.py
python run_stage2.py
python run_stage3.py
```

## Layout

- `src/data.py` : `Instance` dataclass, `build_instance`, `generate_instance`
- `src/baseline.py` : nearest-warehouse plan, fair capacity-aware plan, cost, loads, violations
- `src/lp_model.py` : transportation LP, shadow prices
- `src/milp_model.py` : facility-location MILP (open/close warehouses), cost sweep
- `NOTES.md` : plain-language notes on every concept so far
- `tests/` : hand-checked and invariant tests
- `learning/` : small standalone practice scripts (not part of the engine)
