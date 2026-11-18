"""People and organizations: actor resolution, escalation targets and insurance-network routing."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.errors import NotFound
from ..domain.model import Actor, ActorType, CaseState
from ..infra.cache import Cache
from ..infra.db import OrganizationRow, PatientRow, PractitionerRow

CLINICIAN_ROLES = {"family_physician", "gi_specialist", "clinic_lead"}
ROLE_TO_ACTOR = {
    "family_physician": ActorType.CLINICIAN,
    "gi_specialist": ActorType.CLINICIAN,
    "clinic_lead": ActorType.CLINICIAN,
    "navigator": ActorType.NAVIGATOR,
    "program_coordinator": ActorType.COORDINATOR,
}
DIR_TTL = 300


@dataclass(frozen=True)
class Person:
    id: str
    name: str
    role: str
    org_id: str
    lead_id: str | None


@dataclass(frozen=True)
class PatientInfo:
    id: str
    display_name: str
    preferred_language: str
    insurance_network: str | None
    family_physician_id: str | None
    birth_year: int | None


class Directory:
    def __init__(self, session: Session, cache: Cache) -> None:
        self.s = session
        self.cache = cache

    # ---- practitioners -------------------------------------------------------------------------
    def person(self, pid: str) -> Person | None:
        key = f"dir:prac:{pid}"
        hit = self.cache.get(key)
        if hit is not None:
            return Person(**hit) if hit else None
        row = self.s.get(PractitionerRow, pid)
        data = ({"id": row.id, "name": row.name, "role": row.role, "org_id": row.org_id, "lead_id": row.lead_id}
                if row else {})
        self.cache.set(key, data, DIR_TTL)
        return Person(**data) if data else None

    def require_person(self, pid: str) -> Person:
        p = self.person(pid)
        if p is None:
            raise NotFound("practitioner", pid)
        return p

    def people(self) -> list[Person]:
        rows = self.s.execute(select(PractitionerRow).order_by(PractitionerRow.role, PractitionerRow.id)).scalars()
        return [Person(r.id, r.name, r.role, r.org_id, r.lead_id) for r in rows]

    def coordinator_id(self) -> str:
        key = "dir:coordinator"
        hit = self.cache.get(key)
        if hit:
            return hit
        row = self.s.execute(
            select(PractitionerRow).where(PractitionerRow.role == "program_coordinator").order_by(PractitionerRow.id)
        ).scalars().first()
        if row is None:
            raise NotFound("practitioner", "program_coordinator")
        self.cache.set(key, row.id, DIR_TTL)
        return row.id

    def fallback_clinician_id(self) -> str:
        """A clinician for a case whose owner is not one and whose patient has no family physician (found by the
        real-world-fit run: a distress message from such a patient went to the non-clinical coordinator, who
        cannot resolve it). Order: the coordinator's lead if a clinician, then clinic leads, then family
        physicians, by id. The coordinator only if the directory has no clinician at all."""
        key = "dir:fallback-clinician"
        hit = self.cache.get(key)
        if hit:
            return hit
        coord = self.person(self.coordinator_id())
        lead = self.person(coord.lead_id) if coord and coord.lead_id else None
        pick = lead.id if lead and lead.role in CLINICIAN_ROLES else None
        for role in ("clinic_lead", "family_physician"):
            if pick:
                break
            pick = self.s.execute(select(PractitionerRow.id).where(PractitionerRow.role == role)
                                  .order_by(PractitionerRow.id)).scalars().first()
        pick = pick or self.coordinator_id()
        self.cache.set(key, pick, DIR_TTL)
        return pick

    # ---- patients ------------------------------------------------------------------------------
    def patient(self, pid: str) -> PatientInfo | None:
        row = self.s.get(PatientRow, pid)
        if row is None:
            return None
        return PatientInfo(row.id, row.display_name, row.preferred_language, row.insurance_network,
                           row.family_physician_id, row.birth_year)

    def patients(self) -> list[PatientInfo]:
        rows = self.s.execute(select(PatientRow).order_by(PatientRow.id)).scalars()
        return [PatientInfo(r.id, r.display_name, r.preferred_language, r.insurance_network,
                            r.family_physician_id, r.birth_year) for r in rows]

    # ---- actors --------------------------------------------------------------------------------
    def actor_for(self, ident: str) -> Actor:
        p = self.person(ident)
        if p is not None:
            return Actor(id=p.id, type=ROLE_TO_ACTOR.get(p.role, ActorType.NAVIGATOR))
        if self.patient(ident) is not None:
            return Actor(id=ident, type=ActorType.PATIENT)
        raise NotFound("identity", ident)

    # ---- routing -------------------------------------------------------------------------------
    def default_owner(self, patient: PatientInfo) -> tuple[str, list[str]]:
        """R1: family physician by default; coordinator fallback with a visible warning."""
        if patient.family_physician_id and self.person(patient.family_physician_id):
            return patient.family_physician_id, []
        return self.coordinator_id(), ["No registered family physician: program coordinator owns this case."]

    def resolver(self, state: CaseState, target: str) -> str:
        """Resolve an escalation target to a named person (R4). Always returns someone."""
        if target == "owner":
            return state.owner_id
        if target == "clinic_lead":
            owner = self.person(state.owner_id)
            if owner and owner.lead_id:
                return owner.lead_id
            return self.coordinator_id()
        if target == "program_coordinator":
            return self.coordinator_id()
        if target == "clinician":
            owner = self.person(state.owner_id)
            if owner and owner.role in CLINICIAN_ROLES:
                return owner.id
            pat = self.patient(state.patient_id)
            if pat and pat.family_physician_id:
                return pat.family_physician_id
            return self.fallback_clinician_id()
        return self.coordinator_id()

    def person_for_role(self, state: CaseState, role: str) -> str:
        """Named person for a playbook role on this case: clinician = owner, navigator = a navigator in the
        owner's organisation, coordinator = the program coordinator. Falls back to the owner (R1/R4)."""
        if role == "navigator":
            owner = self.person(state.owner_id)
            if owner is not None:
                key = f"dir:nav:{owner.org_id}"
                hit = self.cache.get(key)
                if hit is None:
                    row = self.s.execute(
                        select(PractitionerRow.id).where(PractitionerRow.role == "navigator",
                                                         PractitionerRow.org_id == owner.org_id)
                        .order_by(PractitionerRow.id)).scalars().first()
                    hit = row or ""
                    self.cache.set(key, hit, DIR_TTL)
                if hit:
                    return hit
            return state.owner_id
        if role == "coordinator":
            return self.coordinator_id()
        return state.owner_id

    def org_members(self, org_id: str) -> list[str]:
        key = f"dir:org:{org_id}"
        hit = self.cache.get(key)
        if hit is None:
            hit = list(self.s.execute(select(PractitionerRow.id).where(PractitionerRow.org_id == org_id)).scalars())
            self.cache.set(key, hit, DIR_TTL)
        return hit

    def referral_options(self, patient_id: str, service: str | None) -> list[dict]:
        pat = self.patient(patient_id)
        if pat is None:
            raise NotFound("patient", patient_id)
        rows = self.s.execute(select(OrganizationRow).order_by(OrganizationRow.name)).scalars()
        out = []
        for r in rows:
            if service and service not in (r.services or []):
                continue
            if not service and r.kind == "program":
                continue
            in_network = pat.insurance_network is not None and pat.insurance_network in (r.insurance_networks or [])
            out.append({"org_id": r.id, "name": r.name, "kind": r.kind, "in_network": in_network,
                        "networks": r.insurance_networks})
        return [o for o in out if o["in_network"]]
