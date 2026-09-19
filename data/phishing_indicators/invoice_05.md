---
id: invoice_05
tactic: invoice
title: Lookalike Vendor Domains (Typosquatting)
source: MITRE ATT&CK T1583.001 / T1566.002
technique: Domain Typosquatting
---
Adversaries register domains nearly identical to genuine corporate suppliers (e.g., substituting 'rn' for 'm' or adding hyphens) to issue counterfeit invoices. Because the email headers closely resemble legitimate suppliers, accounting staff may process payments without noticing subtle spelling differences. Modern billing security relies on automated SPF, DKIM, and DMARC verification alongside human scrutiny of invoice line items. Any change in vendor domain suffix or spelling requires immediate escalation.
