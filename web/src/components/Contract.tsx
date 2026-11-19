import { useState, type CSSProperties } from 'react';

import type { ContractReport, PaymentSource, Totals, WorkLine } from '../api.ts';
import {
  barSegments, formatDate, formatMoney, formatRub, isZero, unscheduled, type BarPart, type Money,
} from '../money.ts';
import { Alert } from './Icons.tsx';
import { PaymentStatus, WorkStatus } from './Status.tsx';

// Наведение на платёж подсвечивает работы, которые он закрыл, и наоборот:
// так видно, «за что мы уже рассчитались».
type Highlight = string | null;

export function Contract({ contract }: { contract: ContractReport }) {
  const [highlight, setHighlight] = useState<Highlight>(null);
  const { totals } = contract;
  const titleId = `contract-${contract.contract_id}`;

  return (
    <article className="contract" aria-labelledby={titleId}>
      <header className="contract__head">
        <div>
          <p className="contract__id">Договор {contract.contract_id}</p>
          <h2 id={titleId} className="contract__title">{contract.contractor}</h2>
          <p className="contract__meta">
            Подписан {formatDate(contract.signed_at)} · сумма договора {formatRub(contract.amount)}
          </p>
        </div>
        <div className="contract__figure">
          <span className="label">Осталось оплатить</span>
          <span className="figure figure--contract">{formatRub(totals.remaining)}</span>
          <span className="contract__meta">из {formatRub(totals.works_due)} по работам</span>
        </div>
      </header>

      <PaymentBar totals={totals} />

      {contract.warnings.length > 0 && (
        <aside className="notice" aria-label={`Проверить по договору ${contract.contract_id}`}>
          <Alert className="notice__icon" />
          <ul>
            {contract.warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        </aside>
      )}

      <WorksTable contract={contract} highlight={highlight} onHighlight={setHighlight} />

      <div className="contract__split">
        <Ledger totals={totals} unappliedFrom={contract.unapplied_from} />
        <Payments contract={contract} highlight={highlight} onHighlight={setHighlight} />
      </div>
    </article>
  );
}

const BAR_LABELS: Record<BarPart, string> = {
  works: 'Зачтено в работы',
  advance: 'Аванс, не зачтённый в работы',
  overpaid: 'Переплата',
  queued: 'В очереди на оплату',
};

const BAR_VALUES: Record<BarPart, keyof Totals> = {
  works: 'paid_to_works',
  advance: 'advance_unapplied',
  overpaid: 'overpaid',
  queued: 'queued',
};

function PaymentBar({ totals }: { totals: Totals }) {
  const segments = barSegments(totals);
  const rest = unscheduled(totals.remaining, totals.queued);
  const description = [
    ...segments.map(({ part }) => `${BAR_LABELS[part]} ${formatRub(totals[BAR_VALUES[part]])}`),
    `стоимость работ ${formatRub(totals.works_due)}`,
  ].join(', ');

  return (
    <figure className="bar">
      <div className="bar__track" role="img" aria-label={description}>
        <div className="bar__fill">
          {segments.map(({ part, share }) => (
            <span key={part} className={`bar__segment bar__segment--${part}`} style={{ '--share': share } as CSSProperties} />
          ))}
        </div>
      </div>
      <figcaption className="legend">
        {segments.map(({ part }) => (
          <span key={part} className="legend__item">
            <span className={`legend__swatch bar__segment--${part}`} aria-hidden="true" />
            {BAR_LABELS[part]}
            <span className="legend__value">{formatMoney(totals[BAR_VALUES[part]])}</span>
          </span>
        ))}
        {!isZero(rest) && (
          <span className="legend__item">
            <span className="legend__swatch legend__swatch--rest" aria-hidden="true" />
            Ещё не оплачено и не в очереди
            <span className="legend__value">{formatMoney(rest)}</span>
          </span>
        )}
      </figcaption>
    </figure>
  );
}

interface HighlightProps {
  highlight: Highlight;
  onHighlight: (paymentId: Highlight) => void;
}

function paidBy(work: WorkLine, paymentId: Highlight): boolean {
  return paymentId !== null && work.paid_from.some((source) => source.payment_id === paymentId);
}

function WorksTable({ contract, highlight, onHighlight }: { contract: ContractReport } & HighlightProps) {
  return (
    <div className="works">
      <table className="table">
        <caption className="visually-hidden">Работы по договору {contract.contract_id}</caption>
        <thead>
          <tr>
            <th scope="col">Работа</th>
            <th scope="col">Статус на дату</th>
            <th scope="col" className="num">Цена, ₽</th>
            <th scope="col" className="num">Выплачено, ₽</th>
            <th scope="col" className="num">Осталось, ₽</th>
            <th scope="col">Чем оплачено</th>
          </tr>
        </thead>
        <tbody>
          {contract.works.map((work) => (
            <tr
              key={work.work_id}
              className={[
                'table__row',
                work.status === 'cancelled' && 'is-cancelled',
                paidBy(work, highlight) && 'is-highlighted',
              ].filter(Boolean).join(' ')}
            >
              <th scope="row" className="work-cell">
                <span className="work">
                  <span className="id">{work.work_id}</span>
                  <span className="work__title">{work.title}</span>
                </span>
              </th>
              <td data-label="Статус"><WorkStatus work={work} /></td>
              <td data-label="Цена" className="num work__price">
                <span className="amount">{formatMoney(work.price)}</span>
              </td>
              <td data-label="Выплачено" className="num">
                <Amount value={work.paid} />
              </td>
              <td data-label="Осталось" className="num">
                <Amount value={work.remaining} strong />
              </td>
              <td data-label="Чем оплачено">
                <Sources sources={work.paid_from} highlight={highlight} onHighlight={onHighlight} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Amount({ value, strong = false }: { value: Money; strong?: boolean }) {
  const zero = isZero(value);
  return <span className={zero ? 'amount amount--zero' : strong ? 'amount amount--strong' : 'amount'}>{formatMoney(value)}</span>;
}

function Sources({ sources, highlight, onHighlight }: { sources: PaymentSource[] } & HighlightProps) {
  if (sources.length === 0) return <span className="muted">—</span>;
  return (
    <ul className="sources">
      {sources.map((source) => (
        <li
          key={source.payment_id}
          className={source.payment_id === highlight ? 'source is-highlighted' : 'source'}
          onMouseEnter={() => onHighlight(source.payment_id)}
          onMouseLeave={() => onHighlight(null)}
        >
          <span className="id">{source.payment_id}</span>
          {formatMoney(source.amount)}
        </li>
      ))}
    </ul>
  );
}

function Ledger({ totals, unappliedFrom }: { totals: Totals; unappliedFrom: PaymentSource[] }) {
  const rows: [string, Money, string?][] = [
    ['Стоимость работ без отменённых', totals.works_due],
    ['из них приняты', totals.accepted, 'sub'],
    ['Выплачено', totals.paid],
    ['зачтено в работы', totals.paid_to_works, 'sub'],
    ['аванс, ещё не зачтённый в работы', totals.advance_unapplied, 'sub'],
  ];
  if (!isZero(totals.overpaid)) rows.push(['переплата', totals.overpaid, 'sub bad']);
  rows.push(
    ['Осталось оплатить', totals.remaining, 'total'],
    ['из них долг за принятые работы', totals.accepted_debt, 'sub'],
    ['В очереди на оплату', totals.queued],
  );

  return (
    <section className="ledger" aria-label="Итоги по договору">
      <h3 className="section-label">Итоги</h3>
      <dl>
        {rows.map(([label, value, kind]) => (
          <div key={label} className={`ledger__row ${kind ? kind.split(' ').map((k) => `ledger__row--${k}`).join(' ') : ''}`}>
            <dt>{label}</dt>
            <dd>{formatMoney(value)}</dd>
          </div>
        ))}
      </dl>
      {unappliedFrom.length > 0 && (
        <p className="ledger__note">
          Не зачтены в работы деньги из платежей{' '}
          {unappliedFrom.map((source) => `${source.payment_id} (${formatMoney(source.amount)})`).join(', ')}.
        </p>
      )}
    </section>
  );
}

function Payments({ contract, highlight, onHighlight }: { contract: ContractReport } & HighlightProps) {
  return (
    <section className="payments" aria-label="Платежи на дату">
      <h3 className="section-label">Платежи на дату</h3>
      {contract.payments.length === 0 ? (
        <p className="muted">На эту дату платежей по договору нет.</p>
      ) : (
        <ul className="payments__list">
          {contract.payments.map((payment) => (
            <li
              key={payment.payment_id}
              className={[
                'payment',
                payment.status !== 'paid' && 'payment--inactive',
                payment.payment_id === highlight && 'is-highlighted',
              ].filter(Boolean).join(' ')}
              onMouseEnter={() => onHighlight(payment.payment_id)}
              onMouseLeave={() => onHighlight(null)}
            >
              <span className="id">{payment.payment_id}</span>
              <span className="payment__purpose">
                {payment.purpose || 'Без назначения'}
                {payment.work_id && <span className="payment__work">к работе {payment.work_id}</span>}
              </span>
              <PaymentStatus payment={payment} />
              <span className={payment.status === 'refunded' ? 'num payment__amount is-struck' : 'num payment__amount'}>
                {formatMoney(payment.amount)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
