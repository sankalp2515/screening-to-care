"""People and organizations: actor resolution, escalation targets and insurance-network routing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

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
    away_until: str | None = None
    cover_id: str | None = None

    def away(self, now: datetime | None = None) -> bool:
        if not (self.away_until and self.cover_id):
            return False
        until = datetime.fromisoformat(self.away_until)
        until = until if until.tzinfo else until.replace(tzinfo=UTC)  # SQLite drops the zone
        return until > (now or datetime.now(UTC))


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
        data = _person_data(row) if row else {}
        self.cache.set(key, data, DIR_TTL)
        return Person(**data) if data else None

    def require_person(self, pid: str) -> Person:
        p = self.person(pid)
        if p is None:
            raise NotFound("practitioner", pid)
        return p

    def people(self) -> list[Person]:
        rows = self.s.execute(select(PractitionerRow).order_by(PractitionerRow.role, PractitionerRow.id)).scalars()
        return [Person(**_person_data(r)) for r in rows]

    # ---- cover while away (TSL-160) ---------------------------------------------------------------
    def acting_for(self, pid: str, now: datetime | None = None) -> str:
        """Who acts for `pid` right now: the person, or their cover while they are away (followed at most three
        links, never in a circle). Always a named person (R4)."""
        seen = {pid}
        current = pid
        for _ in range(3):
            p = self.person(current)
            if p is None or not p.away(now) or not p.cover_id or p.cover_id in seen:
                return current
            seen.add(p.cover_id)
            current = p.cover_id
        return current

    def covering_for(self, pid: str, now: datetime | None = None) -> list[Person]:
        """People who are away now and named `pid` as their cover: their work shows in `pid`'s list."""
        rows = self.s.execute(select(PractitionerRow).where(PractitionerRow.cover_id == pid)).scalars()
        return [p for p in (Person(**_person_data(r)) for r in rows) if p.away(now)]

    def set_absence(self, pid: str, until: datetime | None, cover_id: str | None) -> Person:
        row = self.s.get(PractitionerRow, pid)
        if row is None:
            raise NotFound("practitioner", pid)
        row.away_until, row.cover_id = (until, cover_id) if until else (None, None)
        self.s.commit()
        data = _person_data(row)
        self.cache.set(f"dir:prac:{pid}", data, DIR_TTL)
        return Person(**data)

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
        return self.acting_for(self._resolve(state, target))

    def _resolve(self, state: CaseState, target: str) -> str:
        if target == "owner":
            return state.owner_id
        if target == "consult_target":
            open_q = sorted((k for k in state.consults.values() if k.answer is None), key=lambda k: k.due_at)
            return open_q[0].to_id if open_q else state.owner_id
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
        """Named person for a playbook role on this case: clinician = the owner if a clinician, else the
        patient's family physician, else a fallback clinician (never a non-clinician owner: found by the AI-user
        run, where a 'done elsewhere' report from a patient with no family physician went to the coordinator);
        navigator = a navigator in the owner's organisation; coordinator = the program coordinator. Falls back to
        the owner (R1/R4)."""
        return self.acting_for(self._for_role(state, role))

    def _for_role(self, state: CaseState, role: str) -> str:
        if role == "clinician":
            return self._resolve(state, "clinician")
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

    def referral_options(self, patient_id: str, service: str | None, prefer_female: bool = False) -> list[dict]:
        """In-network services for the referral. When the patient asked for a female doctor (TSL-165), centres
        with a female endoscopist come first and are marked; the choice stays with the clinician."""
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
                        "networks": r.insurance_networks,
                        "female_endoscopist": "female_endoscopist" in (r.services or [])})
        options = [o for o in out if o["in_network"]]
        if prefer_female:
            options.sort(key=lambda o: not o["female_endoscopist"])
        return options


def _person_data(row: PractitionerRow) -> dict:
    return {"id": row.id, "name": row.name, "role": row.role, "org_id": row.org_id, "lead_id": row.lead_id,
            "away_until": row.away_until.isoformat() if row.away_until else None, "cover_id": row.cover_id}
