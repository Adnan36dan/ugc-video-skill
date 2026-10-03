"""First-pass claim-safety check for scripts (English, Hinglish and Hindi).

It flags wording that Indian advertising rules commonly restrict for Ayurvedic / wellness products
(Drugs & Magic Remedies (Objectionable Advertisements) Act 1954, ASCI Code incl. its health-claim and
virtual-influencer guidance) and wording that turns an AI character into a fake testimonial.
It is a safety net, not legal advice: the brand's compliance owner makes the final call.
"""
import re

R = re.IGNORECASE

# (severity, label, [patterns], why, safer wording)
RULES = [
    ("HIGH", "cure / treatment claim",
     [r"\bcur(e|es|ed|ing)\b", r"\bheal(s|ed|ing)?\b", r"\btreat(s|ed|ing|ment)?\b", r"\bremed(y|ies)\b",
      r"\bilaa?j\b", r"\bjadd? se\b", r"इलाज", r"जड़ से", r"\bthee?k kar (deta|deti|dega|degi|diya|di)\b",
      r"\brog mukt\b", r"रोग\s*मुक्त"],
     "Claims to cure, heal or treat a condition are restricted for Ayurvedic products (DMR Act, ASCI).",
     "'supports', 'is traditionally used for', 'part of my daily routine'"),
    ("HIGH", "guarantee / absolute promise",
     [r"\bguarantee(d|s)?\b", r"\bgaranti\b", r"गारंटी", r"\b100\s?%\s*(result|effective|asar|guarantee)",
      r"\bpermanent(ly)?\b", r"\bpakka (result|asar)\b"],
     "Absolute results cannot be promised for a wellness product.",
     "describe the routine or experience, not a guaranteed outcome"),
    ("HIGH", "clinical / proof claim",
     [r"\bclinically\b", r"\bscientifically proven\b", r"\bproven\b", r"\bdoctors?\s+(recommend|approved|certified|tested)",
      r"\bfda\b", r"साबित"],
     "Needs documented, product-level clinical evidence you can show ASCI; ingredient studies are not "
     "proof for the finished product.",
     "'contains X, traditionally used for Y' or 'studies have looked at X' (only if true and sourced)"),
    ("HIGH", "named disease or medical condition",
     [r"\bdiabet(es|ic)\b", r"\bblood sugar\b", r"\bsugar\s+(level|control|kam|normal|patient)", r"\binsulin\b",
      r"\bmadhumeh\b", r"मधुमेह", r"शुगर", r"\bblood pressure\b", r"\bb\.?p\.?\b", r"\bhypertension\b", r"बीपी",
      r"\bheart (disease|attack|problem|blockage)", r"\bcardiac\b", r"\bblock(age|ed) (arter|nas)", r"हार्ट",
      r"\bcancer\b", r"\btumou?r\b", r"कैंसर", r"\bobes(e|ity)\b", r"\bmotapa\b", r"मोटापा", r"\bkidney stones?\b",
      r"\bpathri\b", r"\bparalysis\b", r"\bepilepsy\b", r"\binfertil(e|ity)\b", r"\bsterility\b",
      r"\bdementia\b", r"\balzheimer", r"\bmemory loss\b", r"\barthritis\b", r"\bthyroid\b", r"\bliver disease\b",
      r"\bfatty liver\b", r"\bpcos\b", r"\bmenstrual\b"],
     "Naming a disease invites a 'treats/prevents X' reading; diabetes, blood pressure, heart disease, obesity, "
     "cancer, sexual impotence and others are on the DMR Act schedule.",
     "talk about the daily routine or general wellness after 45, not the disease; never imply it replaces treatment"),
    ("HIGH", "sexual-performance claim",
     [r"\bsex(ual)?\s*(power|stamina|performance|drive|wellness|health)", r"\blibido\b", r"\bviril(e|ity)\b",
      r"\bimpoten", r"\berectile\b", r"\bmardana\b", r"मर्दाना", r"\bmard(on)? ki (taakat|takat|shakti)",
      r"यौन", r"\bperformance in bed\b"],
     "Claims about sexual capacity are prohibited by the DMR Act.",
     "'energy for my day', 'part of my morning routine' (and only if accurate)"),
    ("HIGH", "replacing medicine or doctor",
     [r"\b(stop(ped)?|quit|left|leave|without|skip(ped)?)\b.{0,25}\b(medicines?|medication|tablets|insulin|dawai|dawa|pills)\b",
      r"\bdawai?\s*(chhod|band|bandh)", r"दवा(ई)?\s*(छोड़|बंद)", r"\bno need (for|of|to see)?\s*(a )?(doctor|medicine)",
      r"\binstead of (medicine|doctor|treatment)", r"\bdoctor ki zaroorat nahi"],
     "Suggesting someone can drop prescribed treatment is unsafe and prohibited.",
     "'keep taking what your doctor prescribed; ask your doctor before adding any supplement'"),
    ("HIGH", "absolute safety claim",
     [r"\b(no|zero)\s+side[- ]?effects?\b", r"\b100\s?%\s*safe\b", r"\bcompletely safe\b", r"\bkoi side ?effect nahi",
      r"\bbina (kisi )?side ?effect", r"साइड\s*इफेक्ट\s*नहीं"],
     "ASCI repeatedly flags 'no side effects' / '100% safe' as unsubstantiated absolutes.",
     "'gentle enough for my daily routine' or simply leave it out"),
    ("HIGH", "personal health result from an AI person",
     [r"\b(my|meri|mera|mere)\s+(sugar|b\.?p|blood pressure|cholesterol|weight|wajan|vajan|pain|dard|knees?|joints?|"
      r"reports?|hba1c|thyroid|levels?|hair ?fall|wrinkles)\b",
      r"\b(i|main|maine|mujhe|mera)\b.{0,30}\b(lost|kam ho (gaya|gayi|gaye)|reduced|dropped|cured|normal ho)",
      r"\b(i|main|maine)\b.{0,25}\b\d+\s?(kg|kilo)\b", r"मेरा\s*(शुगर|बीपी|वज़न|वजन)", r"मेरी\s*(शुगर|रिपोर्ट)"],
     "An AI-generated person describing their own health results is a fabricated testimonial (ASCI requires "
     "testimonials to be genuine and documented).",
     "the character can share the routine, taste, ingredients or how easy it is - not medical results"),
    ("HIGH", "posing as a health professional",
     [r"\b(as a|i am a|i'm a|main ek|mai ek)\s+(doctor|physician|nutritionist|dietitian|vaidya|vaid|ayurvedacharya)\b",
      r"\bdr\.?\s+[a-z]+", r"डॉक्टर\s*हूँ", r"\bmain doctor (hoon|hu)\b"],
     "An AI character must not present as a doctor or expert; it implies professional endorsement.",
     "use a relatable everyday persona"),
    ("MEDIUM", "time-bound or before/after result",
     [r"\bbefore\s*(and|&|/)\s*after\b", r"\b(in|within|just)\s+\d+\s+(days?|weeks?|months?)\b",
      r"\b\d+\s+(din|dino|hafte|hafton|mahine|mahino)\s+(mein|me|main)\b", r"\d+\s*दिन\s*में"],
     "Time-bound promises need evidence and suggest a medical effect.",
     "'I've made it part of my routine' (no promised timeline)"),
    ("MEDIUM", "miracle / instant",
     [r"\bmiracle\b", r"\bmagic(al)?\b", r"\bchamatkar", r"\bjaadu\b", r"जादू", r"चमत्कार", r"\binstant(ly)?\b",
      r"\bovernight\b", r"\bturant\b", r"तुरंत", r"\bimmediately\b"],
     "Exaggerated, unsubstantiated effect.", "plain, specific, honest wording"),
    ("MEDIUM", "anti-ageing / reversal",
     [r"\breverse[sd]?\b", r"\banti[- ]?ag(e)?ing\b", r"\byears younger\b", r"\bjawan (dikh|lag)", r"जवान"],
     "Reversal / age claims need strong evidence and read as medical.",
     "'how I take care of myself after 45'"),
    ("MEDIUM", "purity / natural absolute",
     [r"\b100\s?%\s*(natural|pure|ayurvedic|herbal)\b", r"\bchemical[- ]free\b", r"\bnatural,? so (it'?s )?safe\b"],
     "Absolute purity claims need proof; 'natural' does not mean safe.",
     "'made with sea buckthorn and amla' (state the actual ingredients)"),
    ("MEDIUM", "superlative / comparison",
     [r"\b(no\.?\s?1|number one|#1)\b", r"\bbest in (india|the market)\b", r"\bindia'?s best\b", r"\bsabse (best|acch?ha)\b"],
     "Comparative claims need substantiation.", "speak for yourself: 'what I like about it'"),
    ("MEDIUM", "detox / immunity / disease-adjacent claim",
     [r"\bdetox", r"\b(boost|increase|improve)s?\s+(your\s+)?immunity\b", r"\bimmunity badha", r"\bstamina\b",
      r"\bjoint pain\b", r"\bhair regrowth\b", r"\bbaldness\b", r"\bcholesterol\b", r"\bganjapan\b"],
     "Reads as a health effect; keep to the product's approved label claims.",
     "describe the routine and ingredients; keep to approved label wording"),
    ("INFO", "price / offer",
     [r"(₹|\brs\.?|\binr)\s?\d", r"\b\d+\s?%\s*off\b", r"\bdiscount\b", r"\bsale\b"],
     "Fine for ads, but must be accurate and current on the day the ad runs.", ""),
]

