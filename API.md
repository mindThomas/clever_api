# Clever mobile API reference

This is an unofficial, implementation-oriented reference derived from Clever
Android app 26.33.0 and read-only response inspection. Clever does not publish
this as a supported public API and may change it without notice.

No account credentials, bearer tokens, refresh tokens, or captured customer
data belong in this document or in repository fixtures.

## Authentication and transport

- The app signs in through Firebase Identity Toolkit using email and password.
- Subsequent Clever requests use the Firebase ID token as a bearer token.
- ID tokens are renewed through Firebase Secure Token using a refresh token.
- The integration stores the refresh token, never the password.
- Clever REST routes use the mobile backend v6 base URL.
- Live documents come from the `user-database` Firestore database in the
  `clever-app-prod` project, scoped below `v1-user-data/{firebaseUserId}`.
- Mobile app identity/version headers are required by the backend. Their current
  values are implementation details in `clever/clever.py`, not user secrets.

## Handles used by the integration

| Method | Handle | Purpose |
| --- | --- | --- |
| GET | `profiles/get-profile` | Customer/profile identity |
| GET | `installations` | Home charger, connector, model, and capabilities |
| GET | `consumption/history` | Completed charging sessions and energy |
| GET | `energysurcharge/estimated` | Current estimated energy surcharge |
| GET | `chargingprofiles` | Smart-charging configuration |
| PUT | `chargingprofiles/{id}/enable` | Enable or disable a profile |
| PUT | `chargingprofiles/{id}/departure-time` | Set planned departure |
| PUT | `chargingprofiles/{id}/power-required` | Set required energy in kWh |
| PUT | `chargingprofiles/{id}/preheat` | Enable or disable preheating |
| POST | `smartcharging/chargePoints/{chargePointId}/connectors/{connectorId}/boost` | Boost the active session |
| POST | `smartcharging/chargePoints/{chargePointId}/connectors/{connectorId}/timebox-boost` | Timed boost |
| POST | `smartcharging/chargePoints/{chargePointId}/connectors/{connectorId}/unboost` | Cancel boost |
| Firestore | `home-chargepoints` | Live status, last seen, and lock state |
| Firestore | `active-transactions` | Live session, consumption, plan, and vehicle state |

### Active transaction fields

| Field | Meaning | Home Assistant exposure |
| --- | --- | --- |
| `cpmsChargingStatus` | Charging, suspended, completed, or faulted state | Charger state and charging binary sensor |
| `chargingStart` | Session start timestamp | Expected-completion attributes and duration calculation |
| `chargingEnd` | Session end timestamp, when present | Duration calculation |
| `consumedWh` | Energy delivered in the session | Session energy |
| `smartChargingFlow` | Smart-charging strategy | Parsed for future diagnostics |
| `chargingPlan.powerRequiredInKwh` | Expected/target session energy | Target energy and progress |
| `chargingPlan.departureTime` | Planned departure | Expected-completion attributes |
| `chargingPlan.earliestFinishedAt` | Earliest expected completion | Expected completion |
| `chargingPlan.postponedUntil` | Planned charging delay | Expected-completion attributes |
| `chargingPlan.segments[]` | Scheduled start/end, energy, and reason | Boost detection |
| `vehicleStateOfCharge.vehicleChargeState.batteryLevel` | Vehicle battery percentage, when linked | Vehicle battery level |
| `vehicleStateOfCharge.vehicleChargeState.chargeLimit` | Vehicle charge limit | Battery sensor attribute |
| `vehicleStateOfCharge.vehicleChargeState.isPluggedIn` | Vehicle connection state | Connected binary sensor |

The Android transaction model contains no instantaneous power field. The
integration therefore exposes **average session power**, calculated as delivered
kWh divided by elapsed session hours. It is not a current-rate measurement.

## Additional REST handles observed in the Android app

These handles are documented for completeness but are not necessarily used or
safe to expose as Home Assistant actions. State-changing and payment/account
routes require additional review before implementation.

| Method | Handle |
| --- | --- |
| DELETE | `profiles/delete-profile` |
| POST | `profiles/save-profile` |
| GET | `chargingprofiles/{id}` |
| GET | `chargingprofiles/{id}/recommendation` |
| POST | `chargingprofiles/home` |
| POST | `chargingprofiles/network` |
| DELETE | `chargingprofiles/network/{id}` |
| PUT | `chargingprofiles/{id}/happy-hour` |
| POST | `installations/chargepoint/{chargePointId}/connector/{connectorId}/lock` |
| POST | `installations/chargepoint/{chargePointId}/connector/{connectorId}/unlock` |
| GET | `energysurcharge/historical` |
| GET | `subscriptions` |
| GET | `subscriptions/conversions` |
| GET | `favorites/suggestions` |
| POST | `locations/location-ids` |
| POST | `locations/chargepoint-ids` |
| POST | `locations/evse-ids` |
| GET | `tariffs/evses/{evseId}` |
| GET | `tariffs/locations/{locationId}` |
| GET | `electricity-pricing/app-price` |
| GET | `powerconsumption/powerEngagements` |
| GET | `powerconsumption/daily/gsnr/{gsnrId}` |
| GET | `powerconsumption/monthly/gsnr/{gsnrId}` |
| GET | `powerconsumption/yearly/gsnr/{gsnrId}` |
| POST | `stateOfCharge/connect/car` |
| POST | `stateOfCharge/vendor/disconnect` |
| POST | `stateOfCharge/vehicles/interventions` |
| POST | `unified-session/payment/start-session` |
| POST | `unified-session/rfid/start-session` |
| POST | `unified-session/{sessionId}/stop-session` |
| POST | `unified-session/payment/details-session` |
| GET/POST/DELETE | `payments/methods` and `payments/methods/{id}` |
| POST | `transaction-surveys/submit` |
| GET/POST | `marketing/consent/get` and `marketing/consent/store` |
| POST | `device/register` |
| POST | `device/remove` |
| GET | `content/news` |
| GET | `version/verify` |
| POST | `auth/check` |
| GET | `auth/sms-verification` |
| GET | `auth/masked-phone` |
| POST | `auth/add-claim` |
| POST | `auth/create` |
| GET | `auth/passwordrules` |

The `auth/*` account creation, SMS verification, claim migration, and
password-rule handles remain deliberately outside the integration: account
creation and migration must be completed in the official Clever app.
