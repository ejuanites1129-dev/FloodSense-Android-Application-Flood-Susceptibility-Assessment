from django.db import migrations


REVIEW_NOTICE = (
    "COMPLETE PROTOTYPE DRAFT — requires review and approval by the research "
    "adviser, institution, and qualified privacy/legal personnel before deployment. "
    "This text is not legal advice."
)

TERMS = (
    ("purpose", "Purpose and research scope", "What FloodSense is", "FloodSense is a thesis research prototype for scenario-based flood susceptibility decision support and preparedness awareness in the documented study area. It is not a live monitoring or emergency-response service."),
    ("eligibility", "Eligibility and account responsibility", "Who may create and use an account", "Use is subject to the institutionally approved minimum-age and participant policy. Residents must provide accurate account information, protect sign-in credentials, and promptly report suspected unauthorized use."),
    ("acceptable-use", "Acceptable use", "Use the prototype responsibly", "Residents may use FloodSense for lawful research participation, hypothetical scenario exploration, preparedness learning, and review of source-attributed public information."),
    ("prohibited-use", "Prohibited use", "Activities the service does not permit", "Do not misuse accounts, probe or disrupt security, scrape restricted data, impersonate others, submit unlawful content, interfere with research, or present prototype results as official government information."),
    ("scenario-limitations", "Scenario-based and non-real-time limitations", "Scenarios are hypothetical", "Rainfall intensity and duration are selected by the resident. FloodSense does not continuously monitor rainfall, automatically reassess conditions, track residents in the background, or provide real-time forecasting."),
    ("no-official-order", "No official forecast, warning, or evacuation order", "Outputs are decision-support information", "Susceptibility classifications and DSS guidance are not official forecasts, alerts, emergency instructions, route-safety findings, or evacuation orders."),
    ("official-authorities", "Reliance on official authorities", "Official instructions take priority", "Always follow PAGASA, MGB, Bacoor CDRRMO/LGU, barangay officials, police, fire, medical responders, and other authorized emergency services. Call the appropriate emergency service when immediate help is needed."),
    ("third-parties", "Third-party services and links", "External services have separate terms", "Maps, map tiles, Google authentication, email delivery, and external links may be provided by third parties under their own terms, availability, security, and privacy practices."),
    ("intellectual-property", "Intellectual property", "Respect research and third-party materials", "The prototype interface and research materials may be protected by institutional or author rights. Source datasets, maps, marks, and third-party materials remain subject to their owners’ licenses and attribution requirements."),
    ("availability", "Availability and changes", "Prototype access may change", "The research team may correct, update, suspend, restrict, or discontinue prototype functions for testing, security, governance, data quality, institutional direction, or project completion."),
    ("termination", "Suspension and termination", "Misuse may end access", "Accounts may be limited or deactivated for security, prohibited use, legal or institutional requirements, or withdrawal of prototype availability, subject to applicable review procedures."),
    ("account-deletion", "Account deletion", "Residents may request deletion", "The Account screen may record a deletion request for authorized review. Completion, retention exceptions, research-record handling, and verification of identity remain subject to the approved institutional retention policy."),
    ("disclaimers", "Disclaimers and limitation of liability", "Use requires independent judgment", "Data may be incomplete, provisional, delayed, synthetic, or limited by methodology. To the extent permitted by applicable institutional policy and law, the prototype is provided for research without guarantees of availability, accuracy, or fitness for emergency decisions."),
    ("governing-policy", "Applicable institutional and governing policy", "Final policy must be confirmed", "Use is intended to follow applicable Philippine law, research ethics requirements, university policy, and approved study protocols. The responsible institution, venue, and dispute process must be confirmed before deployment."),
    ("contact", "Contact information", "How to contact the research team", "Prototype placeholder: the responsible researcher, adviser, institution, postal address, and monitored contact email must be inserted and approved before deployment."),
)