COMPILED = [(sev, label, [re.compile(p, R) for p in pats], why, safer) for sev, label, pats, why, safer in RULES]
ORDER = {"HIGH": 0, "MEDIUM": 1, "INFO": 2}


def check_texts(items):
    """items: list of (where, text). Returns findings sorted by severity."""
    found = []
    for where, text in items:
        if not text:
            continue
        for sev, label, pats, why, safer in COMPILED:
            hits = sorted({m.group(0) for p in pats for m in p.finditer(text)})
            if hits:
                found.append({"severity": sev, "where": where, "label": label, "matched": hits, "why": why,
                              "safer": safer})
    return sorted(found, key=lambda f: (ORDER[f["severity"]], f["where"]))


def plan_texts(job):
    items = []
    for s in job.segments:
        items.append((s["id"], s["say"]))
        if s.get("caption"):
            items.append((f"{s['id']} caption", s["caption"]))
    ec = job.plan["endcard"]
    items += [("endcard cta", ec.get("cta")), ("endcard accent", ec.get("accent"))]
    return items


def report(findings):
    counts = {k: sum(1 for f in findings if f["severity"] == k) for k in ORDER}
    lines = [f"Script check: {counts['HIGH']} HIGH, {counts['MEDIUM']} MEDIUM, {counts['INFO']} INFO"]
    for f in findings:
        lines.append(f"\n{f['severity']:<6} [{f['where']}] {f['label']}: " + ", ".join(f'"{h}"' for h in f["matched"]))
        lines.append(f"       why: {f['why']}")
        if f["safer"]:
            lines.append(f"       try: {f['safer']}")
    lines.append("\nAutomatic first pass only - not legal advice. Final wording must match the product's approved "
                 "label claims and be signed off by Vansaar's compliance owner.")
    return "\n".join(lines), counts
