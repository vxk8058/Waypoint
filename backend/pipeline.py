"""Phase 2 pipeline: generate -> fill Nessie-only fields -> map -> normalize -> validate."""
from dataclasses import dataclass

from .generation.student_generator import generate_all
from .mapping.missing_fields import GeneratedFields, generate_missing_fields
from .mapping.normalize import build_unified_profile
from .mapping.pnc_to_nessie import build_seed_plan
from .schemas.normalized import UnifiedProfile
from .schemas.seed_plan import SeedPlan
from .schemas.student import StudentProfile
from .validation.profile_validator import ValidationReport, validate_profile


@dataclass
class ProfileBundle:
    profile: StudentProfile
    generated: GeneratedFields
    plan: SeedPlan
    unified: UnifiedProfile
    report: ValidationReport


def build_bundle(profile: StudentProfile) -> ProfileBundle:
    generated = generate_missing_fields(profile)
    plan = build_seed_plan(profile, generated)
    unified = build_unified_profile(profile, generated, plan)
    report = validate_profile(profile, plan)
    return ProfileBundle(profile, generated, plan, unified, report)


def build_all() -> list[ProfileBundle]:
    return [build_bundle(p) for p in generate_all()]
