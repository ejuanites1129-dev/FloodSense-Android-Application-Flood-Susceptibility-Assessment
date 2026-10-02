"""Prepare a synthetic, unpublished expansion for an authorized local rehearsal."""

from datetime import date

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from expert.models import SusceptibilityLevel
from provenance.models import DataSource, PublicationStatus

from dss.models import (
    DSSContentBlock,
    DSSFlowVersion,
    DSSOption,
    DSSOutcome,
    DSSQuestion,
    GuidanceItem,
)
from dss.services import validate_dss_flow

FLOW_CODE = "preparedness"
FLOW_VERSION = "presentation-2"
REFERENCE_DATE = date(2026, 10, 2)
SOURCE_NAME = "FloodSense synthetic preparedness expansion — presentation-2"
SOURCE_LIMITATIONS = (
    "Synthetic, paraphrased interface demonstration pending expert validation. "
    "It is not BDRRMO-authored, BDRRMO-approved, adviser-approved, or official "
    "public guidance. No board transcription or private interview material is "
    "reproduced. FloodSense susceptibility classes are distinct from BDRRMO "
    "alert stages, board water-level markers, and PAGASA rainfall warnings. "
    "This content does not identify an active warning, current flood, safe route, "
    "available center, or evacuation order."
)
ATTRIBUTION = "FloodSense research prototype — synthetic demonstration draft"
SOURCE_VALUES = {
    "organization": "FloodSense research prototype",
    "custodian": "FloodSense research team",
    "source_type": DataSource.SourceType.DEMONSTRATION,
    "coverage_description": "Synthetic household preparedness interface examples.",
    "received_or_created_on": REFERENCE_DATE,
    "version": FLOW_VERSION,
    "permitted_use": "Local development, automated tests, and controlled demonstration review.",
    "limitations": SOURCE_LIMITATIONS,
    "citation_url": "",
    "reviewed_on": None,
    "reviewed_by_id": None,
    "status": PublicationStatus.DEMONSTRATION,
    "is_publicly_releasable": False,
}
FLOW_VALUES = {
    "title": "Household Preparedness Check — Expanded Demonstration",
    "operating_mode": DSSFlowVersion.OperatingMode.DEMONSTRATION,
    "data_status": PublicationStatus.DEMONSTRATION,
    "effective_date": REFERENCE_DATE,
    "reviewed_on": None,
    "expires_on": None,
    "source_locator": "Synthetic expanded household preparedness checklist",
    "attribution": ATTRIBUTION,
    "limitations": SOURCE_LIMITATIONS,
}
WARNING = (
    "DEMONSTRATION — pending expert validation. This is a hypothetical, "
    "scenario-based preparedness assessment. It is not a current flood warning, "
    "forecast, water-level observation, safety guarantee, or evacuation order. "
    "Follow PAGASA, Bacoor DRRMO, your barangay, and emergency services for "
    "official instructions."
)

