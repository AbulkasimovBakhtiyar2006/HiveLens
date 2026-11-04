# Submission contributions

HiveLens is submitted by Bakhtiyar Abulkassimov (Desert Eagle), Indie Developer track,
for the Meta Global AI Developer Hackathon, 26 October–4 November 2026.
The submission cutoff is 5 November 2026 at 02:00 UTC / 07:00 Almaty
(4 November at 21:00 US Eastern). Local Git timestamps on 5 November before
07:00 Almaty are still before that cutoff. Git history records the implementation.

## What this team built

- The image-analysis pipeline: tiled SAM requests, detection merging, candidate
  filtering, Muse Spark candidate voting, comb tile classification and evidence images.
- Deterministic measurement/status logic and the inspection agent's hypothesis,
  `check_claim`, correction and verified-finding workflow.
- Hive/farm storage, inspection records, exports and recorded evaluation against a
  classical darkness threshold. The README states the evaluation's development overlap.
- The web interface: onboarding, photo capture, evidence review, history, benchmark,
  usage estimates, maps, demo/production separation and research-data browser.
- Transformation and import of the public MUST-B subset, preserving original study
  identities, observation dates, methods and units separately from photo analyses.

The camera feature captures still frames for analysis. It is not real-time tracking,
an autonomous monitoring deployment or a scheduled background sampling service.

## What the team did not create

Meta's model weights/API and mask parser; Python/JavaScript dependencies; public
scientific datasets; Commons photographs/video; map tiles, weather data and fonts.
They retain their respective rights and licenses. Credits are in the README,
`docs/FIELD_DATA.md`, `hivelens/static/comb-demo-LICENSE.md` and
`hivelens/examples/photo-analysis/ATTRIBUTION.md`.

## What the demo demonstrates

The bundled photo record is an actual saved model run on public samples, replayed
without API calls. Its date is the run date, not the photograph date. Demo exposure,
frame count and earlier history are not field measurements. The evidence, model
report and trace are preserved with an explicit provenance notice.

Simulated apiaries are workflow illustrations. MUST-B histories are genuine published
observations collected by the study authors in 2019–2020. Neither is presented as a
HiveLens customer deployment, prospective trial or independent detector validation.

Changes after the submission cutoff must be identified separately from the submitted
revision and must not be presented as features built during the event.
