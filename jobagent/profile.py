"""Candidate profile derived from Fayyaadh Adams' CV.

Keyword weights drive the first-pass match score. Edit freely: add terms you
want boosted, raise/lower weights, or add titles you never want to see.
"""

CANDIDATE_SUMMARY = """\
Fayyaadh Adams, Cape Town, South Africa (needs fully remote, worldwide-eligible roles).

Experience:
- Social Media & Community Manager, Project Catalyst / Input Output (remote, 2024-2026):
  ran social, community and content for a $160M decentralised innovation fund
  (~47k community across X, Telegram, Discord, email). Content calendars, short
  video strategy (retention 76% -> 93-96%), produced 200 pitch videos in 14 days,
  HubSpot/Mailchimp email (24k list), in-house graphics/motion/video (Illustrator,
  After Effects, Premiere Pro), weekly Town Halls, sentiment/analytics reports, OKRs,
  Zendesk member support, LinkedIn page launch.
- Community Manager, Atala PRISM / Identus at IOHK (remote, 2022-2024): open-source
  developer community under Hyperledger, built Discord from scratch, community
  migration and rebrand, developer onboarding/pioneer programme, hackathons, AMAs,
  wiki and annual reports.
- Graphic Design Consultant, EY (contract 2026): presentations, reports, data visuals,
  templates, internal comms, campaign/event assets.
- Old Mutual (2016-2022): Information Security Awareness Campaign Specialist
  (phishing simulations, awareness campaigns across 8 countries, KnowBe4, video and
  graphics), Business & Systems Analyst / Project Manager (innovation challenge across
  9 countries, blockchain digital identity PoC), IT Trainee (COBOL/C++, UAT).
- Freelance Content Producer & Designer (2021-present): social content, video edits,
  design, websites, small automation tools and dashboards.

Education: PGDip Business & Systems Analysis (UCT), BCom Information Systems (UWC),
Graphic Design short course.

Skills: social strategy, content calendars, copywriting, brand voice, campaigns,
audience growth, social listening, analytics/KPIs/OKRs, Discord/Telegram moderation,
developer and ecosystem programmes, AMAs, video editing, short-form video, live
production, motion graphics, graphic design, deck/report design, Adobe CC, Figma,
HubSpot, Mailchimp, Notion, Zendesk, AI tools (Claude certified).
Strong fit with Web3/blockchain/crypto, open source, developer relations, and
security awareness organisations.
"""

# Title keywords: matched against the job title only (strong signal).
TITLE_KEYWORDS = {
    "community manager": 10,
    "community lead": 10,
    "head of community": 9,
    "community": 6,
    "social media": 10,
    "social": 4,
    "content creator": 8,
    "content producer": 9,
    "content manager": 8,
    "content strategist": 8,
    "content marketing": 7,
    "content": 4,
    "video editor": 8,
    "video producer": 8,
    "video": 4,
    "motion designer": 7,
    "motion graphics": 7,
    "graphic designer": 7,
    "brand designer": 6,
    "marketing designer": 7,
    "creative": 4,
    "developer relations": 7,
    "devrel": 7,
    "developer advocate": 6,
    "ecosystem": 7,
    "engagement": 5,
    "marketing manager": 5,
    "marketing": 3,
    "growth": 3,
    "copywriter": 5,
    "brand": 4,
    "communications": 6,
    "comms": 6,
    "moderator": 5,
    "security awareness": 8,
    "business analyst": 5,
    "program manager": 3,
    "programme manager": 3,
    "events": 3,
    "partnerships": 2,
}

# Body keywords: matched against title + tags + description (weaker signal).
BODY_KEYWORDS = {
    "discord": 3,
    "telegram": 3,
    "community": 2,
    "social media": 2,
    "content calendar": 3,
    "short-form": 2,
    "short form": 2,
    "tiktok": 1,
    "youtube": 1,
    "linkedin": 1,
    "premiere pro": 3,
    "after effects": 3,
    "illustrator": 2,
    "photoshop": 1,
    "figma": 1,
    "hubspot": 2,
    "mailchimp": 2,
    "zendesk": 1,
    "notion": 1,
    "web3": 3,
    "blockchain": 3,
    "crypto": 2,
    "cardano": 4,
    "defi": 1,
    "dao": 2,
    "open source": 2,
    "open-source": 2,
    "hackathon": 2,
    "ama": 1,
    "town hall": 2,
    "copywriting": 1,
    "brand voice": 2,
    "analytics": 1,
    "okr": 1,
    "kpi": 1,
    "moderation": 2,
    "developer community": 3,
    "ambassador": 2,
    "phishing": 2,
    "security awareness": 3,
    "motion graphics": 2,
    "video editing": 2,
}

# Titles containing any of these are dropped outright (wrong career track).
EXCLUDE_TITLE_TERMS = [
    "software engineer", "backend", "back-end", "frontend", "front-end",
    "full stack", "fullstack", "devops", "sre", "data engineer",
    "data scientist", "machine learning", "ml engineer", "android", "ios developer",
    "qa engineer", "test engineer", "nurse", "physician", "therapist",
    "accountant", "bookkeeper", "attorney", "lawyer", "paralegal",
    "sales development", "account executive", "recruiter", "tutor", "teacher",
    "driver", "solidity", "smart contract engineer", "rust engineer",
    "golang", "java developer", "python developer", "php developer",
]

# Minimum keyword score to be considered a candidate match.
MIN_KEYWORD_SCORE = 8
