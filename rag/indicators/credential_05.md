---
id: credential_05
tactic: credential
title: Shared Document Permission Prompts
source: MITRE ATT&CK T1566.002
technique: OAuth Consent / Credential Interception
---
This indicator mimics collaboration tools (such as Google Drive, Microsoft OneDrive, or Notion), stating that a colleague or client has shared an encrypted document that requires authentication to view. Upon clicking, the user is presented with a fake login dialog or an OAuth permission consent screen requesting broad read/write mailbox access. Once granted, attackers gain persistent API access without needing the user's password. Users should only access shared documents from within their authenticated app portals.
