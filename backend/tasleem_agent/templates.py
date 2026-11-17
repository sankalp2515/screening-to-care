"""Approved message library. Every template passes the case-core message policy (tested), so the
offline agent can always offer a safe draft. PLACEHOLDER wording until the programme's patient-education
lead approves it; Arabic must be reviewed by a native-speaking clinician before a pilot."""

from __future__ import annotations

OUTREACH: dict[str, dict[str, str]] = {
    "FEAR": {
        "en": "We understand the test can feel worrying. A member of your care team will call you to explain "
              "what happens on the day and answer your questions.",
        "ar": "نتفهم أن الفحص قد يسبب القلق. سيتصل بك أحد أعضاء فريق الرعاية ليشرح لك ما يحدث في يوم الفحص "
              "ويجيب عن أسئلتك.",
    },
    "PREP_UNCLEAR": {
        "en": "Thank you for telling us the preparation is unclear. A nurse will call you to go through it "
              "step by step before your appointment.",
        "ar": "شكراً لإخبارنا بأن التحضير غير واضح. ستتصل بك ممرضة لمراجعة خطوات التحضير معك قبل موعدك.",
    },
    "NO_ESCORT": {
        "en": "You will need someone to take you home after the test. Our team will call you to help find a "
              "time when a family member can come, or another option.",
        "ar": "ستحتاج إلى من يرافقك إلى المنزل بعد الفحص. سيتصل بك فريقنا لمساعدتك في اختيار موعد يناسب أحد "
              "أفراد عائلتك أو إيجاد بديل.",
    },
    "TRANSPORT": {
        "en": "Getting to the clinic should not stop your care. Our team will call you about a closer centre "
              "or help with transport.",
        "ar": "لا ينبغي أن يمنعك الوصول إلى العيادة من متابعة رعايتك. سيتصل بك فريقنا بشأن مركز أقرب أو "
              "المساعدة في المواصلات.",
    },
    "COST_OR_INSURANCE": {
        "en": "Our team is checking your insurance cover and will call you about a centre in your network.",
        "ar": "يقوم فريقنا بالتحقق من تغطية التأمين الخاصة بك وسيتصل بك بشأن مركز ضمن شبكتك.",
    },
    "TIME_OR_WORK": {
        "en": "We can look for an evening or weekend appointment and can give you a sick-leave note. Our team "
              "will call you to find a time that works.",
        "ar": "يمكننا البحث عن موعد مسائي أو في عطلة نهاية الأسبوع، ويمكننا تزويدك بإجازة مرضية. سيتصل بك "
              "فريقنا لاختيار وقت يناسبك.",
    },
    "LANGUAGE": {
        "en": "We will arrange an interpreter and send your instructions in your preferred language.",
        "ar": "سنرتب لك مترجماً ونرسل لك التعليمات باللغة التي تفضلها.",
    },
    "WANTS_CALLBACK": {
        "en": "Thank you. Your doctor's team will call you back soon.",
        "ar": "شكراً لك. سيتصل بك فريق طبيبك قريباً.",
    },
    "DONE_ELSEWHERE": {
        "en": "Thank you for letting us know. Please tell us where you had the test so we can request the "
              "report for your doctor.",
        "ar": "شكراً لإخبارنا. يرجى إعلامنا بمكان إجراء الفحص حتى نطلب التقرير لطبيبك.",
    },
    "OTHER": {
        "en": "Thank you for letting us know. A member of your care team will call you to understand what "
              "would help.",
        "ar": "شكراً لإخبارنا. سيتصل بك أحد أعضاء فريق الرعاية ليفهم ما الذي يمكن أن يساعدك.",
    },
    "MISSED": {
        "en": "We noticed you could not attend your appointment. Tell us what got in the way in Sahatna, or "
              "wait for our call, and we will help you rebook.",
        "ar": "لاحظنا أنك لم تتمكن من حضور موعدك. أخبرنا بما منعك عبر تطبيق صحتنا، أو انتظر اتصالنا، وسنساعدك "
              "في إعادة الحجز.",
    },
    "GENERIC": {
        "en": "Your care team is following up on your next step. Please open Sahatna or call your clinic if "
              "anything could stop you from attending.",
        "ar": "يتابع فريق الرعاية خطوتك التالية. يرجى فتح تطبيق صحتنا أو الاتصال بعيادتك إذا كان هناك ما قد "
              "يمنعك من الحضور.",
    },
}
