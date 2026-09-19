---
id: credential_02
tactic: credential
title: Multi-Factor Authentication (MFA) Re-Enrollment Lures
source: CISA Alert AA22-216A; MITRE ATT&CK T1621
technique: MFA Fatigue and Re-Registration
---
This lure alerts employees that the organization is rolling out an updated authenticator app or security key protocol, requiring immediate device re-registration. By clicking the link, the victim is taken to a fraudulent registration portal that captures the user's primary password and prompts them to enter an authenticator push code. Attackers then enroll their own device into the victim's corporate account. Legitimate MFA re-enrollment is managed through designated IT helpdesk protocols.
