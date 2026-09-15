# Legacy Majority Is Not Automatically the Standard

## Repository evidence

Most older Java modules issue mapper calls inside entity loops. Newer maintained modules, architecture notes, and regression tests use bounded batch queries and keyed assembly because production incidents traced the older shape to N+1 growth. Compatibility code remains in place for old endpoints.

## Expected judgment

- Do not promote the numerically dominant looped-query shape.
- Promote the established batch-and-assemble positive shape when the evidence supports it.
- Record the old compatibility path as a precise non-propagation boundary rather than a repository-wide rewrite demand.
- Do not ask the Owner merely because positive and legacy code coexist when project evidence already distinguishes them.
