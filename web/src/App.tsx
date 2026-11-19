import { useCallback, useEffect, useState } from 'react';

import { fetchReport, reportUrl, ReportError, type Report } from './api.ts';
import { Contract } from './components/Contract.tsx';
import { DateControl } from './components/DateControl.tsx';
import { Mark } from './components/Icons.tsx';
import { EmptyState, ErrorState, LoadingState } from './components/States.tsx';
import { Summary } from './components/Summary.tsx';
import { isIsoDate, todayIso, type IsoDate } from './money.ts';

// Дата живёт в адресе (?date=2026-11-10): ссылку на отчёт можно переслать.
function initialDate(): IsoDate {
  const fromUrl = new URLSearchParams(window.location.search).get('date');
  return fromUrl && isIsoDate(fromUrl) ? fromUrl : todayIso();
}

interface ReportState {
  report: Report | null;
  error: ReportError | null;
  loading: boolean;
}

function useReport(date: IsoDate) {
  const [state, setState] = useState<ReportState>({ report: null, error: null, loading: true });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState((previous) => ({ ...previous, loading: true }));
    // Небольшая пауза: пока дату набирают с клавиатуры, не дёргаем сервер на каждую цифру.
    const timer = window.setTimeout(() => {
      fetchReport(date, controller.signal)
        .then((report) => setState({ report, error: null, loading: false }))
        .catch((error: unknown) => {
          if (controller.signal.aborted) return;
          const reportError = error instanceof ReportError ? error : new ReportError('offline', 'Сервер отчётов не отвечает');
          setState({ report: null, error: reportError, loading: false });
        });
    }, 150);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [date, attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  return { ...state, retry };
}

export function App() {
  const [date, setDate] = useState<IsoDate>(initialDate);
  const { report, error, loading, retry } = useReport(date);

  useEffect(() => {
    const url = new URL(window.location.href);
    url.searchParams.set('date', date);
    window.history.replaceState(null, '', url);
  }, [date]);

  let content;
  if (error) content = <ErrorState error={error} onRetry={retry} />;
  else if (!report) content = <LoadingState />;
  else if (report.contracts.length === 0) content = <EmptyState date={report.report_date} />;
  else
    content = (
      <>
        <Summary report={report} />
        {report.contracts.map((contract) => <Contract key={contract.contract_id} contract={contract} />)}
      </>
    );

  return (
    <>
      <a className="skip-link" href="#main">Перейти к отчёту</a>
      <header className="topbar">
        <div className="topbar__inner">
          <p className="brand">
            <Mark className="brand__mark" />
            Расчёты с подрядчиками
          </p>
          <DateControl value={date} onChange={setDate} />
          <nav className="topbar__links" aria-label="Другие форматы отчёта">
            <a href={reportUrl(date, 'text')} target="_blank" rel="noreferrer">Текст</a>
            <a href={reportUrl(date)} target="_blank" rel="noreferrer">JSON</a>
          </nav>
        </div>
      </header>

      <main id="main" className={loading && report ? 'page is-refreshing' : 'page'} aria-busy={loading}>
        {content}
      </main>

      <footer className="footer">
        <details className="method">
          <summary>Как считается отчёт</summary>
          <ol>
            <li>Статусы работ и платежей восстанавливаются на конец выбранного дня по датам событий.</li>
            <li>Выплачено — деньги ушли не позже этой даты и к ней не возвращены. Очередь выплатой не считается.</li>
            <li>Платёж, привязанный к работе, идёт в эту работу, излишек — в общий котёл договора.</li>
            <li>Котёл (платежи без привязки, по порядку оплаты) закрывает принятые работы, начиная с принятой раньше всех.</li>
            <li>Остаток котла — аванс по договору. Сверх стоимости всех неотменённых работ — переплата.</li>
          </ol>
        </details>
        <p className="footer__meta">Данные — CSV из папки data/, перечитываются при каждом запросе.</p>
      </footer>
    </>
  );
}
