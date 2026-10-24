# Supply Chain Optimization Engine

Work in progress. All data is synthetic; every number reported here will be
computed by the code in this repository.

## Status

- [x] v1: synthetic data generator and nearest-warehouse baseline
- [ ] v2: transportation LP (PuLP)
- [ ] v3: facility-location MILP
- [ ] v4: simulation and sensitivity analysis
- [ ] v5: figures, results, write-up

## Run

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest
python run_stage1.py
```

## Layout

- `src/data.py` : `Instance` dataclass, `build_instance`, `generate_instance`
- `src/baseline.py` : nearest-warehouse plan, cost, loads, capacity violations
- `tests/` : hand-checked and invariant tests
- `learning/` : small standalone practice scripts (not part of the engine)
