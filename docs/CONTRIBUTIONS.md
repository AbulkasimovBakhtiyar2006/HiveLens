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
- The hosted judging setup: public read-only preview, owner sign-in for writes, and one
  fixed live sample that visitors can run under a shared quota (no uploads or prompts).

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

## The demo video

The [3-minute video](https://www.youtube.com/watch?v=taEsdckX_h4) was edited by the team
during the event (Remotion and FFmpeg). Everything in its HiveLens part is the app built
here: real screen recordings of the running app and figures it produced. Materials the
team did not create, all used under their licences:

- Opening nature footage: Mixkit clips #1879, #4777 and #1705 (Mixkit Stock Video Free
  License) and USDA clips from Wikimedia Commons (public domain, U.S. government works).
- Narration (voice "Marcus K"), background music and meadow sound: generated with
  ElevenLabs on the submitter's account.
- Sticky-board photo IMG_5582 and its annotation: Divasón et al. (2023), CC BY 4.0.
  Comb photo "A slice of the brood nest": Einebillion, CC BY 4.0. Map tiles:
  © OpenStreetMap contributors.
- The pollination fact is quoted from UNEP (2010), *Global Bee Colony Disorders and
  Other Threats to Insect Pollinators*, which the video shows on screen.

Changes after the submission cutoff must be identified separately from the submitted
revision and must not be presented as features built during the event.
