# Optional GitHub Project board sync

`setup/project-taxonomy.json` may set `project_board` to either `null` (default) or
an object. When null, create/classify skip Project sync.

## Config shape

```json
"project_board": {
  "owner": "your-org-or-user",
  "number": 1,
  "lane_field": "Lane",
  "lane_option_map": {
    "lane:observability": "Observability",
    "lane:compute": "Compute"
  }
}
```

After a successful create or classify, the wrapper:

1. `gh project item-add <number> --owner <owner> --url <issue-url>`
2. `gh project item-edit ... --field <lane_field> --text <mapped option>`

Agents must not invent Project GraphQL. Extend `setup/platform_harness/project_sync.py`
if your Project needs a different fixed command shape.
