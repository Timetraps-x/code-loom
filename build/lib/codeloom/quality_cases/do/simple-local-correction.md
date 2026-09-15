# Do Quality Case: Simple Local Correction

## Frozen Build Packet

The admin device list shows the existing `ownerCustomerName` value under the wrong heading. Change only that heading from “使用单位” to “产权单位”. The field meaning, API response, query, export, customer pages, storage, and the separate elevator use-unit concept remain unchanged.

## Current Project Facts

- The target template already receives the correct value.
- The target heading is the only incorrect occurrence on this work surface.
- No state transition, write path, query change, migration, external integration, transaction, or performance-sensitive path is involved.

## Builder Oracle

A strong Builder inspects the target template and nearby naming, changes the one accepted heading, and runs the smallest focused check that can detect the presentation regression. It does not rename DTO fields, alter APIs, add wrappers, migrate data, redesign the page, or discuss unrelated architecture merely to demonstrate quality.

High quality here means exact scope, correct wording, preservation of the distinct use-unit meaning, and a readable local change—not additional layers or a broad test harness.

## Reviewer Oracle

A strong Reviewer verifies the exact sealed diff changes only the target heading and does not affect the separate use-unit surface. It returns `pass` for a correct candidate and does not manufacture performance, abstraction, database, security, or missing-harness findings.

## Verifier Oracle

A focused verification checks the rendered or source work surface closely enough to prove the heading and value binding remain correct. It does not claim unrelated API, database, export, or end-to-end behavior was tested.
