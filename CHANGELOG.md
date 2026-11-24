# Changelog

## Unreleased

- Add independent read-only app electricity prices with tariff attributes
  (20-minute updates) and published monthly surcharge history (daily updates).
  Keep these separate from charging decision inputs and estimated surcharges.
- Test market request parameters, read-only access, negative/invalid prices,
  timezone-aware intervals and published zero surcharge rates.

- Add read-only client methods for Clever Power agreements and daily, monthly
  and yearly main-meter/charger consumption. Document calendar dates and the
  distinction between total metered energy and household-only consumption.
- Add independent six-hour polling for active electricity meters, monthly and
  latest-published-day household sensors, with timestamped chart attributes.
  Missing current-month data remains unknown; the most recent available day's
  date is explicit. Failures do not mark charging entities unavailable.
- Add offline tests for GET-only access, date formatting, meter path escaping
  and parameter validation. No charging behavior changes.

## 0.4.0 (2026-08-24)
---
 - Expose active charging, vehicle connection, target energy, progress, duration, average power, expected completion, and vehicle battery level.
 - Document the observed Android mobile API and Firestore handles.

## 0.3.2 (2026-08-24)
---
 - Preserve existing entity IDs when migrating legacy entries.
 - Route control actions to a selected Clever account when multiple entries exist.

## 0.3.1 (2026-08-24)
---
 - Fix config-flow loading on Home Assistant 2026.6.

## 0.3.0 (2026-08-23)
---
 - Replace the retired email-link flow with Firebase email/password authentication and refresh-token rotation.
 - Migrate backend requests to Clever mobile API v6.
 - Read live home-charger state and active transactions from Cloud Firestore.
 - Add config-entry migration and reauthentication for existing installations.
 - Add mocked API/model tests and automated linting and compilation checks.

## 0.2.4.2 (2023-05-13)
---
 - Deleted a couple of unused fields in the UserInfoData model because of validation errors for some users. These fields were not at use in the integration.

## 0.2.4 (2023-04-22)
---
 - Reauth using options flow.

## 0.2.3 (2023-04-14)
---
 - Fixed bug where integration was out of function when Intelligent Opladning was disabled (unconfirmed if fixed as I can not reproduce)

## 0.2.2 (2023-04-07)
---
 - Now possible to add integration with intelligent opladning disabled

## 0.2.1 (2023-03-24)
---
 - Now possible to add integration without a homecharger
 - `sensor.clever_estimated_total_price_this_month` is no a combination of subscription fee and energitillæg. The energitillæg price without subscription fee is a attribute
