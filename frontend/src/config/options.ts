export const connectorOptions = [
  { label: "Greenhouse", value: "greenhouse" },
  { label: "Lever", value: "lever" },
  { label: "Ashby", value: "ashby" },
  { label: "Microsoft Careers", value: "microsoft-careers" },
  { label: "Google Careers", value: "google-careers" },
  { label: "Workday", value: "workday" },
  { label: "SmartRecruiters", value: "smartrecruiters" },
  { label: "Company API", value: "company-api" },
];

export const countryOptions = [
  { label: "United States", value: "US" },
  { label: "Canada", value: "CA" },
  { label: "India", value: "IN" },
  { label: "Any", value: "ANY" },
];

export const freshnessOptions = [1, 3, 6, 12, 24].map((value) => ({
  label: `${value} hour${value === 1 ? "" : "s"}`,
  value,
}));

export const notificationFrequencyOptions = [
  { label: "Instant", value: "instant" },
  { label: "Morning Digest", value: "morning_digest" },
  { label: "Evening Digest", value: "evening_digest" },
];

export const workArrangementOptions = ["Remote", "Hybrid", "Onsite"];

export const experienceLevelOptions = ["Junior", "Mid", "Senior", "Staff", "Principal", "Lead", "Architect"];

export const jobTypeOptions = [
  { label: "Full-time", value: "full_time" },
  { label: "Part-time", value: "part_time" },
  { label: "Contract", value: "contract" },
  { label: "Contract-to-Hire", value: "contract_to_hire" },
  { label: "Internship", value: "internship" },
  { label: "Temporary", value: "temporary" },
];

export const companySizeOptions = [
  { label: "Startup (1-50)", value: "startup" },
  { label: "Growth (50-500)", value: "growth" },
  { label: "Mid Market (500-2000)", value: "mid_market" },
  { label: "Enterprise (2000+)", value: "enterprise" },
];

export const industryOptions = [
  { label: "Artificial Intelligence", value: "artificial_intelligence" },
  { label: "Developer Tools", value: "developer_tools" },
  { label: "Cloud Infrastructure", value: "cloud_infrastructure" },
  { label: "Enterprise Software", value: "enterprise_software" },
  { label: "Cybersecurity", value: "cybersecurity" },
  { label: "Data Platform", value: "data_platform" },
  { label: "FinTech", value: "fintech" },
  { label: "Healthcare", value: "healthcare" },
  { label: "Productivity", value: "productivity" },
  { label: "Robotics", value: "robotics" },
  { label: "Networking", value: "networking" },
  { label: "Consumer", value: "consumer" },
  { label: "Gaming", value: "gaming" },
  { label: "E-commerce", value: "e_commerce" },
  { label: "Infrastructure", value: "infrastructure" },
  { label: "Observability", value: "observability" },
];

export const visaStatusOptions = [
  { label: "Not specified", value: "" },
  { label: "OPT", value: "opt" },
  { label: "STEM OPT", value: "stem_opt" },
  { label: "US Citizen", value: "us_citizen" },
  { label: "Green Card", value: "green_card" },
  { label: "Need Sponsorship", value: "need_sponsorship" },
  { label: "No Sponsorship Required", value: "no_sponsorship_required" },
];

export const travelPreferenceOptions = [
  { label: "No Travel", value: "no_travel" },
  { label: "Up to 10%", value: "up_to_10" },
  { label: "25%", value: "up_to_25" },
  { label: "50%", value: "up_to_50" },
  { label: "Any", value: "any" },
];

export const remotePreferenceOptions = [
  { label: "Remote Only", value: "remote_only" },
  { label: "Mostly Remote", value: "mostly_remote" },
  { label: "Hybrid", value: "hybrid" },
  { label: "Onsite", value: "onsite" },
  { label: "No Preference", value: "no_preference" },
];

export const notificationRuleOptions = [
  { label: "Only 95%+", value: "only_95_plus" },
  { label: "Only New Jobs", value: "only_new_jobs" },
  { label: "Only Dream Companies", value: "only_dream_companies" },
];

export const companyPriorityOptions = [
  { label: "Dream Companies", value: "dream" },
  { label: "High Priority", value: "high" },
  { label: "Normal", value: "normal" },
  { label: "Hidden", value: "hidden" },
];

export const resumeStrategyOptions = [
  { label: "Auto-select best resume", value: "auto" },
  { label: "Use selected resumes only", value: "selected_only" },
];

export const skillImportanceOptions = [1, 2, 3, 4, 5].map((value) => ({
  label: `${value}/5`,
  value,
}));
