import type { Report } from '../api.ts';
import { formatLongDate, formatRub, isZero, plural } from '../money.ts';

export function Summary({ report }: { report: Report }) {
  const { totals } = report;
  const works = report.contracts.reduce((count, contract) => count + contract.works.length, 0);
  const debtFree = isZero(totals.accepted_debt);

  return (
    <section className="summary" aria-labelledby="report-title">
      <div className="summary__intro">
        <p className="eyebrow">Оплата работ подрядчикам · на конец дня</p>
        <h1 id="report-title" className="display">{formatLongDate(report.report_date)}</h1>
        <p className="lede">
          {plural(report.contracts.length, ['договор', 'договора', 'договоров'])},{' '}
          {plural(works, ['работа', 'работы', 'работ'])}. Принята ли работа и ушли ли деньги — по датам
          событий на этот день, а не по статусам из выгрузки.
        </p>
      </div>

      <dl className="kpis">
        <div className="kpi kpi--primary">
          <dt>Осталось оплатить</dt>
          <dd className="figure">{formatRub(totals.remaining)}</dd>
          <dd className="kpi__note">по всем договорам, аванс уже вычтен</dd>
          {!isZero(totals.overpaid) && (
            <dd className="kpi__alert">
              Переплата {formatRub(totals.overpaid)} — выплачено больше, чем стоят работы. Подробности в договоре ниже.
            </dd>
          )}
        </div>
        <div className="kpi">
          <dt>Выплачено</dt>
          <dd className="kpi__value">{formatRub(totals.paid)}</dd>
          <dd className="kpi__note">без возвратов и очереди</dd>
        </div>
        <div className={`kpi ${debtFree ? '' : 'kpi--attention'}`}>
          <dt>Долг за принятые работы</dt>
          <dd className="kpi__value">{formatRub(totals.accepted_debt)}</dd>
          <dd className="kpi__note">{debtFree ? 'принятые работы оплачены полностью' : 'к оплате уже сейчас'}</dd>
        </div>
        <div className="kpi">
          <dt>В очереди на оплату</dt>
          <dd className="kpi__value">{formatRub(totals.queued)}</dd>
          <dd className="kpi__note">ещё не ушло подрядчикам</dd>
        </div>
      </dl>
    </section>
  );
}
