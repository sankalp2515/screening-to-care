"""HL7 v2 connector (port 8030): the interface-engine edge of Tasleem.

Facilities and Malaffi speak HL7 v2 (ORU results, REF referrals under DoH Circular 210, SIU scheduling).
The connector parses each message, maps it to FHIR R4 (or to a referral-status message), forwards it to
case-core with the sender's message control id as the idempotency key, and answers with an HL7 ACK.
Parsing untrusted interface traffic happens here, outside the service that holds case data.
"""
