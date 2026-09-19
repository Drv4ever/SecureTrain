---
id: invoice_04
tactic: invoice
title: Revised Remittance Advice via Cloud Links
source: MITRE ATT&CK T1566.002
technique: Hosted Malicious Invoice Links
---
Rather than attaching files directly, threat actors embed links to cloud file-sharing services (e.g., SharePoint, OneDrive, Google Drive) claiming to host updated remittance schedules or consolidated billing records. The shared link directs the user to a counterfeit login prompt mimicking Microsoft 365 or Google Workspace. Finance personnel frequently interact with shared vendor documents, making this lure particularly effective. Direct file links from unrecognized or external domains should be inspected cautiously.
