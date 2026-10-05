# T001 - Dataset config for the silver corpus

## Objective

Create `configs/dataset/local.yaml`, the first concrete `DatasetConfig`
pointing at `onepiece-faisabilite/data/silver/chapter_NNNN.md`, with an
explicit `field_map` for the YAML front-matter fields named in SPEC §4.

## Context

SPEC §7 states: "**[OPEN]** No dataset config has been written yet
(`configs/dataset/local.yaml` does not exist). This is a required
pre-implementation step, not a research decision." Every other ticket in the
project reads the corpus through this config; it must exist and be correct
before anything else runs.

## Scope

- Add `configs/dataset/local.yaml` with `dataset.path` pointing at the
  silver directory, `dataset.format: markdown_dir`, and `field_map` entries
  for `chapter`, `title`, `jname`, `arc`, `revision_id`, `revised_at`,
  `complete`, `character_count`, `characters`, `source`, `license` (all
  routed into `ChapterRecord.metadata` except `chapter` → `chapter_index`
  and `title` → `title`).
- Add a committed `configs/dataset/local.example.yaml` (the existing
  `DatasetConfig.resolved_path` error message already references this
  filename) documenting every field with a one-line comment.
- Set `dataset.default_book_id` to a fixed value (e.g. `one_piece`) since
  this is explicitly a single continuous narrative (SPEC §1, §4).

## Non-goals

- Do not write the `markdown_dir` loader itself (T002) — this ticket only
  declares the config; `format: markdown_dir` will fail to resolve until
  T002 registers that loader name.
- Do not decide the cover/flashback granularity question (SPEC §26) — map
  the raw `characters` field as-is; T002/T005 handle interpretation.

## Inputs

- `onepiece-faisabilite/data/silver/chapter_0001.md` (and a few more) to
  confirm the real front-matter field names before writing the map.
- `src/ncp/config/schema.py` (`DatasetConfig`, `FieldMap`) — already exists.

## Outputs

- `configs/dataset/local.yaml`
- `configs/dataset/local.example.yaml`

## Acceptance criteria

- `Config.from_dict(yaml.safe_load(open("configs/dataset/local.yaml")))`
  parses without raising `ConfigError`.
- `DatasetConfig.resolved_path()` returns an existing directory.
- Every front-matter field named in SPEC §4 appears in `field_map.metadata`
  or as an explicit mapped field — none are silently dropped.

## Tests

- A config-loading test asserting the YAML parses into `DatasetConfig` with
  the expected `path`, `format`, and `field_map.metadata` contents.
- No data-reading test here (no loader exists yet) — covered by T002/T003.

## Dependencies

None.

## Risks

- None temporal — this ticket touches no chapter content, only path/schema
  configuration. Risk is purely "wrong field name in the map," caught by
  T002's loader tests reading real files against this config.

## Definition of done

- [ ] `configs/dataset/local.yaml` committed, pointing at the real silver
      directory path used in this environment.
- [ ] `configs/dataset/local.example.yaml` committed with path redacted/
      placeholder and every field commented.
- [ ] Config-loading test passes.
- [ ] `ConfigError` is raised (not a crash) on a deliberately malformed
      field map, verified by a negative test.
