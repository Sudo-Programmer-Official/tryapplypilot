export function parseCsv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function joinCsv(values: string[]): string {
  return values.join(", ");
}

export function toggleStringValue(values: string[], candidate: string): string[] {
  return values.includes(candidate) ? values.filter((value) => value !== candidate) : [...values, candidate];
}
