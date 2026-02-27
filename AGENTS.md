# Project Notes

## Current Product Direction
- Active UI scope is Config Generator only.
- Manage Templates tab removed from UI.
- Jinja Tester tab removed from UI.
- Config generation is YAML-driven (not DB template-name matching).

## Login Section
- Login UI block is intentionally hidden for now.
- Login state logic remains in frontend code for future activation.
- To re-enable later: show `#loginSection` in `templates/index.html`.

## Input Model
- Current Excel columns:
  - `hostname`
  - `host_port`
  - `switch_name`
  - `switch_port`
  - `vlan` (optional)
  - `vip` (optional)

## Switch Facts Before External API
- Use `config-framework/mappings/switch_inventory.yaml`.
- Supports:
  - Exact per-switch facts (`exact_switches`)
  - Regex rules (`regex_rules`)
  - Fallback facts (`default_facts`)

## Git Workflow
- Push all completed changes to the GitHub repository each time.
