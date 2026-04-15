# User-as-Code Prototype

Research prototype for representing user memory as executable Python code.

## Quick start

```bash
# Run all constraints for Jessica Thompson
python runner.py

# Run tests
python -m pytest jessica_thompson/tests/ -v
```

## Structure

Each user is a self-contained Python project with:

- **manifest.py** -- compact index always loaded into agent context
- **domains/** -- typed dataclass schemas + current state
- **constraints/** -- executable invariants that detect conflicts and safety issues
- **tests/** -- pytest suite validating constraint behavior

## Constraint output

The runner discovers all constraint modules and executes their `check()` functions,
collecting alerts with severity levels (critical / warning / info).