PRIVACY = (
    ("operator", "Who operates this prototype", "Research operator details", "FloodSense is operated as a thesis research prototype. The responsible researcher, adviser, institution, data controller role, and approved protocol identifiers must be confirmed before deployment."),
    ("contact", "Contact information", "Privacy questions and requests", "Prototype placeholder: add the monitored privacy contact, institutional office, postal address, and escalation channel approved for the study."),
    ("account-data", "Account data collected", "Username, email, and authentication records", "The system processes a resident username, email address, password hash for password accounts, email-verification state, external identity subject for linked Google accounts, legal acceptances, onboarding acknowledgement, and security-relevant account events. Plain-text passwords are not stored."),
    ("preferences", "Optional preference data", "Resident-controlled defaults", "Residents may save a home barangay, default hypothetical rainfall selections, and accessibility display choices. Preferences do not trigger an assessment and do not store an authoritative current location."),
    ("gps", "Foreground GPS and temporary pin", "Location use is user initiated", "When requested by the resident, the app obtains a foreground position to resolve supported geography and request nearby-center ordering. The precise coordinate and temporary red pin are not account preferences and are cleared with temporary session state. No background location tracking is used."),
    ("assessment", "Assessment and scenario selections", "Inputs used for deterministic classification", "The selected hypothetical intensity, duration, and confirmed supported area are sent to the server to calculate a deterministic susceptibility result from controlled data and rules. The approved retention design for assessment events must be confirmed before deployment."),
    ("dss", "DSS answers", "Branch answers are not stored by default", "Structured DSS selections are used in the current app session to choose deterministic preparedness guidance. The stateless API does not persist resident answer history by default, and DSS answers cannot change the Expert System classification."),
    ("logs", "Device, error, and security logging", "Limited operational records", "The service may record minimal server, error, authentication, throttling, and security information needed to operate and protect the prototype. Logs must not include passwords, reset or verification tokens, Google ID tokens, JWTs, or precise GPS coordinates."),
    ("purposes", "Purposes for processing", "Why information is used", "Information supports account access, verification, setup gating, scenario assessment, preference application, deterministic guidance, security, debugging, research administration, legal compliance, and approved evaluation of the prototype."),
    ("basis", "Legal and institutional basis", "Approval still requires confirmation", "The appropriate consent, legitimate research, institutional, contractual, or legal basis under the approved study protocol and Philippine requirements must be confirmed and documented before participant deployment."),
    ("retention", "Data retention", "Retention periods require approval", "Account and research-related records are retained only for the approved period and purpose, then deleted, anonymized, or archived as authorized. Exact periods, backup handling, legal holds, and deletion exceptions must be inserted after institutional approval."),
    ("providers", "Service providers and third parties", "Limited disclosure for operation", "Data may be processed by authorized hosting, database, security, email, mapping, and authentication providers only as needed to deliver the prototype and under reviewed agreements or provider terms. The final provider list must be documented."),
    ("google", "Google authentication", "Optional federated sign-in", "If selected, the backend verifies a short-lived Google ID token and stores Google’s immutable subject identifier plus the last verified email. FloodSense does not automatically link an existing password account merely because email strings match."),
    ("maps", "Map and tile providers", "Map requests may reach third parties", "Displaying base maps or tiles may disclose ordinary network and device request information to the configured map provider. Provider attribution and privacy terms remain applicable; the final production provider must be identified."),
    ("email-provider", "Email delivery provider", "Verification and reset delivery", "The configured provider processes the destination email and message-delivery metadata for verification and password reset. Local development uses console output; the production provider and retention terms require approval."),
    ("security", "Security measures", "Safeguards reduce but do not eliminate risk", "Controls include password hashing, short-lived access tokens, refresh-token revocation, secure Android storage for remembered refresh tokens, one-time expiring links, access control, HTTPS requirements, throttling, validation, and source-governed content."),
    ("rights", "Access, correction, deletion, and other rights", "Residents may submit privacy requests", "Subject to verified identity, applicable law, research exceptions, and institutional policy, residents may ask to access or correct account data, request deletion, withdraw where applicable, object or restrict processing, and raise a concern with the responsible privacy office."),
    ("philippine-law", "Philippine Data Privacy Act considerations", "Deployment must follow Philippine privacy requirements", "Governance should be reviewed against Republic Act No. 10173, its implementing rules, National Privacy Commission guidance, research ethics obligations, and institutional privacy and security policies."),
    ("children", "Children and minimum age", "Age policy requires confirmation", "FloodSense is not approved for unrestricted collection from children. The applicable minimum age, parental or guardian consent process, school participation rules, and exclusion criteria must be confirmed before deployment."),
    ("international", "International processing", "Cross-border details depend on providers", "Some hosting, Google, email, or map providers may process information outside the Philippines. The production architecture must identify locations, safeguards, contractual terms, and institutional approval before deployment."),
    ("updates", "Policy updates and re-consent", "Published versions remain identifiable", "Each published policy has a version and effective date. A material new version may require residents to review and accept it before continuing, while previously accepted text remains part of the historical record."),
    ("privacy-contact", "Privacy contact", "Submit a privacy concern", "Prototype placeholder: insert the approved data protection officer or privacy office contact and the research team’s monitored contact before deployment."),
)


def seed_drafts(apps, schema_editor):
    Document = apps.get_model("accounts", "LegalDocumentVersion")
    Section = apps.get_model("accounts", "LegalDocumentSection")
    Onboarding = apps.get_model("accounts", "OnboardingVersion")
    for kind, title, sections in (
        ("TERMS", "FloodSense Terms of Use — Prototype Draft", TERMS),
        ("PRIVACY", "FloodSense Privacy Policy — Prototype Draft", PRIVACY),
    ):
        document, created = Document.objects.get_or_create(
            document_type=kind,
            version="prototype-draft-1",
            defaults={
                "title": title,
                "summary": REVIEW_NOTICE,
                "status": "DRAFT",
                "requires_acceptance": True,
            },
        )
        if created:
            Section.objects.bulk_create(
                [
                    Section(
                        document_version=document,
                        section_key=key,
                        title=section_title,
                        short_summary=summary,
                        body=body,
                        display_order=index,
                    )
                    for index, (key, section_title, summary, body) in enumerate(
                        sections, start=1
                    )
                ]
            )
    Onboarding.objects.get_or_create(
        version="prototype-draft-1",
        defaults={
            "title": "FloodSense resident onboarding — Prototype Draft",
            "status": "DRAFT",
        },
    )


def remove_drafts(apps, schema_editor):
    Document = apps.get_model("accounts", "LegalDocumentVersion")
    Onboarding = apps.get_model("accounts", "OnboardingVersion")
    Document.objects.filter(version="prototype-draft-1", status="DRAFT").delete()
    Onboarding.objects.filter(version="prototype-draft-1", status="DRAFT").delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_accountdeletionrequest_emailverificationchallenge_and_more")]
    operations = [migrations.RunPython(seed_drafts, remove_drafts)]
