# Wicker Park, hand count (QA, 2026-10-26)
Clip: data/transit/wicker_park_intersection.mp4 (30.4 s). Run compared: outputs/demo-real-transito-wicker.
Method: visual review of the video, no SAM and no engine run.

## Key finding
The clip is a drone compilation with jump cuts, black frames and white flashes. Vehicles jump or vanish between cuts,
so "unique count" has no single correct value. 100+ distant parked cars can't be counted.

## Visual count (low/medium confidence)
- car: about 19 crossing the intersection in the top-down shots, about 35 moving in total, about 30-35 stopped nearby
- bus: 3 moving + 2 stopped
- truck: 2 stopped (the engine has no truck class)
- motorcycle: 0 seen (the engine counts 1)
- bicycle: 1 waiting

Movements seen (top=N): S→NW 3, NW→SE 4, N→S 3, E→O 4, O→E 1 (bus), S→N 4, SE→NW 1.

## Against the engine (car 56, motorcycle 1, bus 1 = 58)
Status: NOT VERIFIED. There's no firm ground truth, so no MAE can be given.
Discrepancies: motorcycle 1 vs 0, bus 1 vs 3-5, trucks missing, and the turn matrix doesn't match (E→O 7 vs 4, N→S missing from the engine).
The 56 cars falls inside the plausible range (35 moving + stopped ones) only if it includes stopped vehicles.
