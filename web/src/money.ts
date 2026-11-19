// Деньги приходят из API строками "185000.00". Считаем в копейках через BigInt —
// без float, как и на сервере. Нужно это только для полосы оплаты и знаков.

export type Money = string;
export type IsoDate = string;

const NBSP = ' ';
const MINUS = '−';
const MONEY_RE = /^(-?)(\d+)\.(\d{2})$/;
const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
const MONTHS = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
];

export function toKopecks(value: Money): bigint {
  const match = MONEY_RE.exec(value);
  if (!match) throw new Error(`Не сумма: ${value}`);
  const kopecks = BigInt(match[2]) * 100n + BigInt(match[3]);
  return match[1] ? -kopecks : kopecks;
}

export function fromKopecks(kopecks: bigint): Money {
  const sign = kopecks < 0n ? '-' : '';
  const absolute = kopecks < 0n ? -kopecks : kopecks;
  return `${sign}${absolute / 100n}.${String(absolute % 100n).padStart(2, '0')}`;
}

export function isZero(value: Money): boolean {
  return toKopecks(value) === 0n;
}

/** Сколько ещё не оплачено и не стоит в очереди: остаток минус очередь, не меньше нуля. */
export function unscheduled(remaining: Money, queued: Money): Money {
  const rest = toKopecks(remaining) - toKopecks(queued);
  return fromKopecks(rest > 0n ? rest : 0n);
}

/** "185000.00" → "185 000,00" (неразрывные пробелы между разрядами). */
export function formatMoney(value: Money): string {
  const match = MONEY_RE.exec(value);
  if (!match) throw new Error(`Не сумма: ${value}`);
  const grouped = match[2].replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
  return `${match[1] ? MINUS : ''}${grouped},${match[3]}`;
}

export function formatRub(value: Money): string {
  return `${formatMoney(value)}${NBSP}₽`;
}

function parseIso(value: IsoDate): [number, number, number] {
  const match = DATE_RE.exec(value);
  if (!match) throw new Error(`Не дата: ${value}`);
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

export function isIsoDate(value: string): boolean {
  const match = DATE_RE.exec(value);
  if (!match) return false;
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

/** "2026-11-10" → "10.11.2026" */
export function formatDate(value: IsoDate): string {
  const [year, month, day] = parseIso(value);
  return `${String(day).padStart(2, '0')}.${String(month).padStart(2, '0')}.${year}`;
}

/** "2026-11-10" → "10 ноября 2026" */
export function formatLongDate(value: IsoDate): string {
  const [year, month, day] = parseIso(value);
  return `${day}${NBSP}${MONTHS[month - 1]} ${year}`;
}

export function shiftDate(value: IsoDate, days: number): IsoDate {
  const [year, month, day] = parseIso(value);
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10);
}

export function todayIso(now: Date = new Date()): IsoDate {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** 1 договор, 2 договора, 5 договоров. */
export function plural(count: number, forms: [string, string, string]): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  const form = mod10 === 1 && mod100 !== 11 ? 0 : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14) ? 1 : 2;
  return `${count} ${forms[form]}`;
}

export interface BarInput {
  works_due: Money;
  paid_to_works: Money;
  advance_unapplied: Money;
  overpaid: Money;
  queued: Money;
}

export type BarPart = 'works' | 'advance' | 'overpaid' | 'queued';

/**
 * Доли полосы оплаты договора. Шкала — стоимость работ, а если выплачено и
 * поставлено в очередь больше — эта сумма, чтобы переплата была видна.
 */
export function barSegments(totals: BarInput): { part: BarPart; share: number }[] {
  const parts: [BarPart, bigint][] = [
    ['works', toKopecks(totals.paid_to_works)],
    ['advance', toKopecks(totals.advance_unapplied)],
    ['overpaid', toKopecks(totals.overpaid)],
    ['queued', toKopecks(totals.queued)],
  ];
  const used = parts.reduce((sum, [, amount]) => sum + amount, 0n);
  const due = toKopecks(totals.works_due);
  const scale = used > due ? used : due;
  if (scale === 0n) return [];
  return parts
    .filter(([, amount]) => amount > 0n)
    .map(([part, amount]) => ({ part, share: Number((amount * 1_000_000n) / scale) / 1_000_000 }));
}
