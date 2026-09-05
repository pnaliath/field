V0.18 measured result summary

Render CPU: median ~0.001 ms, p99 ~0.059 ms, max ~0.067 ms. Not the lag source.
Paint cadence: ~15-16 ms (~60 Hz). Not the lag source.
Presence: freezes high when FL input route is not IO_Filled. Silent median presence: route1 ~0.954, route2 ~0.763, route3 ~0.938.
Primary-body paint: route2 onset->draw reached ~5375 ms while onset->presence was 0 ms, indicating FX-return suppression blocked body painting.
First profile learn: ~157-172 ms on new routes; measurable but not multi-second lag.
Spectral occupancy: 537/539 rows claimed 28 Hz-18 kHz occupied; lobe gate is too permissive.
