import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  barSegments, formatDate, formatLongDate, formatMoney, fromKopecks, isIsoDate, plural, shiftDate, toKopecks,
  todayIso, unscheduled,
} from './money.ts';

const NBSP = ' ';

test('toKopecks is exact', () => {
  assert.equal(toKopecks('185000.00'), 18_500_000n);
  assert.equal(toKopecks('0.10') + toKopecks('0.20'), 30n);
  assert.equal(toKopecks('-5000.00'), -500_000n);
  assert.throws(() => toKopecks('100'));
  assert.throws(() => toKopecks('1e3'));
});

test('fromKopecks round-trips', () => {
  for (const value of ['0.00', '0.05', '185000.00', '1234567.89', '-5000.00']) {
    assert.equal(fromKopecks(toKopecks(value)), value);
  }
});

test('unscheduled: remaining minus queued, never negative', () => {
  assert.equal(unscheduled('185000.00', '150000.00'), '35000.00');
  assert.equal(unscheduled('15000.00', '0.00'), '15000.00');
  assert.equal(unscheduled('20.00', '50.00'), '0.00');
});

test('formatMoney groups thousands with non-breaking spaces', () => {
  assert.equal(formatMoney('185000.00'), `185${NBSP}000,00`);
  assert.equal(formatMoney('1234567.05'), `1${NBSP}234${NBSP}567,05`);
  assert.equal(formatMoney('0.00'), '0,00');
  assert.equal(formatMoney('-5000.00'), `−5${NBSP}000,00`);
});

test('dates', () => {
  assert.equal(formatDate('2026-11-10'), '10.11.2026');
  assert.equal(formatLongDate('2026-11-10'), `10${NBSP}ноября 2026`);
  assert.equal(shiftDate('2026-11-30', 1), '2026-12-01');
  assert.equal(shiftDate('2026-03-01', -1), '2026-02-28');
  assert.equal(todayIso(new Date(2026, 0, 5)), '2026-01-05');
  assert.ok(isIsoDate('2026-02-28'));
  assert.ok(!isIsoDate('2026-02-30'));
  assert.ok(!isIsoDate('10.11.2026'));
});

test('plural', () => {
  const forms: [string, string, string] = ['договор', 'договора', 'договоров'];
  assert.equal(plural(1, forms), '1 договор');
  assert.equal(plural(2, forms), '2 договора');
  assert.equal(plural(5, forms), '5 договоров');
  assert.equal(plural(11, forms), '11 договоров');
  assert.equal(plural(21, forms), '21 договор');
  assert.equal(plural(112, forms), '112 договоров');
});

test('barSegments: D-1 on 10.11 — works, advance and queued on a 500 000 scale', () => {
  assert.deepEqual(
    barSegments({
      works_due: '500000.00', paid_to_works: '300000.00', advance_unapplied: '15000.00',
      overpaid: '0.00', queued: '150000.00',
    }),
    [{ part: 'works', share: 0.6 }, { part: 'advance', share: 0.03 }, { part: 'queued', share: 0.3 }],
  );
});

test('barSegments: overpayment widens the scale', () => {
  assert.deepEqual(
    barSegments({
      works_due: '90000.00', paid_to_works: '90000.00', advance_unapplied: '0.00',
      overpaid: '10000.00', queued: '0.00',
    }),
    [{ part: 'works', share: 0.9 }, { part: 'overpaid', share: 0.1 }],
  );
  assert.deepEqual(
    barSegments({ works_due: '0.00', paid_to_works: '0.00', advance_unapplied: '0.00', overpaid: '0.00', queued: '0.00' }),
    [],
  );
});
