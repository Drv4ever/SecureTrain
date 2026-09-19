---
id: credential_01
tactic: credential
title: Counterfeit SSO and Identity Gateway Portals
source: MITRE ATT&CK T1566.002 / T1056; SOUPS 2020
technique: Identity Provider Harvesting
---
Adversaries construct pixel-perfect replicas of enterprise Single Sign-On (SSO) login pages (such as Okta, Azure AD, or Ping Identity). The phishing email informs the user that their session has timed out or that identity re-verification is required. Once the user enters their username and password, the page captures the credentials and immediately prompts for MFA codes. Employees must verify browser URL bars for authentic corporate domain roots and utilize FIDO2/WebAuthn hardware tokens resistant to reverse-proxy phishing.
