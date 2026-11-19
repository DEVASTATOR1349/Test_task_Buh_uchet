import type { IsoDate, Money } from './money.ts';

// Форма ответа GET /report — см. README.md, раздел «API».

export interface PaymentSource {
  payment_id: string;
  amount: Money;
}

export type WorkStatus = 'done' | 'planned' | 'cancelled';
export type PaymentStatus = 'paid' | 'queued' | 'refunded';

export interface WorkLine {
  work_id: string;
  title: string;
  status: WorkStatus;
  status_date: IsoDate | null;
  price: Money;
  paid: Money;
  remaining: Money;
  paid_from: PaymentSource[];
}

export interface Totals {
  works_due: Money;
  accepted: Money;
  paid: Money;
  paid_to_works: Money;
  advance_unapplied: Money;
  overpaid: Money;
  accepted_debt: Money;
  queued: Money;
  remaining: Money;
}

export interface PaymentLine {
  payment_id: string;
  work_id: string | null;
  purpose: string;
  amount: Money;
  status: PaymentStatus;
  created_at: IsoDate;
  paid_at: IsoDate | null;
  refunded_at: IsoDate | null;
}

export interface ContractReport {
  contract_id: string;
  contractor: string;
  signed_at: IsoDate;
  amount: Money;
  works: WorkLine[];
  totals: Totals;
  unapplied_from: PaymentSource[];
  payments: PaymentLine[];
  warnings: string[];
}

export interface Report {
  report_date: IsoDate;
  contracts: ContractReport[];
  totals: Totals;
}

export type ReportErrorKind = 'offline' | 'data' | 'request';

export class ReportError extends Error {
  readonly kind: ReportErrorKind;
  readonly problems: string[];

  constructor(kind: ReportErrorKind, message: string, problems: string[] = []) {
    super(message);
    this.kind = kind;
    this.problems = problems;
  }
}

export function reportUrl(date: IsoDate, format: 'json' | 'text' = 'json'): string {
  const query = new URLSearchParams({ date });
  if (format === 'text') query.set('format', 'text');
  return `/report?${query}`;
}

export async function fetchReport(date: IsoDate, signal: AbortSignal): Promise<Report> {
  let response: Response;
  try {
    response = await fetch(reportUrl(date), { signal, headers: { Accept: 'application/json' } });
  } catch (error) {
    if (signal.aborted) throw error;
    throw new ReportError('offline', 'Сервер отчётов не отвечает');
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const details = (body ?? {}) as { error?: string; problems?: string[] };
    const kind = response.status >= 500 ? 'data' : 'request';
    throw new ReportError(kind, details.error ?? `Сервер ответил ${response.status}`, details.problems ?? []);
  }
  return body as Report;
}
