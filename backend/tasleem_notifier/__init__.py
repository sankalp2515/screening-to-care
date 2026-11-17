"""Notifier service: delivers case-core outbox messages to each person on the channel that fits them.

Patients: Sahatna in-app message first, a content-free SMS nudge second, then a human call task.
Clinicians: a FHIR Task in the EMR inbox they already use; urgent alerts also page by SMS.
Navigators: the Tasleem worklist (their work tool). Coordinators: a daily e-mail digest.
"""
