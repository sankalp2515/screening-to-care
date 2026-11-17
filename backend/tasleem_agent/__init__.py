"""Care-team assistant agent (port 8020). Suggest-only by construction.

It reads a case through the case-core API *as the person asking* (their identity is forwarded, so it
sees exactly what they see) and returns drafts: a grounded case brief for the clinician and a
plain-language message for the patient. It holds no credential that can write to a case. A human sends
a draft through the case-core API, which checks the message policy again and records who sent it (R5).
"""
