# Development

```bash
git clone https://github.com/ChristophBellmann/ha-radar-occupancy
cd ha-radar-occupancy
pip install -r requirements_test.txt
pytest
ruff check . && ruff format --check .
```

Tests run against `pytest-homeassistant-custom-component`; CI (`validate`)
runs hassfest, HACS validation, ruff and the tests on every push.

## Layout

| File | |
| --- | --- |
| `engine.py` | distance rule, free of Home Assistant imports |
| `tracking.py` | map mode: observations, tracks, doors, counting |
| `geometry.py` | calibration transforms, outlines, sight lines |
| `maps.py` | robot vacuum maps and floor plans, door detection |
| `home.py` | the home: rooms on maps, overview, settings |
| `lights.py` | light controller: entering, leaving, manual off, fades, pre-light |
| `manager.py` | wiring to Home Assistant: entities, listeners, services |
| `radar.py` | sensor suggestions from a radar device |
| `simulation.py`, `simulation_session.py`, `simulation_routes.py` | sandbox, radar model, animated and measured walks, route generation |
| `frontend/radar-occupancy-card.js` | position card |

## Rules

- Change and test here first, push, then install the commit or release in
  your Home Assistant. Host-specific update scripts belong to your own
  configuration repository.
- New behaviour gets a test, preferably a simulated walk; light timing changes
  get a `measure_simulation` comparison.
- Every version gets a changelog entry, a tag `vX.Y.Z` and a GitHub release
  (HACS offers releases).
- The documentation you are reading lives in `docs/` and is published through
  GitBook; update the affected pages with the change.
