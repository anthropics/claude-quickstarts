export type Severity = "Critical" | "High" | "Medium" | "Low";

export interface Vulnerability {
    name: string;
    severity: Severity;
    line: number | null;
    description: string;
    fix: string;
}

export interface ScanResult {
    vulnerabilities: Vulnerability[];
    summary: string;
}

export interface ScanRequest {
    code: string;
    language: string;
}