# Answers stay in the resident client's memory. Each supporting text is part of
# the canonical content, so a recap needs no independently authored Flutter copy.
QUESTIONS = (
    (
        "support-needs",
        "Does anyone in your household need assistance with preparation?",
        "Consider children, older adults, persons with disabilities, pregnant "
        "household members, and people with mobility or communication needs.",
        "Include each person's preferred assistance in your household plan.",
        "Keep a way to ask for help if household needs change.",
    ),
    (
        "trusted-helper",
        "Have you agreed who can provide trusted help if it is needed?",
        "Check whether household members know whom to contact and how to reach them.",
        "Confirm the helper's role and an alternative contact.",
        "Discuss a trusted helper and an alternative contact before an emergency.",
    ),
    (
        "personal-needs",
        "Have medicine, mobility, and communication needs been included in your plan?",
        "Review personal requirements with the household member concerned.",
        "Keep personal requirements accessible to the people providing support.",
        "List personal requirements and discuss how the household can prepare for them.",
    ),
    (
        "supplies-documents",
        "Are essential supplies and important documents ready to review?",
        "Use a household checklist for essentials, identification, and important records.",
        "Review the checklist periodically and check what still needs preparation.",
        "Make a short checklist of missing supplies and important records.",
    ),
    (
        "communication-plan",
        "Does your household have a contact and meeting plan?",
        "Include a way to communicate if normal contact methods are unavailable.",
        "Confirm that everyone can use and understand the contact and meeting plan.",
        "Agree on household contacts, a meeting plan, and an alternative contact method.",
    ),
    (
        "official-channels",
        "Do you know which current official information channels to follow?",
        "Confirm public information channels with the responsible agency or your barangay.",
        "Keep the confirmed official channels available in your household plan.",
        "Ask the responsible agency or barangay to confirm its current public channels.",
    ),
)
OUTCOMES = (
    (
        "review-household-plan",
        "Review your household plan and answers",
        "Use the completed support check to review remaining preparations with your "
        "household. Revisit any item that needs work and keep confirmed official "
        "information channels available. Your answers do not change the scenario's "
        "susceptibility result.",
    ),
    (
        "identify-official-channels",
        "Include confirmed official information channels in your plan",
        "Ask the responsible agency or your barangay which public information "
        "channels are current. Add them to your household contact plan and review "
        "the other support-check answers. This demonstration supplies no contact "
        "numbers, private groups, or unverified links.",
    ),
)
CONTENT = (
    (
        "ALWAYS",
        "SCENARIO_EXPLANATION",
        "RESIDENT",
        "What this scenario may mean",
        "The selected rainfall intensity, duration, and supported location describe "
        "a hypothetical scenario. Use the susceptibility result to discuss preparation; "
        "it does not establish current weather or flooding.",
    ),
    (
        "BEFORE",
        "HOUSEHOLD_ACTION",
        "RESIDENT",
        "Review a go-bag and essential supplies",
        "Make a household checklist of essential items and identify what still needs preparation.",
    ),
    (
        "BEFORE",
        "HOUSEHOLD_ACTION",
        "HOUSEHOLD_SUPPORT",
        "Plan for personal support needs",
        "Discuss medicine, accessibility, mobility, and communication needs with the "
        "person concerned and the trusted people who can help.",
    ),
    (
        "BEFORE",
        "HOUSEHOLD_ACTION",
        "RESIDENT",
        "Keep identification and important records accessible",
        "Review how your household can keep identification and important records "
        "together and protected for preparation.",
    ),
    (
        "BEFORE",
        "HOUSEHOLD_ACTION",
        "RESIDENT",
        "Review phones, lights, and contact methods",
        "Include communication tools and lighting in the household checklist, with an "
        "alternative way to contact trusted people.",
    ),
    (
        "BEFORE",
        "HOUSEHOLD_ACTION",
        "RESIDENT",
        "Agree on household contacts and a meeting plan",
        "Discuss contacts and meeting arrangements that household members can "
        "understand and use. Confirm who can provide trusted help.",
    ),
    (
        "BEFORE",
        "HOUSEHOLD_ACTION",
        "HOUSEHOLD_SUPPORT",
        "Include everyone in the preparation plan",
        "Review assistance with children, older adults, persons with disabilities, "
        "pregnant household members, and people with mobility or communication needs.",
    ),
    (
        "DURING",
        "HOUSEHOLD_ACTION",
        "PUBLIC_REFERENCE",
        "During-flood educational reference",
        "For an actual event, follow instructions from authorized local officials and "
        "emergency services. Do not use this hypothetical assessment to decide whether "
        "a flooded road, bridge, route, or center is safe or available.",
    ),
    (
        "AFTER",
        "HOUSEHOLD_ACTION",
        "PUBLIC_REFERENCE",
        "After-flood educational reference",
        "Ask the responsible authorities for recovery and return instructions. Review "
        "household needs and the support plan using current official information.",
    ),
    (
        "ALWAYS",
        "OFFICIAL_CHANNEL",
        "RESIDENT",
        "Identify official information channels",
        "Confirm current public channels for PAGASA, Bacoor DRRMO, your barangay, "
        "and emergency services with the responsible organization. Local announcements "
        "may use public notices, radio, or direct community communication. No links "
        "or contacts have been verified for this demonstration.",
    ),
    (
        "ALWAYS",
        "MONITORING_REFERENCE",
        "PUBLIC_REFERENCE",
        "What local responders may monitor",
        "Educational references may describe rainfall, waterways, tide, dam level, "
        "road-water observations, gauges, radar, CCTV, and field teams. FloodSense "
        "does not monitor these sources live. Their mention does not confirm equipment "
        "status or a current event.",
    ),
    (
        "BEFORE",
        "AUTHORITY_ACTIVITY",
        "PUBLIC_REFERENCE",
        "What local authorities may coordinate before a flood",
        "Authorities may coordinate preparation of response resources, community "
        "information, and support arrangements. This reference does not confirm "
        "current readiness, resources, or center availability.",
    ),
    (
        "DURING",
        "AUTHORITY_ACTIVITY",
        "PUBLIC_REFERENCE",
        "What local authorities may coordinate during a flood",
        "Authorities may coordinate rescue, medical support, traffic arrangements, "
        "and public information for an actual event. FloodSense does not perform or "
        "dispatch these activities.",
    ),
    (
        "AFTER",
        "AUTHORITY_ACTIVITY",
        "PUBLIC_REFERENCE",
        "What local authorities may coordinate after a flood",
        "Authorities may coordinate needs assessment, recovery support, and public "
        "information. This educational reference does not identify a current recovery phase.",
    ),
    (
        "ALWAYS",
        "RISK_REFERENCE",
        "PUBLIC_REFERENCE",
        "Keep susceptibility and warning systems distinct",
        "FloodSense Low, Moderate, High, and Very High are scenario susceptibility "
        "classes. BDRRMO alert stages, board water-level markers, and PAGASA rainfall "
        "warnings have separate meanings. Matching colors do not establish a mapping "
        "or an active official warning.",
    ),
)


