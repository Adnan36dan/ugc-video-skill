# Compliance: likeness, AI disclosure, health claims (India)

This is a working guide for keeping videos safe and honest. It is **not legal advice**. Vansaar's
compliance owner or legal advisor has the final word, and the rules change, so check the current
versions of the ASCI Code and guidelines and the AYUSH advertising rules.

## 1. The person on screen

- **Use only faces you have the right to use.** That means an AI-generated character, or a real
  person who signed a release covering AI-generated advertising use of their likeness and voice.
  Keep the release on file.
- **Never** a celebrity, influencer, doctor, public figure or private person without consent. Never
  "a face that looks like" a famous person.
- **No health-professional personas.** The character must not be, or look like, a doctor, vaidya
  or nutritionist (no white coat, stethoscope or clinic). That would imply professional
  endorsement.
- **Cloned voices follow the same rule.** Only clone a voice with written consent.

## 2. Saying it's AI

- ASCI's guidance on influencer advertising asks **virtual influencers / AI-generated humans** to
  disclose upfront that viewers are not interacting with a real person. Ads should also carry the
  usual ad disclosure where relevant.
- Meta, YouTube and other platforms have AI-content labelling rules for realistic synthetic
  people. Turn on the platform's own "AI-generated / altered content" toggle when uploading.
- India's IT Rules have been updated to cover synthetically generated content. Check the current
  labelling requirements with your compliance owner.
- The engine shows a small **"AI-generated"** label for the whole video by default
  (`disclosure` in brand.yaml / plan.yaml).

## 3. Health claims for Ayurvedic and wellness products

**Drugs and Magic Remedies (Objectionable Advertisements) Act, 1954.** It prohibits ads that
suggest a product diagnoses, cures, mitigates, treats or prevents the diseases and conditions in
its Schedule. These include diabetes, high/low blood pressure, heart disease, obesity, cancer,
sexual impotence and premature-ejaculation-type claims, sterility, menstrual disorders, kidney
stones, paralysis, epilepsy and more. It also prohibits ads for improving sexual capacity.

**ASCI Code** (truthful and honest, no misleading claims; health-claim and testimonial
guidance):
- Every claim needs substantiation. Ingredient research is not proof for the finished product.
- Testimonials must be genuine, current and documented. **An AI character describing its own
  health results is not a genuine testimonial.**
- Absolutes ("no side effects", "100% safe", "guaranteed", "permanent") are routinely upheld
  against brands.

**Drugs & Cosmetics Rules for Ayurvedic products.** Claims must stay within what the product
licence and label permit. The status of the AYUSH advertising-approval rule has changed in recent
years, so check its current state.

**Vansaar's own content rules (from the carousel pipeline):** no "proven", "clinically proven",
"cures", "prevents", "reverses", "guarantees" or blockage-removal language. Prefer "traditionally
used for", "supports", "may help as part of a routine". End with the disclaimer *"This product is
not intended to diagnose, treat, cure or prevent any disease."* (the end card shows it).

## 4. Safe-wording table

| Risky | Safer |
|---|---|
| "It controls my sugar" / "meri sugar normal ho gayi" | "It's part of my morning routine now" |
| "Clinically proven" | "Made with karela, jamun and neem" (only real ingredients from the label) |
| "Cures joint pain" | "I like having a simple daily ritual" |
| "No side effects, 100% natural" | "Made with herbs like X and Y" |
| "Results in 7 days" | "I've been taking it every morning" |
| "Stop your BP tablets" | "Keep taking what your doctor prescribed; ask them before adding any supplement" |
| "Doctor recommended" | (only if true and documented, with the doctor's consent) |
| "Mardana taakat / stamina for men" | (don't, it falls under the DMR Act) |
| "Reverse ageing / look 10 years younger" | "How I take care of myself after 50" |
| "Best in India / No. 1" | "What I like about it" |

**Product names that contain a condition** (e.g. a "Diab" or "Cholesterol" product): saying the
product name is factual, but the surrounding script must not claim it treats or controls that
condition. Keep these scripts especially conservative.

## 5. What `ugc.py check` does

It scans every `say`, `caption` and end-card line in English, Hinglish and Hindi. It flags:
- cure or treat words
- guarantees
- clinical or proof claims
- named diseases
- sexual-performance claims
- "stop your medicine"
- absolute safety claims
- first-person health results
- health-professional personas
- time-bound results
- miracle language
- anti-ageing language
- purity absolutes
- superlatives
- detox and immunity claims
- prices

HIGH means rewrite it. MEDIUM means rewrite it or get explicit sign-off. INFO means keep it
accurate. It is a pattern matcher: it misses clever phrasing and sometimes flags harmless words
("a tasty treat"), so Claude still reads every line with these rules in mind.
