# Clever API

Unofficial Home Assistant custom integration for Clever subscriptions and home
chargers. This project is not affiliated with or supported by Clever A/S.

The integration follows the API used by the current Clever Android app:

- Firebase email/password authentication and refresh tokens
- Clever mobile backend API v6
- Cloud Firestore live home-charger state and active transactions

## Prerequisite

Create or migrate your Clever account in the official Clever app first. Account
creation, email verification, SMS verification, and CRM claim migration are not
implemented in this integration.

## Installation and login

Install the repository through HACS as a custom repository, restart Home
Assistant, and add **Clever API** from **Settings → Devices & services**.

Enter the email and password used in the Clever app. The password is used for
the initial Firebase login and is not stored in the Home Assistant config entry.
Home Assistant stores the resulting Firebase refresh token, which must be
treated as a sensitive credential.

Existing version 0.2 entries are migrated to the new entry format and prompt
for reauthentication because the former email-link token cannot be converted
to a Firebase refresh token.

## Entities

All accounts expose:

- Energy this month
- Energy surcharge
- Estimated total price this month

Accounts with a home charger additionally expose:

- Energy this month on the home charger
- Energy in the current charging session
- Live charger state
- Intelligent-charging status and configuration attributes
- Preheat switch
- Skip-intelligent-charging (boost) switch

## Actions

- `clever_api.enable_flex` updates required energy and departure time, then
  enables the home charging profile.
- `clever_api.disable_flex` disables the home charging profile.

The legacy `phase_count` input remains accepted for automation compatibility,
but API v6 does not expose a corresponding charging-profile setting.

## Update intervals

Consumption, surcharge, installations, and charging profiles refresh hourly.
Live chargepoint state and transaction documents refresh every minute.

## Limitations

- Only the first home installation is currently represented.
- Monthly consumption is attributed to the month in which a charging session
  started, matching the earlier integration behavior.
- Clever may change the private mobile API without notice.
- Control actions depend on an active and supported Clever home-charging
  profile.

Use this integration at your own risk and comply with the applicable Clever
terms and account policies.