class Command(BaseCommand):
    help = (
        "Create the optional synthetic presentation-2 DSS draft on an authorized "
        "local database. Preserves published versions and never publishes content."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm-local-development",
            action="store_true",
            help="Confirm that the configured target is an authorized local development database.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["confirm_local_development"]:
            raise CommandError(
                "No changes made. Use --confirm-local-development only after confirming "
                "the configured target is an authorized local development database."
            )
        try:
            levels = self._levels()
            source = self._source()
            existing = (
                DSSFlowVersion.objects.select_for_update()
                .filter(code=FLOW_CODE, version=FLOW_VERSION)
                .first()
            )
            if existing:
                self._validate_existing(existing, source, levels)
                self.stdout.write("Existing matching presentation-2 draft preserved.")
            else:
                self._create_flow(source, levels)
                self.stdout.write("Created presentation-2 as an unpublished demonstration draft.")
        except ValidationError as error:
            raise CommandError(f"Draft preparation failed validation: {error}") from error
        self.stdout.write(self.style.WARNING(WARNING))
        self.stdout.write(
            "No existing publication was changed. Review this draft through the "
            "permission-controlled content workflow before a local demonstration. "
            "BDRRMO candidate transcriptions require a separate validation workflow."
        )

    def _levels(self):
        levels = list(SusceptibilityLevel.objects.select_related("source").order_by("code"))
        if {item.code for item in levels} != set(SusceptibilityLevel.Code.values) or any(
            item.status != PublicationStatus.DEMONSTRATION
            or not item.is_enabled
            or item.source.status != PublicationStatus.DEMONSTRATION
            or item.source.source_type != DataSource.SourceType.DEMONSTRATION
            for item in levels
        ):
            raise CommandError(
                "This optional draft requires the four existing enabled demonstration "
                "susceptibility levels. It does not create or modify assessment data."
            )
        return levels

    def _source(self):
        matches = list(DataSource.objects.select_for_update().filter(name=SOURCE_NAME))
        if len(matches) > 1:
            raise CommandError("Multiple sources use the reserved expansion source name.")
        if matches:
            source = matches[0]
            if any(getattr(source, key) != value for key, value in SOURCE_VALUES.items()):
                raise CommandError(
                    "The reserved expansion source differs; no records were overwritten."
                )
            return source
        source = DataSource(name=SOURCE_NAME, **SOURCE_VALUES)
        source.full_clean()
        source.save()
        return source

    def _create_flow(self, source, levels):
        flow = DSSFlowVersion(
            code=FLOW_CODE,
            version=FLOW_VERSION,
            source=source,
            workflow_status=DSSFlowVersion.WorkflowStatus.DRAFT,
            **FLOW_VALUES,
        )
        flow.full_clean()
        flow.save()
        flow.susceptibility_levels.set(levels)
        outcomes = {}
        for code, title, instruction in OUTCOMES:
            outcome = DSSOutcome(
                flow=flow,
                code=code,
                title=title,
                instruction=instruction,
                category=GuidanceItem.Category.PREPARE,
                source=source,
                warning=WARNING,
            )
            outcome.full_clean()
            outcome.save()
            outcomes[code] = outcome
        questions = []
        for order, (code, prompt, explanation, *_support) in enumerate(QUESTIONS, start=1):
            question = DSSQuestion(
                flow=flow,
                code=code,
                prompt=prompt,
                explanatory_text=explanation,
                display_order=order * 10,
                is_start=order == 1,
            )
            question.full_clean()
            question.save()
            questions.append(question)
        for index, question in enumerate(questions):
            for order, answer in enumerate(("yes", "no"), start=1):
                final = index == len(questions) - 1
                option = DSSOption(
                    question=question,
                    code=answer,
                    label="Yes" if answer == "yes" else "Not yet",
                    supporting_text=QUESTIONS[index][2 + order],
                    display_order=order * 10,
                    next_question=None if final else questions[index + 1],
                    outcome=(
                        outcomes[
                            "review-household-plan"
                            if answer == "yes"
                            else "identify-official-channels"
                        ]
                        if final
                        else None
                    ),
                )
                option.full_clean()
                option.save()
        for order, (phase, content_type, audience, title, body) in enumerate(CONTENT, start=1):
            block = DSSContentBlock(
                flow=flow,
                phase=phase,
                content_type=content_type,
                audience=audience,
                title=title,
                body=body,
                display_order=order * 10,
                source=source,
                data_status=PublicationStatus.DEMONSTRATION,
                source_locator=f"Synthetic expanded checklist / item {order}",
                attribution=ATTRIBUTION,
                limitations=SOURCE_LIMITATIONS,
                effective_date=REFERENCE_DATE,
            )
            block.full_clean()
            block.save()
        validate_dss_flow(flow)
        return flow

    def _validate_existing(self, flow, source, levels):
        if (
            flow.source_id != source.pk
            or flow.workflow_status != DSSFlowVersion.WorkflowStatus.DRAFT
            or flow.published_at is not None
            or any(getattr(flow, key) != value for key, value in FLOW_VALUES.items())
            or set(flow.susceptibility_levels.values_list("pk", flat=True))
            != {item.pk for item in levels}
        ):
            raise CommandError(
                "Existing presentation-2 is different or has entered review; it was preserved."
            )
        actual_questions = list(flow.questions.order_by("display_order", "id"))
        if len(actual_questions) != len(QUESTIONS):
            raise CommandError("Existing draft questions differ; no content was overwritten.")
        actual_outcomes = {item.code: item for item in flow.outcomes.all()}
        if set(actual_outcomes) != {item[0] for item in OUTCOMES}:
            raise CommandError("Existing draft outcomes differ; no content was overwritten.")
        for code, title, instruction in OUTCOMES:
            outcome = actual_outcomes[code]
            if (
                outcome.title,
                outcome.instruction,
                outcome.warning,
                outcome.source_id,
                outcome.category,
                outcome.guidance_item_id,
            ) != (title, instruction, WARNING, source.pk, GuidanceItem.Category.PREPARE, None):
                raise CommandError("Existing draft outcomes differ; no content was overwritten.")
        for index, (question, expected) in enumerate(zip(actual_questions, QUESTIONS, strict=True)):
            if (
                question.code,
                question.prompt,
                question.explanatory_text,
                question.display_order,
                question.is_start,
                question.question_type,
            ) != (
                expected[0],
                expected[1],
                expected[2],
                (index + 1) * 10,
                index == 0,
                DSSQuestion.QuestionType.SINGLE_CHOICE,
            ):
                raise CommandError("Existing draft questions differ; no content was overwritten.")
            actual_options = list(question.options.order_by("display_order", "id"))
            if len(actual_options) != 2:
                raise CommandError("Existing draft options differ; no content was overwritten.")
            for answer_index, option in enumerate(actual_options):
                answer = "yes" if answer_index == 0 else "no"
                final = index == len(QUESTIONS) - 1
                next_id = None if final else actual_questions[index + 1].pk
                outcome_id = (
                    actual_outcomes[
                        "review-household-plan" if answer == "yes" else "identify-official-channels"
                    ].pk
                    if final
                    else None
                )
                if (
                    option.code,
                    option.label,
                    option.supporting_text,
                    option.display_order,
                    option.next_question_id,
                    option.outcome_id,
                ) != (
                    answer,
                    "Yes" if answer == "yes" else "Not yet",
                    expected[3 + answer_index],
                    (answer_index + 1) * 10,
                    next_id,
                    outcome_id,
                ):
                    raise CommandError("Existing draft options differ; no content was overwritten.")
        blocks = list(flow.content_blocks.order_by("display_order", "id"))
        if len(blocks) != len(CONTENT):
            raise CommandError("Existing draft content differs; no content was overwritten.")
        for order, (block, expected) in enumerate(zip(blocks, CONTENT, strict=True), start=1):
            values = (block.phase, block.content_type, block.audience, block.title, block.body)
            if values != expected or (
                block.outcome_id is not None
                or block.source_id != source.pk
                or block.data_status != PublicationStatus.DEMONSTRATION
                or block.reference_stage
                or block.display_order != order * 10
                or block.source_locator != f"Synthetic expanded checklist / item {order}"
                or block.attribution != ATTRIBUTION
                or block.limitations != SOURCE_LIMITATIONS
                or block.effective_date != REFERENCE_DATE
                or block.reviewed_on is not None
                or block.expires_on is not None
                or block.public_url
                or block.url_verified_on is not None
            ):
                raise CommandError("Existing draft content differs; no content was overwritten.")
        validate_dss_flow(flow)
