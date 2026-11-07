# Source timestamps and measurement freshness

Freshness uses cloud `data_updated_at`, never the local poll completion time. Only aware ISO timestamps are accepted; offsets and fractional seconds are supported. Timestamps more than 60 seconds ahead are rejected. Missing, malformed and naive times mean unknown freshness. The default threshold is zero/off for all entries, including existing schema-v2 entries with no stale_threshold option. Zero disables freshness availability gating and stale warnings; it does not manufacture a timestamp. Explicit existing thresholds are preserved. An enabled duration must be strictly longer than the polling interval when options are saved. Persisted incompatible combinations are honored as stored, with `freshness_options_compatible: false` in diagnostics. No hidden clamping or threshold inflation occurs. Open options and change the interval or threshold, or disable freshness, to resolve that diagnostic.

| Normalized keys | Source | Semantics |
|---|---|---|
| V3 heart_rate, oxygen_saturation, battery_percentage, battery_minutes, signal_strength, oxygen_10_av, base_station_on, sock_connection, skin_temperature, sleep_state, movement, alert_paused_status, charging, alerts_mask, update_status, readings_flag, brick_status, movement_bucket, wellness_alert, monitoring_start_time, base_battery_status, hardware_version | REAL_TIME_VITALS wrapper | Periodic snapshot; expire each entity from this time |
| V2 heart_rate | HEART_RATE | Independent measurement |
| V2 oxygen_saturation | OXYGEN_LEVEL | Independent measurement |
| V2 battery_percentage | BATT_LEVEL | State when explicit track_only_changes is true; otherwise periodic |
| V2 signal_strength | BLE_RSSI | Independent property |
| V2 movement | MOVEMENT | Independent property |
| V2 charging | CHARGE_STATUS | State when explicit track_only_changes is true; otherwise periodic |
| V2 base_station_on | BASE_STATION_ON | State when explicit track_only_changes is true; otherwise periodic |
| V2 sock_connection | SOCK_CONNECTION | Independent property |
| V2 update_status | OTA_STATUS | Independent property |
| V2 hardware_version | oem_sock_version | Metadata; no sensor currently created |
| base_monitoring_status, battery_status | BASE_MON_STATUS, BATTERY_STATUS respectively | Independent periodic statuses; cannot borrow a vital's newer time |
| Standalone boolean keys listed below | Their own Ayla property | Event/latched state policy; an old event timestamp does not alone expire the state during successful polling |
| red_alert_updated_at | RED_ALERT_SUMMARY.data_updated_at | Property update time, not a decoded clinical event time |
| last_updated | Newest valid heart-rate/oxygen source time | Diagnostic only; does not gate another entity |

Event mapping:

| Normalized key | Ayla property |
|---|---|
| high_oxygen_alert | HIGH_OX_ALRT |
| low_battery_alert | LOW_BATT_ALRT |
| low_heart_rate_alert | LOW_HR_ALRT |
| high_heart_rate_alert | HIGH_HR_ALRT |
| low_oxygen_alert | LOW_OX_ALRT |
| ppg_log_file | PPG_LOG_FILE |
| firmware_update_available | FW_UPDATE_STATUS |
| lost_power_alert | LOST_POWER_ALRT |
| sock_disconnected | SOCK_DISCON_ALRT |
| sock_off | SOCK_OFF |
| critical_battery_alert | CRIT_BATT_ALRT |
| critical_oxygen_alert | CRIT_OX_ALRT |
| discomfort_alert | DISCOMFORT_ALRT |
| low_integrity_reading | LOW_INTEG_READ |
| preview_high_priority_alarm | PREVIEW_HIGH_PRIORITY_ALARM |
| preview_medium_priority_alarm | PREVIEW_MED_PRIORITY_ALARM |
| preview_low_priority_alarm | PREVIEW_LOW_PRIORITY_ALARM |
| preview_drm_priority_alarm | PREVIEW_DRM_PRIORITY_ALARM |

This event policy is conservative about unchanged-event timestamps, not a claim that every cloud event always remains valid indefinitely. A failed poll makes ordinary event entities unavailable. A successful cloud request still cannot prove the base is uploading. Measurement freshness remains visible separately. Unknown flag values produce unknown states rather than false reassurance.

The local expiry timer schedules the nearest future source deadline, then reschedules the remaining deadlines. A repair warning follows the affected heart-rate/oxygen timestamp once it is an hour old, even when battery or the other vital updates. For missing or invalid measurements it uses one hour since that key became unknown, without presenting that local observation time as a measurement time. A valid recovery clears that per-key unknown interval.

With freshness enabled, charging/base-off suppresses expected-vital warnings only until the newest device-output source time reaches the configured age threshold. Source-health candidates are heart rate, oxygen, battery percentage, signal strength, movement, charging, base station state, sock connection, skin temperature, and sleep state. A recent source change is evidence even for a change-only state. Neither a successful HTTP request nor re-reading the same cached state extends suppression. The expiry timer includes this deadline. The state entity itself can remain available as change-only state while the freshness health warns about missing uploads. A quiet healthy V2 device that uploads none of these properties can therefore produce a warning. The API cannot distinguish that case from an offline device; opt-in freshness is deliberately honest about that limitation. Charging-sensitive entities require an explicit decoded noncharging value; legacy observed charging codes 0/1/2 map to off/on/on. Event entities with existing charging exemptions preserve those exemptions.

Only finite numeric values are accepted. Boolean-as-number is rejected. Percentage domains are 0–100; the known oxygen-average 255 sentinel is therefore unknown. No arbitrary heart-rate or temperature cutoffs are applied. Codes outside the known sleep mapping remain unknown. These decisions are based on inspected source and synthetic fixtures, not an independent validation of vendor physiology or live cloud behavior.


## Unmodified V2 capture

The baseline `tests/fixtures/update_properties_v2.json` is unchanged. At its original capture time, 2023-11-20T14:05:01Z, heart rate is 145, oxygen is 99, signal strength is 98, and battery is 29. Oxygen's timestamp is 12:22:26Z and signal strength's is the previous evening. With no stale option, upgrade keeps those measurements available. With a five-minute threshold explicitly enabled, oxygen and signal strength become unavailable and the old oxygen time produces stale health and a repair. Heart rate remains available. No heart-rate timestamp is borrowed to make oxygen look newer.

`track_only_changes: true` describes state availability, not source liveness. This applies to any explicitly marked property. The existing successful-poll and charging rules still apply to each ordinary entity. Missing or malformed explicit vitals remain unknown and cannot be classified healthy merely because the wrapper timestamp advances.
