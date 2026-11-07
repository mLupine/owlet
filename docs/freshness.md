# Source timestamps and measurement freshness

Freshness uses cloud `data_updated_at`, never the local poll completion time. Only aware ISO timestamps are accepted; offsets and fractional seconds are supported. Timestamps more than 60 seconds ahead are rejected. Missing, malformed and naive times mean unknown freshness. Threshold zero explicitly disables freshness availability gating; it does not manufacture a timestamp.

| Normalized keys | Source | Semantics |
|---|---|---|
| V3 heart_rate, oxygen_saturation, battery_percentage, battery_minutes, signal_strength, oxygen_10_av, base_station_on, sock_connection, skin_temperature, sleep_state, movement, alert_paused_status, charging, alerts_mask, update_status, readings_flag, brick_status, movement_bucket, wellness_alert, monitoring_start_time, base_battery_status, hardware_version | REAL_TIME_VITALS wrapper | Periodic snapshot; expire each entity from this time |
| V2 heart_rate | HEART_RATE | Independent measurement |
| V2 oxygen_saturation | OXYGEN_LEVEL | Independent measurement |
| V2 battery_percentage | BATT_LEVEL | Independent measurement |
| V2 signal_strength | BLE_RSSI | Independent property |
| V2 movement | MOVEMENT | Independent property |
| V2 charging | CHARGE_STATUS | Independent property |
| V2 base_station_on | BASE_STATION_ON | Independent property |
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

The local expiry timer schedules the nearest future source deadline, then reschedules the remaining deadlines. A repair warning follows the affected heart-rate/oxygen timestamp once it is an hour old, even when battery or the other vital updates. For missing source timestamps it uses one hour since coordinator initialization to schedule the warning, without presenting that local time as a measurement time.

Fresh charging/base-off suppress expected-vital stale warnings. That suppression expires with the source state, avoiding indefinite suppression from an old remembered idle state. Charging-sensitive entities require an explicit decoded noncharging value; legacy observed charging codes 0/1/2 map to off/on/on. Event entities with existing charging exemptions preserve those exemptions.

Only finite numeric values are accepted. Boolean-as-number is rejected. Percentage domains are 0–100; the known oxygen-average 255 sentinel is therefore unknown. No arbitrary heart-rate or temperature cutoffs are applied. Codes outside the known sleep mapping remain unknown. These decisions are based on inspected source and synthetic fixtures, not an independent validation of vendor physiology or live cloud behavior.
