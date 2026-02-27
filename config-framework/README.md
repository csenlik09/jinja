# Config Framework (Planning Scaffold)

This folder defines a data model for interface config generation.
It separates:

- `switch platform behavior` (vendor/model/os, syntax translation only)
- `host behavior` (host type profiles)
- `design variants` (single-link vs dual-link, etc.)
- `row-level overrides` (explicit per-request fields)

Merge priority (highest to lowest):

1. row override (Excel/API row)
2. design profile (`intent_variant`)
3. host profile (`host_type`)
4. host-type defaults (`profiles/platform_defaults.yaml`)

Core flow:

1. Validate input row with `schemas/intent_schema.yaml`.
2. Resolve `platform_id` from `mappings/platform_map.yaml` using API facts.
3. Resolve `profile_id` from `mappings/host_type_map.yaml`.
4. Load host-type defaults and overrides from `profiles/*.yaml`.
5. Apply interface naming and feature translation from `platform/*.yaml`.
6. Select template blocks using `templates/template_catalog.yaml`.
7. Run validation gates from `validation/validation_rules.yaml`.

Switch facts source before external API:

- `mappings/switch_inventory.yaml`
- Supports exact switch entries and regex-based rules.
- Each match can define `platform_id`, `vendor`, `os`, `model`.
