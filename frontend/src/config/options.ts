export const connectorOptions = [
  { label: "Greenhouse", value: "greenhouse" },
  { label: "Lever", value: "lever" },
  { label: "Ashby", value: "ashby" },
  { label: "Microsoft Careers", value: "microsoft" },
  { label: "Google Careers", value: "google" },
  { label: "Workday", value: "workday" },
  { label: "SmartRecruiters", value: "smartrecruiters" },
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
  { label: "Hourly digest", value: "hourly" },
  { label: "Daily digest", value: "daily" },
];

export const workArrangementOptions = ["Remote", "Hybrid", "Onsite"];

export const experienceLevelOptions = ["Mid", "Senior", "Staff"];
