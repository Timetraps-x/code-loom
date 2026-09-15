# Tasks Quality Case: Simple Local Correction

## Accepted Spec and Plan Signals

The admin device list shows the existing `ownerCustomerName` value under the wrong label, “使用单位”. The accepted Plan establishes that it is the device owner organization and that only the target admin list heading changes. API field meaning, query, export, customer pages, storage, and the distinct elevator use-unit fact remain unchanged.

## Confirmed Project Facts

- The target template already receives `ownerCustomerName` from the existing list response.
- The target heading is the only incorrect occurrence on that work surface.
- The API, query, export, and customer pages already preserve the accepted owner meaning.
- No write path, state transition, schema, migration, external integration, Job, middleware, transaction, or PlantUML is material.

## Planner Oracle

A strong Tasks candidate is proportionate. It may use one small build packet and one naturally related verify packet, or an equally bounded equivalent. The build result is the corrected heading; its local stop is the target work surface only. The verify result proves the label changed while the displayed value and distinct use-unit meaning did not.

It must not create database, DTO rename, API version, query rewrite, service wrapper, migration, Job, queue, transaction, performance, observability, research, or technical-layer tasks.

## Seeded Bad Candidate

> T1 changes every “使用单位” string in the repository. T2 renames `ownerCustomerName` through every DTO and API. T3 migrates historical data. T4 runs the full test suite.

## Reviewer Oracle

The Reviewer should construct a smallest consumer failure: a global copy replacement changes the separate elevator use-unit fact, while DTO/API/migration work expands an accepted presentation correction without a selected design result. It must not report missing schema, async, performance, diagrams, or an ideal harness as defects in a concise correct candidate.
